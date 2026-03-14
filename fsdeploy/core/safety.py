"""
fsdeploy.core.safety
=====================
Règles de sécurité entre opérations : verrous fichiers, verrous nommés,
priorités, dépendances d'ordre, protection contre les exécutions concurrentes
ou dans le mauvais ordre.

Utilisable indépendamment de tout autre module fsdeploy.

Fonctionnalités :
    FileLock          — verrou exclusif sur un fichier (fcntl)
    OperationLock     — mutex nommé (threading ou fichier PID)
    Priority          — niveau de priorité d'une opération
    DependencyGraph   — DAG d'ordre d'exécution obligatoire
    SafetyManager     — orchestrateur central, vérifie tout avant d'exécuter
    @safe_operation   — décorateur déclaratif sur les méthodes

Option bypass :
    SafetyManager(bypass=True)  — désactive TOUTES les vérifications
    Chaque verrou accepte aussi bypass=True individuellement.

Usage minimal :
    sm = SafetyManager()
    sm.register("mount",    priority=Priority.HIGH,   requires=[])
    sm.register("kernel",   priority=Priority.NORMAL, requires=["mount"])
    sm.register("initramfs",priority=Priority.NORMAL, requires=["mount"])
    sm.register("zbm",      priority=Priority.LOW,    requires=["kernel","initramfs"])

    with sm.run("zbm"):          # vérifie l'ordre, pose les verrous
        install_zbm()

Usage avec décorateur :
    class KernelManager:
        sm = SafetyManager()

        @safe_operation(sm, name="kernel.copy",
                        priority=Priority.HIGH,
                        requires=["mount.boot"],
                        locks=["boot_pool"])
        def copy_kernel(self, ...): ...
"""

from __future__ import annotations

import fcntl
import os
import subprocess
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Callable, Iterator


# =============================================================================
# PRIORITÉ
# =============================================================================

class Priority(IntEnum):
    """
    Niveau de priorité d'une opération.
    Deux opérations de même priorité peuvent tourner en parallèle.
    Une opération CRITICAL bloque toutes les autres jusqu'à sa fin.
    """
    CRITICAL = 0   # ex: rollback d'urgence, export pool
    HIGH     = 1   # ex: mount, umount
    NORMAL   = 2   # ex: kernel copy, initramfs build
    LOW      = 3   # ex: snapshot, stream config

    def label(self) -> str:
        return {0: "CRITIQUE", 1: "HAUTE", 2: "NORMALE", 3: "BASSE"}[self.value]


# =============================================================================
# EXCEPTIONS
# =============================================================================

class SafetyError(Exception):
    """Violation d'une règle de sécurité. Non bypassable par défaut."""

class LockError(SafetyError):
    """Impossible d'acquérir un verrou."""

class OrderError(SafetyError):
    """Opération lancée dans le mauvais ordre (dépendances non satisfaites)."""

class PriorityConflictError(SafetyError):
    """Opération bloquée par une opération de priorité supérieure."""

class CyclicDependencyError(SafetyError):
    """Le graphe de dépendances contient un cycle."""


# =============================================================================
# VERROU FICHIER
# =============================================================================

class FileLock:
    """
    Verrou exclusif sur un fichier via fcntl.flock.
    Fonctionne entre processus (pas seulement entre threads).

    Usage :
        with FileLock("/run/fsdeploy/boot_pool.lock"):
            # opération exclusive sur boot_pool
    """

    LOCK_DIR = Path("/run/fsdeploy/locks")

    def __init__(
        self,
        path: str | Path,
        *,
        timeout: float = 10.0,
        bypass: bool = False,
        shared: bool = False,   # False = exclusif, True = partagé (lecture)
    ) -> None:
        self.path    = Path(path)
        self.timeout = timeout
        self.bypass  = bypass
        self.shared  = shared
        self._fd: int | None = None

    @classmethod
    def for_resource(cls, name: str, **kwargs) -> "FileLock":
        """
        Crée un verrou dans LOCK_DIR pour une ressource nommée.
        ex: FileLock.for_resource("boot_pool")
        """
        cls.LOCK_DIR.mkdir(parents=True, exist_ok=True)
        safe_name = name.replace("/", "_").replace(" ", "_")
        return cls(cls.LOCK_DIR / f"{safe_name}.lock", **kwargs)

    def acquire(self) -> bool:
        if self.bypass:
            return True
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fd = os.open(str(self.path), os.O_CREAT | os.O_WRONLY)
        flag = fcntl.LOCK_SH if self.shared else fcntl.LOCK_EX

        deadline = time.monotonic() + self.timeout
        while True:
            try:
                fcntl.flock(self._fd, flag | fcntl.LOCK_NB)
                # Écrire le PID pour debug
                os.write(self._fd, f"{os.getpid()}\n".encode())
                return True
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    os.close(self._fd)
                    self._fd = None
                    return False
                time.sleep(0.1)

    def release(self) -> None:
        if self._fd is not None:
            try:
                fcntl.flock(self._fd, fcntl.LOCK_UN)
                os.close(self._fd)
            except OSError:
                pass
            self._fd = None

    def __enter__(self) -> "FileLock":
        if not self.acquire():
            raise LockError(
                f"Impossible d'acquérir le verrou fichier : {self.path} "
                f"(timeout={self.timeout}s) — une autre opération est en cours."
            )
        return self

    def __exit__(self, *_) -> None:
        self.release()


