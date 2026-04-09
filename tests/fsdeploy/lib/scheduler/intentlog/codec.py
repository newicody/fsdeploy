"""
fsdeploy.scheduler.intentlog.codec
====================================
BDD compacte en mémoire basée sur un arbre Huffman adaptatif.

Unifie tout le runtime du scheduler dans un seul store compressé :
  - Événements (bus + task.completed/failed)
  - Intents (lifecycle)
  - Tasks (lifecycle + commandes)
  - Resources (état courant)
  - Locks (actifs)
  - DAG (dépendances tasks, ownership resources)

Pourquoi Huffman :
  - Le vocabulaire du scheduler est très répétitif : mêmes noms d'events,
    mêmes classes de tasks, mêmes resource paths.
  - Les tokens fréquents (task.completed, pool.boot_pool) deviennent
    des codes de 3-5 bits au lieu de 15-30 octets UTF-8.
  - L'arbre lui-même EST la carte du système — la TUI peut le visualiser.
  - Requêtes par préfixe natives : "tous les events pool.*" = parcours
    d'un sous-arbre.

Architecture :
  - HuffmanNode  : nœud de l'arbre (feuille = token, interne = branche)
  - HuffmanCodec : encode/décode des tokens via l'arbre adaptatif
  - RecordStore  : table append-only de records compressés
  - HuffmanStore : conteneur principal — multiple RecordStores, un seul codec

Thread-safe : le codec et chaque table ont leur propre Lock.

Mécanisme de compression :
  - Les tokens (chaînes de caractères) sont observés au fur et à mesure
    de leur apparition. Le codec maintient un dictionnaire de fréquences.
  - Périodiquement (selon rebuild_threshold) un arbre de Huffman est
    reconstruit à partir des fréquences. Les tokens les plus fréquents
    reçoivent des codes binaires plus courts.
  - L'encodage d'un token connu produit un en-tête (1 octet indiquant la
    longueur en bits) suivi des bits du code Huffman (complétés à l'octet).
  - Un token inconnu est encodé via un octet d'échappement (0x00), suivi
    de la longueur UTF-8 (2 octets) et des octets bruts du token.
  - Les enregistrements (Record) sont sérialisés sous la forme :
        [timestamp 8 octets][longueur payload 2 octets][payload compressé]
  - Plusieurs tables (events, intents, tasks, etc.) partagent le même
    codec Huffman, ce qui permet une compression inter‑table encore plus
    efficace grâce à un vocabulaire global.
  - La persistance sur disque (méthode save()) sauvegarde l'état des
    fréquences et les buffers binaires compressés dans un format binaire
    propriétaire (magic « HFDB »). Le chargement restaure l'arbre et
    les index.
  - La compression peut être visualisée via snapshot() et stats() qui
    fournissent le ratio de compression, le vocabulaire, etc.
"""

import io
import struct
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, Optional


# ═════════════════════════════════════════════════════════════════════════════
# HUFFMAN TREE
# ═════════════════════════════════════════════════════════════════════════════

class HuffmanNode:
    """Nœud de l'arbre Huffman."""

    __slots__ = ("token", "freq", "left", "right")

    def __init__(self, token: str | None = None, freq: int = 0,
                 left: "HuffmanNode | None" = None,
                 right: "HuffmanNode | None" = None):
        self.token = token   # None pour les nœuds internes
        self.freq = freq
        self.left = left
        self.right = right

    @property
    def is_leaf(self) -> bool:
        return self.token is not None

    def __lt__(self, other: "HuffmanNode") -> bool:
        return self.freq < other.freq


