"""
Store persistant pour les logs d'intentions.
Étend RecordStore avec une sauvegarde sur disque.

Ce store utilise un format JSONL (une ligne JSON par enregistrement) qui
n'est PAS compressé, contrairement au HuffmanStore du module codec.
Il est conçu pour une persistance simple et lisible par un humain,
tandis que le HuffmanStore fournit une compression forte en mémoire
et sur disque (format binaire HFDB). Les deux mécanismes peuvent
coexister : IntentLog peut écrire à la fois dans ce fichier texte
et dans le store compressé via son attribut `store`.
"""

import os
import struct
import threading
import json
from collections import defaultdict
from typing import Any

from .codec import Record, RecordStore, HuffmanCodec


class PersistentRecordStore(RecordStore):
    """
    RecordStore qui persiste les enregistrements dans un fichier JSONL.
    Format sur disque : une ligne JSON par enregistrement, lisible par un humain.
    """

    def __init__(self, filename: str) -> None:
        """
        :param filename: Chemin du fichier de persistance.
        """
        from .codec import HuffmanCodec
        codec = HuffmanCodec(rebuild_threshold=10000)
        self._filename = filename
        self._file_lock = threading.Lock()
        self._loading = False
        super().__init__(codec, name="persistent")
        self._dirty = False

        # Charge les enregistrements existants
        if os.path.exists(filename):
            self._load()

    def _load(self) -> None:
        """Charge tous les enregistrements depuis le fichier (format JSONL)."""
        self._loading = True
        try:
            if not os.path.exists(self._filename):
                return

            with open(self._filename, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    entry = json.loads(line)
                    # Compatibilité avec l'ancien format (path, payload) et nouveau (tokens, meta, severity)
                    tokens = []
                    meta = {}
                    severity = "info"
                    if 'path' in entry:
                        tokens.append(entry['path'])
                    if 'payload' in entry and isinstance(entry['payload'], dict):
                        meta = entry['payload']
                    if 'severity' in entry:
                        severity = entry['severity']
                    # Si l'entrée a directement des tokens/meta, les utiliser
                    if 'tokens' in entry:
                        tokens = entry['tokens']
                    if 'meta' in entry:
                        meta = entry['meta']
                    rec = Record(
                        timestamp=entry['timestamp'],
                        category=entry['category'],
                        action=entry.get('action', 'persist'),
                        severity=severity,
                        tokens=tokens,
                        meta=meta,
                    )
                    # Ajout interne sans persister
                    severity_token = f"severity:{rec.severity}"
                    all_tokens = [rec.category, rec.action, severity_token] + rec.tokens
                    self.codec.observe_many(all_tokens)
                    payload = self.codec.encode_tokens(all_tokens)
                    offset = len(self._buffer)
                    idx = self._count
                    self._buffer.extend(struct.pack(">dH", rec.timestamp, len(payload)))
                    self._buffer.extend(payload)
                    self._offsets.append(offset)
                    self._index_category[rec.category].append(idx)
                    self._index_severity[rec.severity].append(idx)
                    for token in rec.tokens:
                        if len(token) > 200:
                            continue
                        parts = token.split(".")
                        for i in range(1, len(parts) + 1):
                            prefix = ".".join(parts[:i])
                            self._index_prefix[prefix].append(idx)
                    self._count += 1
        finally:
            self._loading = False
        self._dirty = False

    def append(self, record: Record) -> int:
        """Ajoute un enregistrement et le persiste immédiatement."""
        idx = super().append(record)
        self._persist_one(record)
        return idx

    def _persist_one(self, record: Record) -> None:
        """Écrit un seul enregistrement à la fin du fichier (format JSONL)."""
        if self._loading:
            return
        with self._file_lock:
            # Sérialiser l'ensemble de l'enregistrement en JSON (nouveau format)
            entry = {
                'timestamp': record.timestamp,
                'category': record.category,
                'action': record.action,
                'severity': record.severity,
                'tokens': record.tokens,
                'meta': record.meta,
            }
            line = json.dumps(entry, ensure_ascii=False)
            with open(self._filename, "a", encoding="utf-8", buffering=1) as f:
                f.write(line + "\n")
