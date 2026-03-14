"""
fsdeploy.core.tasks
====================
Gestionnaire central de toutes les tâches subprocess lancées par fsdeploy.

Responsabilités :
  - Lancer un subprocess de façon async (asyncio.create_subprocess_exec)
  - Suivre chaque tâche : id, nom, commande, état, durée, progression, logs
  - Estimer le pourcentage et le temps restant (parseur de sortie ou durée
    historique si la commande n'émet pas de progression)
  - Permettre l'annulation propre (SIGTERM → SIGKILL si nécessaire)
  - Exposer une API observable pour l'UI Textual (callbacks + snapshot)

Usage depuis n'importe quel module :
    from fsdeploy.core.tasks import get_task_manager, TaskSpec

    tm = get_task_manager()

    task_id = await tm.submit(TaskSpec(
        name     = "Construction initramfs",
        category = "initramfs",
        cmd      = ["dracut", "--force", "--kver", kver, str(dst)],
        timeout  = 300,
    ))
    result = await tm.wait(task_id)

Usage depuis l'UI Textual :
    tm = get_task_manager()
    tm.on_change(lambda tasks: self.app.call_from_thread(self.refresh, tasks))
    tasks  = tm.snapshot()   # list[TaskInfo] — thread-safe
    counts = tm.count()      # {"RUNNING": 1, "DONE": 4, "TOTAL": 5, ...}
    await tm.cancel(task_id)
"""

from __future__ import annotations

import asyncio
import os
import re
import signal
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Callable, Sequence


# =============================================================================
# ÉTATS
# =============================================================================

class TaskState(Enum):
    PENDING    = auto()   # soumise, pas encore démarrée
    RUNNING    = auto()   # subprocess actif
    CANCELLING = auto()   # SIGTERM envoyé, en attente de fin
    DONE       = auto()   # terminée exit 0
    FAILED     = auto()   # terminée exit != 0
    CANCELLED  = auto()   # annulée par l'utilisateur


# =============================================================================
# DURÉES HISTORIQUES PAR CATÉGORIE (secondes)
# Fallback d'estimation quand la commande n'émet pas de %
# =============================================================================

_HISTORICAL_DURATION: dict[str, float] = {
    "zpool_import":   4.0,
    "zpool_export":   2.0,
    "zfs_mount":      1.5,
    "zfs_umount":     1.0,
    "zfs_snapshot":   2.0,
    "zfs_send":      60.0,
    "zfs_recv":      60.0,
    "zfs_destroy":    2.0,
    "mksquashfs":   120.0,
    "dracut":       180.0,
    "apt_install":  120.0,
    "apt_update":    30.0,
    "git_clone":     20.0,
    "pip_install":   30.0,
    "efibootmgr":     2.0,
    "ffmpeg":        -1.0,   # -1 = durée indéfinie (stream continu)
    "kernel_compile":900.0,
    "cpio_build":    15.0,
    "cp_image":      10.0,
    "default":       10.0,
}


# =============================================================================
# PARSEURS DE PROGRESSION
# Chaque parseur reçoit une ligne stdout/stderr, renvoie float 0-100 ou None
# =============================================================================

def _parse_mksquashfs(line: str) -> float | None:
    # "[==========             ] 247/512  48%"
    m = re.search(r"(\d+)%", line)
    return float(m.group(1)) if m else None

def _parse_apt(line: str) -> float | None:
    # "Unpacking foo (12/42)" ou "XX%"
    m = re.search(r"\((\d+)/(\d+)\)", line)
    if m:
        return 100.0 * int(m.group(1)) / max(int(m.group(2)), 1)
    m = re.search(r"(\d+)%", line)
    return float(m.group(1)) if m else None

def _parse_generic(line: str) -> float | None:
    m = re.search(r"(\d+)\s*%", line)
    return float(m.group(1)) if m else None

def _parse_none(_line: str) -> float | None:
    return None