class HuffmanCodec:
    """
    Codec Huffman adaptatif.

    L'arbre se reconstruit périodiquement quand les fréquences changent
    significativement. Entre les reconstructions, les nouveaux tokens
    sont encodés avec un code d'échappement + UTF-8 brut.

    Thread-safe.
    """

    # Code d'échappement pour les tokens inconnus
    ESCAPE = "\x00"

    def __init__(self, rebuild_threshold: int = 1024):
        self._lock = threading.Lock()
        self._freq: dict[str, int] = defaultdict(int)
        self._codes: dict[str, str] = {}      # token → bitstring
        self._decode_tree: HuffmanNode | None = None
        self._dirty = False
        self._inserts_since_rebuild = 0
        self._rebuild_threshold = rebuild_threshold
        self._total_tokens = 0

    # ── Fréquences ────────────────────────────────────────────────────────

    def observe(self, token: str) -> None:
        """Enregistre une occurrence d'un token."""
        with self._lock:
            self._freq[token] += 1
            self._total_tokens += 1
            self._inserts_since_rebuild += 1
            if token not in self._codes:
                self._dirty = True
            if self._inserts_since_rebuild >= self._rebuild_threshold:
                self._rebuild()

    def observe_many(self, tokens: list[str]) -> None:
        """Enregistre plusieurs tokens en batch."""
        with self._lock:
            for t in tokens:
                self._freq[t] += 1
                self._total_tokens += 1
                if t not in self._codes:
                    self._dirty = True
            self._inserts_since_rebuild += len(tokens)
            if self._inserts_since_rebuild >= self._rebuild_threshold:
                self._rebuild()

    # ── Construction de l'arbre ───────────────────────────────────────────

    def _rebuild(self) -> None:
        """Reconstruit l'arbre Huffman depuis les fréquences. Appelé sous lock."""
        if not self._freq:
            return

        import heapq

        # Construire le tas
        heap: list[HuffmanNode] = []
        for token, freq in self._freq.items():
            heapq.heappush(heap, HuffmanNode(token=token, freq=freq))

        # Cas dégénéré : un seul token
        if len(heap) == 1:
            node = heapq.heappop(heap)
            root = HuffmanNode(freq=node.freq, left=node)
            self._decode_tree = root
            self._codes = {node.token: "0"}
            self._dirty = False
            self._inserts_since_rebuild = 0
            return

        # Fusion des nœuds
        while len(heap) > 1:
            left = heapq.heappop(heap)
            right = heapq.heappop(heap)
            parent = HuffmanNode(
                freq=left.freq + right.freq,
                left=left,
                right=right,
            )
            heapq.heappush(heap, parent)

        root = heap[0]
        self._decode_tree = root

        # Extraire les codes
        codes: dict[str, str] = {}
        self._extract_codes(root, "", codes)
        self._codes = codes
        self._dirty = False
        self._inserts_since_rebuild = 0

    def _extract_codes(self, node: HuffmanNode, prefix: str,
                       codes: dict[str, str]) -> None:
        if node.is_leaf:
            codes[node.token] = prefix or "0"
            return
        if node.left:
            self._extract_codes(node.left, prefix + "0", codes)
        if node.right:
            self._extract_codes(node.right, prefix + "1", codes)

    def force_rebuild(self) -> None:
        """Force une reconstruction immédiate."""
        with self._lock:
            self._rebuild()

    # ── Encode / Decode ───────────────────────────────────────────────────

    def encode_token(self, token: str) -> bytes:
        """
        Encode un token en bytes compressés.

        Si le token est dans le codebook → bits Huffman packés.
        Si inconnu → byte d'échappement + longueur + UTF-8 brut.
        """
        with self._lock:
            code = self._codes.get(token)

        if code is not None:
            # Pack les bits en bytes avec padding
            bits = code
            n_bits = len(bits)
            # Format : [1 byte n_bits] [packed bytes]
            n_bytes = (n_bits + 7) // 8
            value = int(bits, 2) << (n_bytes * 8 - n_bits)
            return struct.pack("B", n_bits) + value.to_bytes(n_bytes, "big")
        else:
            # Échappement : 0x00 + len(utf8) + utf8
            raw = token.encode("utf-8")
            return b"\x00" + struct.pack(">H", len(raw)) + raw

    def encode_tokens(self, tokens: list[str]) -> bytes:
        """Encode une liste de tokens en un seul blob."""
        buf = io.BytesIO()
        # Header : nombre de tokens
        buf.write(struct.pack(">H", len(tokens)))
        for token in tokens:
            buf.write(self.encode_token(token))
        return buf.getvalue()

    def decode_tokens(self, data: bytes) -> list[str]:
        """Décode un blob en liste de tokens."""
        buf = io.BytesIO(data)
        count = struct.unpack(">H", buf.read(2))[0]
        tokens = []
        for _ in range(count):
            token = self._decode_one(buf)
            if token is not None:
                tokens.append(token)
        return tokens

    def _decode_one(self, buf: io.BytesIO) -> str | None:
        """Décode un token depuis le buffer."""
        header = buf.read(1)
        if not header:
            return None

        n_bits = header[0]

        if n_bits == 0:
            # Échappement
            raw_len = struct.unpack(">H", buf.read(2))[0]
            return buf.read(raw_len).decode("utf-8")

        # Huffman : lire les bits et traverser l'arbre
        n_bytes = (n_bits + 7) // 8
        packed = buf.read(n_bytes)
        if len(packed) < n_bytes:
            return None

        value = int.from_bytes(packed, "big")

        with self._lock:
            node = self._decode_tree

        if node is None:
            return None

        for i in range(n_bits):
            bit = (value >> (n_bytes * 8 - 1 - i)) & 1
            node = node.right if bit else node.left
            if node is None:
                return None
            if node.is_leaf:
                return node.token

        return None

    # ── Statistiques ──────────────────────────────────────────────────────

    @property
    def vocabulary_size(self) -> int:
        with self._lock:
            return len(self._freq)

    @property
    def total_observations(self) -> int:
        return self._total_tokens

    def top_tokens(self, n: int = 20) -> list[tuple[str, int, str]]:
        """Retourne les N tokens les plus fréquents avec leur code Huffman."""
        with self._lock:
            sorted_freq = sorted(self._freq.items(), key=lambda x: -x[1])[:n]
            return [(tok, freq, self._codes.get(tok, "?"))
                    for tok, freq in sorted_freq]

    def compression_ratio(self) -> float:
        """Ratio de compression estimé (< 1.0 = compression effective)."""
        if not self._freq or not self._codes:
            return 1.0
        with self._lock:
            raw_bits = sum(len(tok.encode("utf-8")) * 8 * freq
                          for tok, freq in self._freq.items())
            compressed_bits = sum(len(self._codes.get(tok, "0")) * freq
                                 for tok, freq in self._freq.items())
        return compressed_bits / raw_bits if raw_bits > 0 else 1.0

    def prune(self, min_freq: int = 2) -> int:
        """
        Supprime les tokens dont la fréquence est inférieure à min_freq,
        puis reconstruit l'arbre.
        Retourne le nombre de tokens supprimés.
        """
        with self._lock:
            to_delete = [t for t, f in self._freq.items() if f < min_freq]
            for t in to_delete:
                del self._freq[t]
                self._codes.pop(t, None)
            if to_delete:
                self._dirty = True
                self._rebuild()
            return len(to_delete)

    def dump_tree(self, max_depth: int = 8) -> list[dict]:
        """
        Exporte l'arbre pour visualisation dans la TUI.

        Retourne une liste de nœuds avec :
          - path (ex: "010")
          - token (ou None pour les internes)
          - freq
          - depth
        """
        result = []
        with self._lock:
            self._walk_tree(self._decode_tree, "", 0, max_depth, result)
        return result

    def _walk_tree(self, node: HuffmanNode | None, path: str,
                   depth: int, max_depth: int, result: list) -> None:
        if node is None or depth > max_depth:
            return
        result.append({
            "path": path or "root",
            "token": node.token,
            "freq": node.freq,
            "depth": depth,
            "is_leaf": node.is_leaf,
        })
        self._walk_tree(node.left, path + "0", depth + 1, max_depth, result)
        self._walk_tree(node.right, path + "1", depth + 1, max_depth, result)