# =============================================================================
# VERROU NOMMÉ (threading)
# =============================================================================

class OperationLock:
    """
    Mutex nommé pour éviter deux opérations simultanées sur la même ressource
    dans le même processus (threads).

    Usage :
        with OperationLock("pool:boot_pool"):
            # une seule opération à la fois sur boot_pool
    """

    _registry: dict[str, threading.Lock] = {}
    _registry_lock = threading.Lock()

    def __init__(
        self,
        name: str,
        *,
        timeout: float = 30.0,
        bypass: bool = False,
    ) -> None:
        self.name    = name
        self.timeout = timeout
        self.bypass  = bypass
        self._lock   = self._get_or_create(name)
        self._acquired = False

    @classmethod
    def _get_or_create(cls, name: str) -> threading.Lock:
        with cls._registry_lock:
            if name not in cls._registry:
                cls._registry[name] = threading.Lock()
            return cls._registry[name]

    @classmethod
    def is_locked(cls, name: str) -> bool:
        """Vrai si le verrou est actuellement pris."""
        lock = cls._registry.get(name)
        if lock is None:
            return False
        acquired = lock.acquire(blocking=False)
        if acquired:
            lock.release()
            return False
        return True

    @classmethod
    def active_locks(cls) -> list[str]:
        """Liste tous les verrous actuellement pris."""
        return [name for name in cls._registry if cls.is_locked(name)]

    def acquire(self) -> bool:
        if self.bypass:
            return True
        self._acquired = self._lock.acquire(timeout=self.timeout)
        return self._acquired

    def release(self) -> None:
        if self._acquired and not self.bypass:
            self._lock.release()
            self._acquired = False

    def __enter__(self) -> "OperationLock":
        if not self.acquire():
            raise LockError(
                f"Opération '{self.name}' déjà en cours "
                f"(timeout={self.timeout}s)."
            )
        return self

    def __exit__(self, *_) -> None:
        self.release()


# =============================================================================
# NŒUD D'OPÉRATION
# =============================================================================

@dataclass
class OperationNode:
    """Définition d'une opération dans le graphe de sécurité."""
    name:       str
    priority:   Priority         = Priority.NORMAL
    requires:   list[str]        = field(default_factory=list)
    # Noms de ressources à verrouiller (FileLock.for_resource)
    locks:      list[str]        = field(default_factory=list)
    # Si True, l'opération est exclusive : bloque toutes les autres
    exclusive:  bool             = False
    # Si True, l'opération ne peut être lancée que si on dispose des droits root
    # (soit euid==0, soit sudo NOPASSWD disponible via _has_privilege())
    root_only:  bool             = False
    # Description humaine
    description: str             = ""
    # Nombre de fois où cette opération a été exécutée avec succès
    run_count:  int              = 0
    # Dernière exécution réussie (timestamp)
    last_run:   float            = 0.0

    @property
    def completed(self) -> bool:
        return self.run_count > 0


# =============================================================================
# GRAPHE DE DÉPENDANCES
# =============================================================================