# Mapping nom d'exécutable → (catégorie, parseur)
_CMD_PROFILES: dict[str, tuple[str, Callable[[str], float | None]]] = {
    "mksquashfs": ("mksquashfs",    _parse_mksquashfs),
    "dracut":     ("dracut",        _parse_none),
    "ffmpeg":     ("ffmpeg",        _parse_none),
    "apt-get":    ("apt_install",   _parse_apt),
    "apt":        ("apt_install",   _parse_apt),
    "pip":        ("pip_install",   _parse_none),
    "pip3":       ("pip_install",   _parse_none),
    "git":        ("git_clone",     _parse_generic),
    "efibootmgr": ("efibootmgr",   _parse_generic),
    "cp":         ("cp_image",      _parse_generic),
}


def _profile_for_cmd(cmd: Sequence[str]) -> tuple[str, Callable[[str], float | None]]:
    if not cmd:
        return "default", _parse_generic
    exe = Path(cmd[0]).name.lower()

    if exe == "zfs" and len(cmd) > 1:
        sub = cmd[1].lower()
        cat = {
            "snapshot": "zfs_snapshot",
            "send":     "zfs_send",
            "recv":     "zfs_recv",
            "receive":  "zfs_recv",
            "mount":    "zfs_mount",
            "umount":   "zfs_umount",
            "destroy":  "zfs_destroy",
        }.get(sub, "zfs_mount")
        return cat, _parse_none

    if exe == "zpool" and len(cmd) > 1:
        sub = cmd[1].lower()
        cat = {
            "import": "zpool_import",
            "export": "zpool_export",
        }.get(sub, "zpool_import")
        return cat, _parse_generic

    return _CMD_PROFILES.get(exe, ("default", _parse_generic))


# =============================================================================
# SPEC (entrée)
# =============================================================================

@dataclass
class TaskSpec:
    """
    Description d'une tâche à soumettre.

        name        — Nom humain affiché dans l'UI
        cmd         — Commande sous forme de liste
        category    — Catégorie explicite (déduit depuis cmd si absent)
        timeout     — Timeout en secondes (None = pas de limite)
        env         — Variables d'environnement supplémentaires
        cwd         — Répertoire de travail
        on_output   — Callback(line: str) par ligne stdout/stderr
        cancelable  — Si False, cancel() est ignoré
        tags        — Métadonnées libres (pool, dataset, kernel_ver…)
    """
    name:       str
    cmd:        Sequence[str]
    category:   str                              = ""
    timeout:    float | None                     = None
    env:        dict[str, str] | None            = None
    cwd:        str | Path | None                = None
    on_output:  Callable[[str], None] | None     = None
    cancelable: bool                             = True
    tags:       dict[str, str]                   = field(default_factory=dict)


# =============================================================================
# SNAPSHOT (sortie — immuable, thread-safe)
# =============================================================================

@dataclass(frozen=True)
class TaskInfo:
    """
    Vue immuable d'une tâche — safe à passer à l'UI depuis n'importe quel thread.
    """
    id:         str
    name:       str
    category:   str
    cmd_str:    str
    state:      TaskState
    percent:    float | None
    elapsed:    float
    eta:        float | None
    last_line:  str
    exit_code:  int | None
    error:      str
    cancelable: bool
    tags:       dict[str, str]

    @property
    def is_active(self) -> bool:
        return self.state in (TaskState.PENDING, TaskState.RUNNING, TaskState.CANCELLING)

    @property
    def elapsed_str(self) -> str:
        s = int(self.elapsed)
        if s < 60:   return f"{s}s"
        if s < 3600: return f"{s//60}m{s%60:02d}s"
        return f"{s//3600}h{(s%3600)//60:02d}m"

    @property
    def eta_str(self) -> str:
        if self.eta is None: return "—"
        if self.eta < 0:     return "∞"
        s = int(self.eta)
        if s < 60:   return f"~{s}s"
        if s < 3600: return f"~{s//60}m{s%60:02d}s"
        return f"~{s//3600}h{(s%3600)//60:02d}m"

    @property
    def percent_str(self) -> str:
        return f"{self.percent:.0f}%" if self.percent is not None else "—"

    @property
    def state_icon(self) -> str:
        return {
            TaskState.PENDING:    "⏳",
            TaskState.RUNNING:    "⚙️ ",
            TaskState.CANCELLING: "🛑",
            TaskState.DONE:       "✅",
            TaskState.FAILED:     "❌",
            TaskState.CANCELLED:  "⊘ ",
        }.get(self.state, "?")