# ═════════════════════════════════════════════════════════════════════════════
# RECORD STORE — table append-only compressée
# ═════════════════════════════════════════════════════════════════════════════

@dataclass
class Record:
    """Enregistrement brut avant compression."""
    timestamp: float
    category: str        # event | intent | task | resource | lock | dag
    action: str          # created | started | completed | failed | acquired | released
    tokens: list[str] = field(default_factory=list)   # données du record (noms, paths, IDs, etc.)
    severity: str = "info"  # niveau de sévérité (debug, info, warning, error, critical)
    meta: dict[str, Any] = field(default_factory=dict)


class RecordStore:
    """
    Table append-only de records compressés.

    Chaque record est stocké comme :
      [8 bytes timestamp][2 bytes payload_len][payload Huffman-encoded]

    Index en mémoire :
      - Par catégorie (event/intent/task/...)
      - Par token préfixe (pool.*, dataset.tank.*)
      - Par timestamp (range queries)
    """

    HEADER_SIZE = 10  # 8 (timestamp) + 2 (payload_len)

    def __init__(self, codec: HuffmanCodec, name: str):
        self.codec = codec
        self.name = name
        self._lock = threading.Lock()
        self._buffer = bytearray()
        self._offsets: list[int] = []            # offset de chaque record
        self._index_category: dict[str, list[int]] = defaultdict(list)  # category → [record_idx]
        self._index_prefix: dict[str, list[int]] = defaultdict(list)    # prefix → [record_idx]
        self._index_severity: dict[str, list[int]] = defaultdict(list)  # severity → [record_idx]
        self._count = 0

    def append(self, record: Record) -> int:
        """
        Ajoute un record au store.

        Retourne l'index du record.
        """
        # Observer les tokens pour adaptation du codec
        severity_token = f"severity:{record.severity}"
        all_tokens = [record.category, record.action, severity_token] + record.tokens
        self.codec.observe_many(all_tokens)

        # Encoder
        payload = self.codec.encode_tokens(all_tokens)

        with self._lock:
            offset = len(self._buffer)
            idx = self._count

            # Écrire le header + payload
            self._buffer.extend(struct.pack(">dH", record.timestamp, len(payload)))
            self._buffer.extend(payload)
            self._offsets.append(offset)

            # Indexer
            self._index_category[record.category].append(idx)
            self._index_severity[record.severity].append(idx)
            for token in record.tokens:
                # Ignorer les tokens trop longs pour l'indexation par préfixe
                if len(token) > 200:
                    continue
                # Index par préfixes : "pool.boot_pool" → ["pool", "pool.boot_pool"]
                parts = token.split(".")
                for i in range(1, len(parts) + 1):
                    prefix = ".".join(parts[:i])
                    self._index_prefix[prefix].append(idx)

            self._count += 1
            return idx

    def get(self, idx: int) -> Record | None:
        """Récupère un record par index."""
        with self._lock:
            if idx < 0 or idx >= self._count:
                return None
            return self._decode_at(idx)


    def _decode_at(self, idx: int) -> Record:
        """Décode un record à l'offset donné. Appelé sous lock."""
        offset = self._offsets[idx]
        ts, payload_len = struct.unpack_from(">dH", self._buffer, offset)
        payload = bytes(self._buffer[offset + self.HEADER_SIZE:
                                     offset + self.HEADER_SIZE + payload_len])
        tokens = self.codec.decode_tokens(payload)
        category, action, severity, data_tokens = self._extract_tokens(tokens)
        return Record(
            timestamp=ts,
            category=category,
            action=action,
            severity=severity,
            tokens=data_tokens,
        )

    def _extract_tokens(self, tokens: list[str]):
        """Extrait category, action, severity et data_tokens d'une liste de tokens."""
        if not tokens:
            return "", "", "info", []
        category = tokens[0]
        action = tokens[1] if len(tokens) > 1 else ""
        severity = "info"
        data_start = 2
        if len(tokens) > 2 and tokens[2].startswith("severity:"):
            severity = tokens[2].split(":", 1)[1]
            data_start = 3
        else:
            # pas de token severity, les données commencent à l'indice 2
            data_start = 2
        data_tokens = tokens[data_start:]
        return category, action, severity, data_tokens

    # ── Requêtes ──────────────────────────────────────────────────────────

    def by_category(self, category: str, limit: int = 100) -> list[Record]:
        """Tous les records d'une catégorie."""
        with self._lock:
            indices = self._index_category.get(category, [])[-limit:]
            return [self._decode_at(i) for i in indices]

    def by_severity(self, severity: str, limit: int = 100) -> list[Record]:
        """Tous les records d'un niveau de sévérité."""
        with self._lock:
            indices = self._index_severity.get(severity, [])[-limit:]
            return [self._decode_at(i) for i in indices]

    def by_severity_and_time_range(self, severity: str, start: float, end: float, limit: int = 100) -> list[Record]:
        """Records d'un niveau de sévérité donné dans un intervalle de temps."""
        with self._lock:
            indices = self._index_severity.get(severity, [])
            results = []
            # Parcourir du plus récent au plus ancien (indices croissants)
            for idx in reversed(indices):
                offset = self._offsets[idx]
                ts = struct.unpack_from(">d", self._buffer, offset)[0]
                if ts < start:
                    break
                if ts <= end:
                    results.append(self._decode_at(idx))
                    if len(results) >= limit:
                        break
            results.reverse()
            return results

    def by_category_and_time_range(self, category: str, start: float, end: float, limit: int = 100) -> list[Record]:
        """Records d'une catégorie donnée dans un intervalle de temps."""
        with self._lock:
            indices = self._index_category.get(category, [])
            results = []
            # Parcourir du plus récent au plus ancien (indices croissants)
            for idx in reversed(indices):
                offset = self._offsets[idx]
                ts = struct.unpack_from(">d", self._buffer, offset)[0]
                if ts < start:
                    break
                if ts <= end:
                    results.append(self._decode_at(idx))
                    if len(results) >= limit:
                        break
            results.reverse()
            return results

    def by_severity_and_category(self, severity: str, category: str, limit: int = 100) -> list[Record]:
        """Records d'une sévérité et d'une catégorie données."""
        with self._lock:
            sev_indices = self._index_severity.get(severity, [])
            cat_indices = self._index_category.get(category, [])
            # Intersection des deux listes triées (elles sont en ordre croissant)
            i, j = 0, 0
            common = []
            while i < len(sev_indices) and j < len(cat_indices):
                if sev_indices[i] < cat_indices[j]:
                    i += 1
                elif sev_indices[i] > cat_indices[j]:
                    j += 1
                else:
                    common.append(sev_indices[i])
                    i += 1
                    j += 1
            common = common[-limit:]  # prendre les plus récents
            return [self._decode_at(idx) for idx in common]

    def severity_counts(self) -> dict[str, int]:
        """Retourne le nombre d'enregistrements par niveau de sévérité."""
        with self._lock:
            return {sev: len(indices) for sev, indices in self._index_severity.items()}

    def category_counts(self) -> dict[str, int]:
        """Retourne le nombre d'enregistrements par catégorie."""
        with self._lock:
            return {cat: len(indices) for cat, indices in self._index_category.items()}

    def by_prefix(self, prefix: str, limit: int = 100) -> list[Record]:
        """Tous les records contenant un token commençant par prefix."""
        with self._lock:
            indices = self._index_prefix.get(prefix, [])[-limit:]
            return [self._decode_at(i) for i in indices]

    def by_time_range(self, start: float, end: float,
                      limit: int = 1000) -> list[Record]:
        """Records dans un intervalle de temps."""
        results = []
        with self._lock:
            for i in range(self._count - 1, -1, -1):
                offset = self._offsets[i]
                ts = struct.unpack_from(">d", self._buffer, offset)[0]
                if ts < start:
                    break
                if ts <= end:
                    results.append(self._decode_at(i))
                    if len(results) >= limit:
                        break
        results.reverse()
        return results

    def last(self, n: int = 10) -> list[Record]:
        """Les N derniers records."""
        with self._lock:
            start = max(0, self._count - n)
            return [self._decode_at(i) for i in range(start, self._count)]

    # ── Stats ─────────────────────────────────────────────────────────────

    @property
    def count(self) -> int:
        return self._count

    @property
    def size_bytes(self) -> int:
        return len(self._buffer)

    @property
    def categories(self) -> list[str]:
        with self._lock:
            return list(self._index_category.keys())

    @property
    def prefixes(self) -> list[str]:
        with self._lock:
            return sorted(self._index_prefix.keys())