class DependencyGraph:
    """
    Graphe orienté acyclique (DAG) des dépendances entre opérations.
    Garantit qu'une opération ne peut démarrer que si toutes ses dépendances
    ont été complétées.
    """

    def __init__(self) -> None:
        self._nodes: dict[str, OperationNode] = {}

    def add(self, node: OperationNode) -> None:
        """Enregistre un nœud. Lève CyclicDependencyError si un cycle est introduit."""
        self._nodes[node.name] = node
        self._check_cycles()

    def _check_cycles(self) -> None:
        """Détection de cycles par DFS (algorithme des couleurs)."""
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {n: WHITE for n in self._nodes}

        def dfs(name: str) -> None:
            if color[name] == BLACK:
                return
            if color[name] == GRAY:
                raise CyclicDependencyError(
                    f"Cycle détecté dans le graphe de dépendances impliquant '{name}'."
                )
            color[name] = GRAY
            node = self._nodes[name]
            for dep in node.requires:
                if dep in self._nodes:
                    dfs(dep)
            color[name] = BLACK

        for name in list(self._nodes):
            if color[name] == WHITE:
                dfs(name)

    def check_ready(self, name: str) -> tuple[bool, list[str]]:
        """
        Vérifie si une opération peut être lancée.
        Retourne (True, []) ou (False, [liste des dépendances manquantes]).
        """
        node = self._nodes.get(name)
        if node is None:
            return True, []

        missing = [
            dep for dep in node.requires
            if dep in self._nodes and not self._nodes[dep].completed
        ]
        return len(missing) == 0, missing

    def execution_order(self) -> list[str]:
        """
        Retourne un ordre d'exécution valide (tri topologique de Kahn).
        """
        in_degree = {n: 0 for n in self._nodes}
        for node in self._nodes.values():
            for dep in node.requires:
                if dep in in_degree:
                    in_degree[node.name] = in_degree.get(node.name, 0) + 1

        queue = [n for n, d in in_degree.items() if d == 0]
        order: list[str] = []

        while queue:
            # Trier par priorité pour avoir un ordre déterministe
            queue.sort(key=lambda n: self._nodes[n].priority.value)
            name = queue.pop(0)
            order.append(name)
            node = self._nodes[name]
            for dep in node.requires:
                if dep in in_degree:
                    in_degree[dep] -= 1
                    if in_degree[dep] == 0:
                        queue.append(dep)

        return order

    def mark_done(self, name: str) -> None:
        if name in self._nodes:
            self._nodes[name].run_count += 1
            self._nodes[name].last_run = time.monotonic()

    def reset(self, name: str | None = None) -> None:
        targets = [name] if name else list(self._nodes)
        for n in targets:
            if n in self._nodes:
                self._nodes[n].run_count = 0
                self._nodes[n].last_run = 0.0

    def summary(self) -> list[dict]:
        return [
            {
                "name":      n,
                "priority":  node.priority.label(),
                "requires":  node.requires,
                "locks":     node.locks,
                "completed": node.completed,
                "run_count": node.run_count,
            }
            for n, node in self._nodes.items()
        ]


# =============================================================================
# VÉRIFICATION DES DROITS PRIVILÉGIÉS
# =============================================================================

# Cache de session : le sudoers ne change pas en cours d'exécution.
_PRIVILEGE_CACHE: bool | None = None


def _has_privilege() -> bool:
    """
    Retourne True si le processus peut effectuer des opérations root, c'est-à-dire :
      - euid == 0  (root direct), OU
      - sudo -n true réussit  (NOPASSWD configuré par launch.sh)

    fsdeploy tourne en utilisateur normal avec sudo ciblé. Cette fonction
    remplace le simple `os.geteuid() != 0` dans SafetyManager._check_all,
    afin de ne pas bloquer les opérations root_only pour un utilisateur
    qui dispose du sudoers NOPASSWD posé par launch.sh.

    Le résultat est mis en cache pour toute la durée du processus.
    """
    global _PRIVILEGE_CACHE

    if _PRIVILEGE_CACHE is not None:
        return _PRIVILEGE_CACHE

    # Root direct → trivial
    if os.geteuid() == 0:
        _PRIVILEGE_CACHE = True
        return True

    # Tenter sudo -n true (non-interactif, échoue immédiatement si MdP requis)
    try:
        result = subprocess.run(
            ["sudo", "-n", "true"],
            capture_output=True,
            timeout=3,
        )
        _PRIVILEGE_CACHE = (result.returncode == 0)
    except (OSError, subprocess.TimeoutExpired):
        _PRIVILEGE_CACHE = False

    return _PRIVILEGE_CACHE