# =============================================================================
# RÉSULTAT FINAL
# =============================================================================

@dataclass(frozen=True)
class TaskResult:
    task_id:   str
    success:   bool
    exit_code: int | None
    error:     str
    elapsed:   float
    logs:      list[str]


# =============================================================================
# TÂCHE INTERNE (mutable, privée)
# =============================================================================

class _Task:
    def __init__(self, spec: TaskSpec) -> None:
        self.id          = str(uuid.uuid4())
        self.spec        = spec
        self.state       = TaskState.PENDING
        self.percent     : float | None = None
        self.started_at  : float | None = None
        self.ended_at    : float | None = None
        self.exit_code   : int | None   = None
        self.error       : str          = ""
        self.last_line   : str          = ""
        self.logs        : list[str]    = []
        self._process    : asyncio.subprocess.Process | None = None
        self._done_event : asyncio.Event = asyncio.Event()

        cat, parser = _profile_for_cmd(spec.cmd)
        self.category  = spec.category or cat
        self._parser   = parser
        self._expected : float = _HISTORICAL_DURATION.get(
            self.category, _HISTORICAL_DURATION["default"]
        )

    @property
    def elapsed(self) -> float:
        if self.started_at is None:
            return 0.0
        return (self.ended_at or time.monotonic()) - self.started_at

    @property
    def eta(self) -> float | None:
        if self.state not in (TaskState.RUNNING, TaskState.CANCELLING):
            return None
        if self._expected < 0:
            return -1.0
        if self.percent is not None and self.percent > 0:
            elapsed = self.elapsed
            total_est = elapsed / (self.percent / 100.0)
            return max(0.0, total_est - elapsed)
        if self._expected > 0:
            return max(0.0, self._expected - self.elapsed)
        return None

    @property
    def percent_effective(self) -> float | None:
        if self.percent is not None:
            return self.percent
        if self._expected > 0 and self.started_at is not None:
            return min(99.0, 100.0 * self.elapsed / self._expected)
        return None

    def push_line(self, line: str) -> None:
        line = line.rstrip("\r\n")
        if not line:
            return
        self.last_line = line
        self.logs.append(line)
        parsed = self._parser(line)
        if parsed is not None:
            self.percent = float(parsed)
        if self.spec.on_output:
            try:
                self.spec.on_output(line)
            except Exception:
                pass

    def to_info(self) -> TaskInfo:
        return TaskInfo(
            id         = self.id,
            name       = self.spec.name,
            category   = self.category,
            cmd_str    = " ".join(str(a) for a in self.spec.cmd),
            state      = self.state,
            percent    = self.percent_effective,
            elapsed    = self.elapsed,
            eta        = self.eta,
            last_line  = self.last_line,
            exit_code  = self.exit_code,
            error      = self.error,
            cancelable = self.spec.cancelable,
            tags       = dict(self.spec.tags),
        )


# =============================================================================
# TASK MANAGER
# =============================================================================