# ═════════════════════════════════════════════════════════════════════════════
# HUFFMAN STORE — conteneur principal
# ═════════════════════════════════════════════════════════════════════════════

class HuffmanStore:
    """
    BDD compacte unifiée du runtime fsdeploy.

    Combine un codec Huffman adaptatif partagé avec plusieurs
    tables (RecordStores) spécialisées.

    Usage :
        store = HuffmanStore()

        # Enregistrer un événement
        store.log_event("boot.request", params={"preset": "default"})

        # Enregistrer un changement de task
        store.log_task("compile_kernel", "started", locks=["kernel"])

        # Enregistrer une relation DAG
        store.log_dag("initramfs_build", depends_on="kernel_switch")

        # Requêtes
        events = store.events.by_prefix("pool")
        tasks = store.tasks.by_category("task")

        # Snapshot pour la TUI
        snap = store.snapshot()

        # Statistiques de compression
        print(store.stats())
    """

    def __init__(self, rebuild_threshold: int = 1024):
        self.codec = HuffmanCodec(rebuild_threshold=rebuild_threshold)

        # Tables
        self.events = RecordStore(self.codec, "events")
        self.intents = RecordStore(self.codec, "intents")
        self.tasks = RecordStore(self.codec, "tasks")
        self.resources = RecordStore(self.codec, "resources")
        self.locks = RecordStore(self.codec, "locks")
        self.dag = RecordStore(self.codec, "dag")

        # État courant (vue live pour la TUI)
        self._lock = threading.Lock()
        self._active_tasks: dict[str, Record] = {}
        self._active_locks: dict[str, Record] = {}
        self._active_resources: dict[str, str] = {}  # resource_path → status
        self._dag_edges: dict[str, set[str]] = defaultdict(set)  # task → {deps}

    # ═════════════════════════════════════════════════════════════════
    # LOGGING — interface de haut niveau
    # ═════════════════════════════════════════════════════════════════

    def log_event(self, name: str, source: str = "", severity: str = "info", **params) -> None:
        """Enregistre un événement du bus."""
        tokens = [name]
        if source:
            tokens.append(f"src:{source}")
        for k, v in params.items():
            tokens.append(f"{k}:{v}")
        self.events.append(Record(
            timestamp=time.time(),
            category="event",
            action=name.split(".")[-1],
            severity=severity,
            tokens=tokens,
        ))

    def log_intent(self, intent_id: str, intent_class: str,
                   action: str, severity: str = "info", **meta) -> None:
        """Enregistre un changement d'état d'intent."""
        tokens = [intent_id, intent_class]
        for k, v in meta.items():
            tokens.append(f"{k}:{v}")
        self.intents.append(Record(
            timestamp=time.time(),
            category="intent",
            action=action,
            severity=severity,
            tokens=tokens,
        ))

    def log_task(self, task_id: str, action: str,
                 task_class: str = "", severity: str = "info", **meta) -> None:
        """Enregistre un changement d'état de task."""
        tokens = [task_id]
        if task_class:
            tokens.append(task_class)
        for k, v in meta.items():
            tokens.append(f"{k}:{v}")

        record = Record(
            timestamp=time.time(),
            category="task",
            action=action,
            severity=severity,
            tokens=tokens,
        )
        self.tasks.append(record)

        # Mise à jour de l'état courant
        with self._lock:
            if action in ("started", "running"):
                self._active_tasks[task_id] = record
            elif action in ("completed", "failed"):
                self._active_tasks.pop(task_id, None)

    def log_resource(self, path: str, action: str, owner: str = "", severity: str = "info") -> None:
        """Enregistre un changement d'état de resource."""
        tokens = [path]
        if owner:
            tokens.append(f"owner:{owner}")
        self.resources.append(Record(
            timestamp=time.time(),
            category="resource",
            action=action,
            severity=severity,
            tokens=tokens,
        ))
        with self._lock:
            self._active_resources[path] = action

    def log_lock(self, resource_path: str, owner_id: str,
                 action: str, exclusive: bool = True, severity: str = "info") -> None:
        """Enregistre acquisition/libération de lock."""
        tokens = [resource_path, f"owner:{owner_id}"]
        if not exclusive:
            tokens.append("shared")
        record = Record(
            timestamp=time.time(),
            category="lock",
            action=action,
            severity=severity,
            tokens=tokens,
        )
        self.locks.append(record)

        key = f"{resource_path}:{owner_id}"
        with self._lock:
            if action == "acquired":
                self._active_locks[key] = record
            elif action == "released":
                self._active_locks.pop(key, None)

    def log_dag(self, task: str, depends_on: str = "",
                action: str = "edge", severity: str = "info") -> None:
        """Enregistre une relation de dépendance dans le DAG."""
        tokens = [task]
        if depends_on:
            tokens.append(depends_on)
        self.dag.append(Record(
            timestamp=time.time(),
            category="dag",
            action=action,
            severity=severity,
            tokens=tokens,
        ))
        if depends_on:
            with self._lock:
                self._dag_edges[task].add(depends_on)

    # ═════════════════════════════════════════════════════════════════
    # SNAPSHOT — vue temps réel pour la TUI
    # ═════════════════════════════════════════════════════════════════

    def snapshot(self) -> dict[str, Any]:
        """
        Retourne un snapshot léger de l'état courant.

        Conçu pour être consommé par la TUI sans copier
        l'historique complet.
        """
        with self._lock:
            return {
                # État courant
                "active_tasks": {
                    tid: {
                        "class": r.tokens[1] if len(r.tokens) > 1 else "",
                        "started": r.timestamp,
                    }
                    for tid, r in self._active_tasks.items()
                },
                "active_locks": {
                    key: {
                        "resource": r.tokens[0] if r.tokens else "",
                        "since": r.timestamp,
                    }
                    for key, r in self._active_locks.items()
                },
                "resources": dict(self._active_resources),
                "dag": {task: list(deps) for task, deps in self._dag_edges.items()},

                # Compteurs
                "counts": {
                    "events": self.events.count,
                    "intents": self.intents.count,
                    "tasks": self.tasks.count,
                    "resources": self.resources.count,
                    "locks": self.locks.count,
                    "dag": self.dag.count,
                },

                # Compression
                "codec": {
                    "vocabulary": self.codec.vocabulary_size,
                    "observations": self.codec.total_observations,
                    "ratio": self.codec.compression_ratio(),
                },

                # Derniers événements (pour le ticker TUI)
                "recent_events": [
                    {"time": r.timestamp, "name": r.tokens[0] if r.tokens else ""}
                    for r in self.events.last(5)
                ],
            }

    # ═════════════════════════════════════════════════════════════════
    # REQUÊTES DE HAUT NIVEAU
    # ═════════════════════════════════════════════════════════════════

    def query_prefix(self, prefix: str, table: str = "events",
                     limit: int = 100) -> list[Record]:
        """Requête par préfixe sur une table."""
        store = getattr(self, table, self.events)
        return store.by_prefix(prefix, limit=limit)

    def query_severity(self, severity: str, table: str = "events",
                       limit: int = 100) -> list[Record]:
        """Requête par sévérité sur une table."""
        store = getattr(self, table, self.events)
        return store.by_severity(severity, limit=limit)

    def query_time(self, seconds_ago: float, table: str = "events",
                   limit: int = 1000) -> list[Record]:
        """Records des N dernières secondes."""
        now = time.time()
        store = getattr(self, table, self.events)
        return store.by_time_range(now - seconds_ago, now, limit=limit)

    def query_severity_time(self, severity: str, seconds_ago: float, table: str = "events",
                            limit: int = 1000) -> list[Record]:
        """Records d'un niveau de sévérité donné des N dernières secondes."""
        now = time.time()
        store = getattr(self, table, self.events)
        return store.by_severity_and_time_range(severity, now - seconds_ago, now, limit=limit)

    def query_category_time(self, category: str, seconds_ago: float, table: str = "events",
                            limit: int = 1000) -> list[Record]:
        """Records d'une catégorie donnée des N dernières secondes."""
        now = time.time()
        store = getattr(self, table, self.events)
        return store.by_category_and_time_range(category, now - seconds_ago, now, limit=limit)

    def query_severity_and_category(self, severity: str, category: str, table: str = "events",
                                    limit: int = 1000) -> list[Record]:
        """Records d'une sévérité et d'une catégorie données."""
        store = getattr(self, table, self.events)
        return store.by_severity_and_category(severity, category, limit=limit)

    def history(self, table: str = "events", limit: int = 50) -> list[Record]:
        """Derniers records d'une table."""
        store = getattr(self, table, self.events)
        return store.last(limit)

    def get_recent(self, limit: int = 50, severity: Optional[str] = None,
                   category: Optional[str] = None, table: str = "events") -> list[Record]:
        """
        Récupère les enregistrements récents avec filtres optionnels.
        Si severity et category sont tous deux fournis, les deux filtres sont appliqués.
        Sinon, un seul filtre est appliqué si fourni.
        """
        store = getattr(self, table, self.events)
        if severity is not None and category is not None:
            return store.by_severity_and_category(severity, category, limit=limit)
        elif severity is not None:
            return store.by_severity(severity, limit=limit)
        elif category is not None:
            return store.by_category(category, limit=limit)
        else:
            return store.last(limit)

    def export_json(self, path: str | Path, table: str = "all",
                    severity: str | None = None,
                    category: str | None = None,
                    start_time: float | None = None,
                    end_time: float | None = None,
                    limit: int = 10_000) -> None:
        """
        Exporte les logs dans un fichier JSON (non compressé).
        Si table = "all", exporte toutes les tables.
        Les paramètres permettent de filtrer par sévérité, catégorie et plage de temps.
        """
        import json
        from pathlib import Path
        output = []
        tables_to_export = []
        if table == "all":
            tables_to_export = [
                ("events", self.events),
                ("intents", self.intents),
                ("tasks", self.tasks),
                ("resources", self.resources),
                ("locks", self.locks),
                ("dag", self.dag),
            ]
        else:
            store = getattr(self, table, None)
            if store is not None:
                tables_to_export = [(table, store)]

        for name, store in tables_to_export:
            # Choisir la méthode de récupération selon les filtres
            if severity is not None and category is not None:
                records = store.by_severity_and_category(severity, category, limit=limit)
            elif severity is not None:
                records = store.by_severity(severity, limit=limit)
            elif category is not None:
                records = store.by_category(category, limit=limit)
            else:
                records = store.last(limit)

            for rec in records:
                # Appliquer filtres supplémentaires (temps)
                if start_time is not None and rec.timestamp < start_time:
                    continue
                if end_time is not None and rec.timestamp > end_time:
                    continue
                output.append({
                    "table": name,
                    "timestamp": rec.timestamp,
                    "category": rec.category,
                    "action": rec.action,
                    "severity": rec.severity,
                    "tokens": rec.tokens,
                    "meta": rec.meta,
                })
        path_obj = Path(path)
        path_obj.parent.mkdir(parents=True, exist_ok=True)
        with open(path_obj, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False, default=str)

    # ═════════════════════════════════════════════════════════════════
    # PERSISTANCE
    # ═════════════════════════════════════════════════════════════════

    def save(self, path: Path | str) -> int:
        """
        Sauvegarde le store complet sur disque.

        Format binaire :
          [magic 4B "HFDB"] [version 2B] [codec_blob] [table_count 2B]
          Pour chaque table : [name_len 1B] [name] [data_len 4B] [data]

        Retourne le nombre d'octets écrits.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        buf = io.BytesIO()
        buf.write(b"HFDB")  # magic
        buf.write(struct.pack(">H", 1))  # version

        # Sérialiser le codec (fréquences)
        codec_data = self._serialize_codec()
        buf.write(struct.pack(">I", len(codec_data)))
        buf.write(codec_data)

        # Tables
        tables = [
            ("events", self.events),
            ("intents", self.intents),
            ("tasks", self.tasks),
            ("resources", self.resources),
            ("locks", self.locks),
            ("dag", self.dag),
        ]
        buf.write(struct.pack(">H", len(tables)))

        for name, store in tables:
            name_bytes = name.encode("utf-8")
            buf.write(struct.pack("B", len(name_bytes)))
            buf.write(name_bytes)
            with store._lock:
                data = bytes(store._buffer)
            buf.write(struct.pack(">I", len(data)))
            buf.write(data)

        result = buf.getvalue()
        path.write_bytes(result)
        return len(result)

    def load(self, path: Path | str) -> bool:
        """Charge un store depuis le disque."""
        path = Path(path)
        if not path.exists():
            return False

        data = path.read_bytes()
        buf = io.BytesIO(data)

        magic = buf.read(4)
        if magic != b"HFDB":
            return False

        version = struct.unpack(">H", buf.read(2))[0]
        if version != 1:
            return False

        # Codec
        codec_len = struct.unpack(">I", buf.read(4))[0]
        codec_data = buf.read(codec_len)
        self._deserialize_codec(codec_data)

        # Tables
        table_count = struct.unpack(">H", buf.read(2))[0]
        table_map = {
            "events": self.events,
            "intents": self.intents,
            "tasks": self.tasks,
            "resources": self.resources,
            "locks": self.locks,
            "dag": self.dag,
        }

        for _ in range(table_count):
            name_len = struct.unpack("B", buf.read(1))[0]
            name = buf.read(name_len).decode("utf-8")
            data_len = struct.unpack(">I", buf.read(4))[0]
            table_data = buf.read(data_len)

            store = table_map.get(name)
            if store:
                with store._lock:
                    store._buffer = bytearray(table_data)
                    # Reconstruire les offsets et index
                    self._rebuild_store_index(store)

        return True

    def _serialize_codec(self) -> bytes:
        """Sérialise les fréquences du codec."""
        buf = io.BytesIO()
        with self.codec._lock:
            freq = dict(self.codec._freq)
        buf.write(struct.pack(">I", len(freq)))
        for token, count in freq.items():
            raw = token.encode("utf-8")
            buf.write(struct.pack(">HI", len(raw), count))
            buf.write(raw)
        return buf.getvalue()


    def _deserialize_codec(self, data: bytes) -> None:
        """Restaure les fréquences et reconstruit l'arbre."""
        buf = io.BytesIO(data)
        count = struct.unpack(">I", buf.read(4))[0]
        with self.codec._lock:
            self.codec._freq.clear()
            for _ in range(count):
                raw_len, freq = struct.unpack(">HI", buf.read(6))
                token = buf.read(raw_len).decode("utf-8")
                self.codec._freq[token] = freq
                self.codec._total_tokens += freq
            self.codec._rebuild()

    def _rebuild_store_index(self, store: RecordStore) -> None:
        """Reconstruit les index d'un store après chargement. Appelé sous lock."""
        store._offsets.clear()
        store._index_category.clear()
        store._index_prefix.clear()
        store._index_severity.clear()
        store._count = 0

        offset = 0
        while offset + RecordStore.HEADER_SIZE <= len(store._buffer):
            ts, payload_len = struct.unpack_from(">dH", store._buffer, offset)
            if offset + RecordStore.HEADER_SIZE + payload_len > len(store._buffer):
                break

            idx = store._count
            store._offsets.append(offset)

            # Décoder pour indexer
            payload = bytes(store._buffer[offset + RecordStore.HEADER_SIZE:
                                          offset + RecordStore.HEADER_SIZE + payload_len])
            try:
                tokens = self.codec.decode_tokens(payload)
                category, action, severity, data_tokens = store._extract_tokens(tokens)
                store._index_category[category].append(idx)
                store._index_severity[severity].append(idx)
                for token in data_tokens:
                    parts = token.split(".")
                    for i in range(1, len(parts) + 1):
                        store._index_prefix[".".join(parts[:i])].append(idx)
            except Exception:
                pass

            store._count += 1
            offset += RecordStore.HEADER_SIZE + payload_len

    # ═════════════════════════════════════════════════════════════════
    # STATISTIQUES
    # ═════════════════════════════════════════════════════════════════

    def stats(self) -> dict[str, Any]:
        """Statistiques complètes du store."""
        from collections import defaultdict

        tables = {
            "events": self.events,
            "intents": self.intents,
            "tasks": self.tasks,
            "resources": self.resources,
            "locks": self.locks,
            "dag": self.dag,
        }

        total_records = sum(t.count for t in tables.values())
        total_bytes = sum(t.size_bytes for t in tables.values())

        # Agrégation des comptes par sévérité
        severity_agg = defaultdict(int)
        severity_by_table = {}
        for name, t in tables.items():
            sev_counts = t.severity_counts()
            severity_by_table[name] = dict(sev_counts)
            for sev, cnt in sev_counts.items():
                severity_agg[sev] += cnt

        # Agrégation des comptes par catégorie
        category_agg = defaultdict(int)
        category_by_table = {}
        for name, t in tables.items():
            cat_counts = t.category_counts()
            category_by_table[name] = dict(cat_counts)
            for cat, cnt in cat_counts.items():
                category_agg[cat] += cnt

        return {
            "tables": {
                name: {"records": t.count, "bytes": t.size_bytes}
                for name, t in tables.items()
            },
            "total_records": total_records,
            "total_bytes": total_bytes,
            "severity_counts": dict(severity_agg),
            "severity_by_table": severity_by_table,
            "category_counts": dict(category_agg),
            "category_by_table": category_by_table,
            "codec_vocabulary": self.codec.vocabulary_size,
            "codec_observations": self.codec.total_observations,
            "compression_ratio": self.codec.compression_ratio(),
            "top_tokens": self.codec.top_tokens(10),
        }