def invalidate_privilege_cache() -> None:
    """
    Remet à zéro le cache de _has_privilege().
    À appeler si le sudoers a été modifié en cours de session (rare).
    """
    global _PRIVILEGE_CACHE
    _PRIVILEGE_CACHE = None


# =============================================================================
# SAFETY MANAGER
# =============================================================================

class SafetyManager:
    """
    Orchestrateur central de la sécurité entre opérations.

    Chaque module instancie son propre SafetyManager ou partage un singleton.
    Toutes les vérifications sont désactivables via bypass=True.

    Usage :
        sm = SafetyManager()
        sm.register("mount.boot", priority=Priority.HIGH)
        sm.register("kernel.copy", priority=Priority.NORMAL,
                    requires=["mount.boot"], locks=["boot_pool"])

        with sm.run("kernel.copy"):
            copy_kernel_files()

    Bypass complet (ex: mode rescue, tests) :
        sm = SafetyManager(bypass=True)
    """

    # Singleton optionnel partagé entre modules
    _global: "SafetyManager | None" = None

    def __init__(self, *, bypass: bool = False) -> None:
        self.bypass = bypass
        self._graph = DependencyGraph()
        self._active_ops: set[str] = set()
        self._active_lock = threading.Lock()
        self._file_locks: dict[str, FileLock] = {}

    @classmethod
    def global_instance(cls, *, bypass: bool = False) -> "SafetyManager":
        """Retourne (ou crée) le singleton global."""
        if cls._global is None:
            cls._global = cls(bypass=bypass)
        return cls._global

    # ── Enregistrement ────────────────────────────────────────────────────────

    def register(
        self,
        name: str,
        *,
        priority:    Priority  = Priority.NORMAL,
        requires:    list[str] = None,
        locks:       list[str] = None,
        exclusive:   bool      = False,
        root_only:   bool      = False,
        description: str       = "",
    ) -> None:
        """Enregistre une opération dans le graphe de sécurité."""
        node = OperationNode(
            name        = name,
            priority    = priority,
            requires    = requires or [],
            locks       = locks or [],
            exclusive   = exclusive,
            root_only   = root_only,
            description = description,
        )
        self._graph.add(node)

    # ── Exécution sécurisée ───────────────────────────────────────────────────

    @contextmanager
    def run(self, name: str, *, bypass: bool = False) -> Iterator[None]:
        """
        Context manager qui :
          1. Vérifie les droits suffisants (root ou sudo NOPASSWD)
          2. Vérifie les dépendances d'ordre
          3. Vérifie les conflits de priorité
          4. Pose les verrous fichiers et opération
          5. Marque l'opération comme terminée à la sortie (si pas d'exception)

        bypass=True désactive toutes les vérifications pour cet appel.
        """
        effective_bypass = self.bypass or bypass

        if not effective_bypass:
            self._check_all(name)

        acquired_file_locks: list[FileLock] = []
        acquired_op_locks:   list[OperationLock] = []

        try:
            if not effective_bypass:
                node = self._graph._nodes.get(name)
                if node:
                    # Verrous fichiers
                    for resource in node.locks:
                        fl = FileLock.for_resource(resource)
                        fl.__enter__()
                        acquired_file_locks.append(fl)

                    # Verrou opération nommée
                    ol = OperationLock(f"op:{name}")
                    ol.__enter__()
                    acquired_op_locks.append(ol)

                    # Si exclusive, bloquer toutes les autres
                    if node.exclusive:
                        ol_global = OperationLock("__exclusive__", timeout=60.0)
                        ol_global.__enter__()
                        acquired_op_locks.append(ol_global)

            # Marquer l'opération comme active
            with self._active_lock:
                self._active_ops.add(name)

            yield

            # Succès → marquer comme terminée
            self._graph.mark_done(name)

        finally:
            with self._active_lock:
                self._active_ops.discard(name)

            # Libérer verrous en ordre inverse
            for ol in reversed(acquired_op_locks):
                ol.release()
            for fl in reversed(acquired_file_locks):
                fl.release()

    def _check_all(self, name: str) -> None:
        """Effectue toutes les vérifications de sécurité."""
        node = self._graph._nodes.get(name)
        if node is None:
            return  # opération non enregistrée → pas de contrainte

        # 1. Droits suffisants : root direct OU sudo NOPASSWD (configuré par launch.sh)
        if node.root_only and not _has_privilege():
            raise SafetyError(
                f"L'opération '{name}' nécessite les droits root ou sudo (NOPASSWD).\n"
                f"Vérifiez que l'utilisateur appartient au groupe fsdeploy et que\n"
                f"launch.sh a correctement configuré /etc/sudoers.d/10-fsdeploy."
            )

        # 2. Dépendances d'ordre
        ready, missing = self._graph.check_ready(name)
        if not ready:
            raise OrderError(
                f"L'opération '{name}' ne peut pas démarrer — "
                f"dépendances non satisfaites : {', '.join(missing)}.\n"
                f"Ordre suggéré : {' → '.join(self._graph.execution_order())}"
            )

        # 3. Conflit de priorité (opération CRITICAL active)
        with self._active_lock:
            for active_name in self._active_ops:
                active_node = self._graph._nodes.get(active_name)
                if active_node and active_node.priority == Priority.CRITICAL:
                    raise PriorityConflictError(
                        f"L'opération CRITIQUE '{active_name}' est en cours. "
                        f"'{name}' doit attendre."
                    )

        # 4. Vérifier que les ressources à verrouiller ne sont pas déjà prises
        for resource in node.locks:
            if OperationLock.is_locked(f"op:{name}"):
                raise LockError(
                    f"L'opération '{name}' est déjà en cours d'exécution."
                )

    # ── Introspection ─────────────────────────────────────────────────────────

    def status(self) -> dict:
        """Retourne l'état complet du safety manager."""
        return {
            "bypass":       self.bypass,
            "has_privilege": _has_privilege(),
            "active_ops":   list(self._active_ops),
            "active_locks": OperationLock.active_locks(),
            "graph":        self._graph.summary(),
            "order":        self._graph.execution_order(),
        }

    def mark_done(self, name: str) -> None:
        """Marquer manuellement une opération comme terminée (ex: reprise)."""
        self._graph.mark_done(name)

    def reset(self, name: str | None = None) -> None:
        """Remet à zéro un ou tous les compteurs d'exécution."""
        self._graph.reset(name)

    def can_run(self, name: str) -> tuple[bool, str]:
        """
        Vérifie sans lancer si une opération peut démarrer.
        Retourne (True, "") ou (False, "raison").
        """
        try:
            self._check_all(name)
            return True, ""
        except SafetyError as e:
            return False, str(e)