class TaskManager:
    """
    Gestionnaire central de toutes les tâches subprocess.

        tm = get_task_manager()
        task_id = await tm.submit(spec)
        await tm.cancel(task_id)
        result  = await tm.wait(task_id)
        infos   = tm.snapshot()
        tm.on_change(callback)
    """

    def __init__(self) -> None:
        self._tasks     : dict[str, _Task]                          = {}
        self._lock      : threading.Lock                            = threading.Lock()
        self._callbacks : list[Callable[[list[TaskInfo]], None]]    = []

    # ── Abonnement ────────────────────────────────────────────────────────────

    def on_change(self, callback: Callable[[list[TaskInfo]], None]) -> None:
        """Enregistre un callback appelé après chaque changement d'état."""
        with self._lock:
            self._callbacks.append(callback)

    def off_change(self, callback: Callable[[list[TaskInfo]], None]) -> None:
        with self._lock:
            self._callbacks = [c for c in self._callbacks if c is not callback]

    def _notify(self) -> None:
        snap = self.snapshot()
        for cb in list(self._callbacks):
            try:
                cb(snap)
            except Exception:
                pass

    # ── Lecture ───────────────────────────────────────────────────────────────

    def snapshot(self) -> list[TaskInfo]:
        """Liste immuable de toutes les tâches — safe depuis l'UI."""
        with self._lock:
            return [t.to_info() for t in self._tasks.values()]

    def get(self, task_id: str) -> TaskInfo | None:
        with self._lock:
            t = self._tasks.get(task_id)
            return t.to_info() if t else None

    def active(self) -> list[TaskInfo]:
        return [t for t in self.snapshot() if t.is_active]

    def count(self) -> dict[str, int]:
        snap   = self.snapshot()
        result = {s.name: 0 for s in TaskState}
        result["TOTAL"] = len(snap)
        for info in snap:
            result[info.state.name] += 1
        return result

    # ── Soumission ────────────────────────────────────────────────────────────

    async def submit(self, spec: TaskSpec) -> str:
        """Soumet et démarre une tâche. Retourne l'ID. Non bloquant."""
        task = _Task(spec)
        with self._lock:
            self._tasks[task.id] = task
        asyncio.create_task(self._run(task))
        return task.id

    async def submit_and_wait(self, spec: TaskSpec) -> TaskResult:
        """Soumet et attend la fin. Bloquant pour l'appelant."""
        task_id = await self.submit(spec)
        return await self.wait(task_id)

    # ── Attente ───────────────────────────────────────────────────────────────

    async def wait(self, task_id: str) -> TaskResult:
        with self._lock:
            task = self._tasks.get(task_id)
        if task is None:
            return TaskResult(task_id, False, None, "Tâche introuvable", 0.0, [])
        await task._done_event.wait()
        with self._lock:
            info = task.to_info()
            logs = list(task.logs)
        return TaskResult(
            task_id   = task_id,
            success   = info.state == TaskState.DONE,
            exit_code = info.exit_code,
            error     = info.error,
            elapsed   = info.elapsed,
            logs      = logs,
        )

    # ── Annulation ────────────────────────────────────────────────────────────

    async def cancel(self, task_id: str, force: bool = False) -> bool:
        """
        Annule une tâche — SIGTERM, puis SIGKILL après 5s si force=True.
        Retourne True si l'annulation a été déclenchée.
        """
        with self._lock:
            task = self._tasks.get(task_id)
        if task is None or not task.spec.cancelable:
            return False
        if task.state not in (TaskState.PENDING, TaskState.RUNNING):
            return False
        with self._lock:
            task.state = TaskState.CANCELLING
        self._notify()
        if task._process and task._process.returncode is None:
            try:
                task._process.send_signal(signal.SIGTERM)
            except ProcessLookupError:
                pass
            if force:
                asyncio.create_task(self._force_kill(task))
        return True

    async def cancel_all(self) -> int:
        ids = [t.id for t in self.active()]
        return sum(1 for tid in ids if await self.cancel(tid))

    # ── Nettoyage ─────────────────────────────────────────────────────────────

    def purge_done(self) -> int:
        """Supprime les tâches terminées. Retourne le nombre supprimées."""
        with self._lock:
            done = [tid for tid, t in self._tasks.items()
                    if t.state in (TaskState.DONE, TaskState.FAILED, TaskState.CANCELLED)]
            for tid in done:
                del self._tasks[tid]
        if done:
            self._notify()
        return len(done)

    # ── Boucle interne ────────────────────────────────────────────────────────

    async def _run(self, task: _Task) -> None:
        with self._lock:
            task.state      = TaskState.RUNNING
            task.started_at = time.monotonic()
        self._notify()

        env = {**os.environ}
        if task.spec.env:
            env.update(task.spec.env)
        cwd = str(task.spec.cwd) if task.spec.cwd else None

        try:
            proc = await asyncio.create_subprocess_exec(
                *task.spec.cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=env,
                cwd=cwd,
            )
        except FileNotFoundError as exc:
            with self._lock:
                task.state    = TaskState.FAILED
                task.error    = f"Commande introuvable : {task.spec.cmd[0]} — {exc}"
                task.ended_at = time.monotonic()
            task._done_event.set()
            self._notify()
            return
        except Exception as exc:
            with self._lock:
                task.state    = TaskState.FAILED
                task.error    = f"Erreur démarrage : {exc}"
                task.ended_at = time.monotonic()
            task._done_event.set()
            self._notify()
            return

        with self._lock:
            task._process = proc

        try:
            coro = self._read_lines(task, proc)
            if task.spec.timeout:
                await asyncio.wait_for(coro, timeout=task.spec.timeout)
            else:
                await coro
        except asyncio.TimeoutError:
            with self._lock:
                task.state = TaskState.CANCELLING
                task.error = f"Timeout ({task.spec.timeout}s)"
            try:
                proc.kill()
            except ProcessLookupError:
                pass

        await proc.wait()

        with self._lock:
            task.ended_at  = time.monotonic()
            task.exit_code = proc.returncode
            if task.state == TaskState.CANCELLING:
                task.state = TaskState.CANCELLED
            elif proc.returncode == 0:
                task.state   = TaskState.DONE
                task.percent = 100.0
            else:
                task.state = TaskState.FAILED
                if not task.error:
                    task.error = f"Exit code {proc.returncode}"

        task._done_event.set()
        self._notify()

    async def _read_lines(self, task: _Task, proc: asyncio.subprocess.Process) -> None:
        assert proc.stdout is not None
        last_notify = time.monotonic()
        async for raw in proc.stdout:
            line = raw.decode(errors="replace")
            with self._lock:
                task.push_line(line)
            now = time.monotonic()
            if now - last_notify >= 0.1:   # max 10 notifications/s
                self._notify()
                last_notify = now

    async def _force_kill(self, task: _Task) -> None:
        await asyncio.sleep(5)
        with self._lock:
            proc = task._process
        if proc and proc.returncode is None:
            try:
                proc.kill()
            except ProcessLookupError:
                pass


# =============================================================================
# SINGLETON GLOBAL
# =============================================================================

_manager      : TaskManager | None = None
_manager_lock : threading.Lock     = threading.Lock()


def get_task_manager() -> TaskManager:
    """Retourne le TaskManager singleton. Thread-safe."""
    global _manager
    if _manager is None:
        with _manager_lock:
            if _manager is None:
                _manager = TaskManager()
    return _manager


# =============================================================================
# RACCOURCI
# =============================================================================

async def run_task(
    name:       str,
    cmd:        Sequence[str],
    *,
    category:   str                          = "",
    timeout:    float | None                 = None,
    env:        dict[str, str] | None        = None,
    cwd:        str | Path | None            = None,
    on_output:  Callable[[str], None] | None = None,
    cancelable: bool                         = True,
    tags:       dict[str, str] | None        = None,
) -> TaskResult:
    """
    Soumet et attend une tâche en une ligne.

        result = await run_task(
            "Import pool boot_pool",
            ["zpool", "import", "-f", "boot_pool"],
            timeout=10,
            tags={"pool": "boot_pool"},
        )
        if not result.success:
            raise RuntimeError(result.error)
    """
    return await get_task_manager().submit_and_wait(TaskSpec(
        name       = name,
        cmd        = list(cmd),
        category   = category,
        timeout    = timeout,
        env        = env,
        cwd        = cwd,
        on_output  = on_output,
        cancelable = cancelable,
        tags       = tags or {},
    ))