# =============================================================================
# DÉCORATEUR @safe_operation
# =============================================================================

def safe_operation(
    manager:     SafetyManager,
    *,
    name:        str,
    priority:    Priority  = Priority.NORMAL,
    requires:    list[str] = None,
    locks:       list[str] = None,
    exclusive:   bool      = False,
    root_only:   bool      = False,
    description: str       = "",
    bypass:      bool      = False,
):
    """
    Décorateur qui enregistre et sécurise automatiquement une méthode.

    Usage :
        class KernelManager:
            _sm = SafetyManager()

            @safe_operation(_sm,
                name="kernel.copy",
                priority=Priority.HIGH,
                requires=["mount.boot"],
                locks=["boot_pool"],
                root_only=True)
            def copy_kernel(self, src, dst):
                ...
    """
    manager.register(
        name,
        priority    = priority,
        requires    = requires or [],
        locks       = locks or [],
        exclusive   = exclusive,
        root_only   = root_only,
        description = description,
    )

    def decorator(fn: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            local_bypass = kwargs.pop("_bypass", bypass) or manager.bypass
            with manager.run(name, bypass=local_bypass):
                return fn(*args, **kwargs)
        wrapper.__name__   = fn.__name__
        wrapper.__doc__    = fn.__doc__
        wrapper._safe_name = name
        return wrapper
    return decorator


# =============================================================================
# INSTANCE GLOBALE PAR DÉFAUT
# Pré-enregistre l'ordre standard du workflow fsdeploy.
# =============================================================================

def build_default_safety(*, bypass: bool = False) -> SafetyManager:
    """
    Construit le SafetyManager avec le workflow complet de fsdeploy.
    Peut être importé et utilisé tel quel ou étendu.
    """
    sm = SafetyManager(bypass=bypass)

    # ── Détection ─────────────────────────────────────────────────────────
    sm.register("detection.pool",
        priority=Priority.HIGH,
        requires=[],
        description="Import et analyse des pools ZFS")

    sm.register("detection.dataset",
        priority=Priority.HIGH,
        requires=["detection.pool"],
        locks=["probe_mounts"],
        description="Montage temporaire et analyse des datasets")

    sm.register("detection.partition",
        priority=Priority.HIGH,
        requires=[],
        description="Détection des partitions EFI et disques")

    sm.register("detection.report",
        priority=Priority.NORMAL,
        requires=["detection.pool", "detection.dataset", "detection.partition"],
        description="Synthèse du rapport de détection")

    # ── Montages ──────────────────────────────────────────────────────────
    sm.register("mount.boot",
        priority=Priority.HIGH,
        requires=["detection.report"],
        locks=["boot_pool"],
        root_only=True,
        description="Montage de boot_pool")

    sm.register("mount.datasets",
        priority=Priority.HIGH,
        requires=["detection.report"],
        locks=["fast_pool", "data_pool"],
        root_only=True,
        description="Montage des datasets utilisateur")

    # ── Kernel ────────────────────────────────────────────────────────────
    sm.register("kernel.copy",
        priority=Priority.NORMAL,
        requires=["mount.boot"],
        locks=["boot_pool"],
        root_only=True,
        description="Copie du noyau dans boot_pool")

    sm.register("kernel.compile",
        priority=Priority.LOW,
        requires=["mount.boot"],
        locks=["boot_pool"],
        root_only=True,
        exclusive=True,
        description="Compilation d'un noyau custom (exclusif)")

    sm.register("kernel.symlink",
        priority=Priority.NORMAL,
        requires=["kernel.copy"],
        locks=["boot_pool"],
        root_only=True,
        description="Mise à jour des symlinks noyau actif")

    # ── Initramfs ─────────────────────────────────────────────────────────
    sm.register("initramfs.build",
        priority=Priority.NORMAL,
        requires=["mount.boot"],
        locks=["boot_pool"],
        root_only=True,
        description="Construction de l'initramfs (dracut ou cpio)")

    # ── Images squashfs ───────────────────────────────────────────────────
    sm.register("squash.rootfs",
        priority=Priority.LOW,
        requires=["mount.boot"],
        locks=["boot_pool"],
        root_only=True,
        description="Création du rootfs squashfs")

    sm.register("squash.modules",
        priority=Priority.LOW,
        requires=["kernel.copy"],
        locks=["boot_pool"],
        root_only=True,
        description="Création du modules squashfs")

    sm.register("squash.python",
        priority=Priority.LOW,
        requires=["mount.boot"],
        locks=["boot_pool"],
        root_only=True,
        description="Création du python.sfs")

    # ── ZFSBootMenu ───────────────────────────────────────────────────────
    sm.register("zbm.install",
        priority=Priority.LOW,
        requires=["kernel.symlink", "initramfs.build"],
        locks=["boot_pool", "efi"],
        root_only=True,
        exclusive=True,
        description="Installation de ZFSBootMenu EFI (exclusif)")

    sm.register("zbm.config",
        priority=Priority.NORMAL,
        requires=["mount.boot"],
        locks=["boot_pool"],
        root_only=True,
        description="Écriture de la configuration ZFSBootMenu")

    # ── Presets ───────────────────────────────────────────────────────────
    sm.register("preset.write",
        priority=Priority.NORMAL,
        requires=["mount.boot"],
        locks=["boot_pool"],
        description="Écriture d'un preset de boot")

    sm.register("preset.activate",
        priority=Priority.HIGH,
        requires=["preset.write", "zbm.install"],
        locks=["boot_pool"],
        root_only=True,
        description="Activation du preset (symlinks actifs)")

    # ── Cohérence ─────────────────────────────────────────────────────────
    sm.register("coherence.check",
        priority=Priority.NORMAL,
        requires=["mount.boot"],
        description="Vérification cohérence du système de boot")

    # ── Snapshots ─────────────────────────────────────────────────────────
    sm.register("snapshot.create",
        priority=Priority.LOW,
        requires=["detection.report"],
        description="Création d'un snapshot ZFS")

    sm.register("snapshot.restore",
        priority=Priority.HIGH,
        requires=["detection.report"],
        exclusive=True,
        root_only=True,
        description="Restauration d'un snapshot (exclusif)")

    # ── Stream ────────────────────────────────────────────────────────────
    sm.register("stream.start",
        priority=Priority.LOW,
        requires=[],
        description="Démarrage du stream YouTube")

    sm.register("stream.stop",
        priority=Priority.HIGH,
        requires=["stream.start"],
        description="Arrêt du stream YouTube")

    return sm
