"""
fsdeploy.scheduler.model.task
=============================
Classe de base pour toutes les tâches exécutables.

Chaque Task :
  - déclare ses ressources et locks
  - implémente before_run / run / after_run
  - a accès au runtime pour émettre des sous-événements
  - peut exécuter des commandes système via run_cmd()
"""

import subprocess
import shlex
import time
from dataclasses import dataclass, field
from typing import Any, Optional
from pathlib import Path

from scheduler.model.resource import Resource
from scheduler.model.lock import Lock


@dataclass
class CommandResult:
    """Résultat d'une commande système."""

    cmd: str
    returncode: int
    stdout: str
    stderr: str
    duration: float
    success: bool = True

    def __post_init__(self):
        self.success = self.returncode == 0


class Task:
    """
    Tâche exécutable par le scheduler.

    Sous-classes : override run() au minimum.
    Optionnel : before_run(), after_run(), required_resources(), required_locks().
    """

    executor = "default"  # "default" | "threaded"

    def __init__(self, id: str | None = None, params: dict | None = None,
                 context: dict | None = None):
        self.id = id
        self.params = params or {}
        self.context = context or {}
        self.runtime = None
        self.meta: dict[str, Any] = {}
        self._cmd_log: list[CommandResult] = []
        self._before_run_called = False

    # ── Runtime ───────────────────────────────────────────────────────────────

    def set_runtime(self, runtime) -> None:
        self.runtime = runtime

    def emit_event(self, name: str, params: dict | None = None) -> None:
        """Émet un sous-événement dans le scheduler."""
        if self.runtime and hasattr(self.runtime, "event_queue"):
            from scheduler.model.event import Event
            evt = Event(
                name=name,
                params=params or {},
                source=f"task:{self.id}",
                parent_id=self.meta.get("intent_id"),
            )
            self.runtime.event_queue.put(evt)

    # ── Ressources et locks ───────────────────────────────────────────────────

    def required_resources(self) -> list[Resource]:
        """Ressources nécessaires à l'exécution. Override dans les sous-classes."""
        return []

    def required_locks(self) -> list[Lock]:
        """Locks à acquérir avant exécution. Override dans les sous-classes."""
        return []

    @property
    def locks(self) -> list[Lock]:
        """Alias utilisé par RuntimeState.add_running()."""
        return self.required_locks()

    # ── Lifecycle hooks ───────────────────────────────────────────────────────

    def before_run(self) -> None:
        """Hook pré-exécution. Override optionnel.
        Les sous-classes DOIVENT appeler super().before_run() pour garantir
        l'exécution dans le contexte du scheduler.
        """
        if self._before_run_called:
            return
        self._before_run_called = True
        # Vérification que la tâche est bien exécutée dans le contexte du scheduler
        if self.runtime is None:
            raise RuntimeError(
                f"Tâche {self.__class__.__name__} exécutée hors contexte du scheduler. "
                f"Toutes les tâches doivent être lancées via le scheduler."
            )

    def run(self) -> Any:
        """Exécution principale. DOIT être implémenté.
        Les sous-classes peuvent appeler super().run() pour bénéficier de la validation automatique.
        """
        self.before_run()
        raise NotImplementedError(f"{self.__class__.__name__} must implement run()")

    def after_run(self) -> None:
        """Hook post-exécution. Override optionnel."""
        pass

    # ── Utilitaire : exécution de commandes système ───────────────────────────

    def run_cmd(
        self,
        cmd: str | list[str],
        check: bool = True,
        capture: bool = True,
        timeout: int | None = 120,
        sudo: bool = False,
        cwd: str | Path | None = None,
        env: dict | None = None,
        dry_run: bool = None,
    ) -> CommandResult:
        """
        Exécute une commande système avec logging complet.

        Args:
            cmd: commande (str ou list)
            check: lever une exception si returncode != 0
            capture: capturer stdout/stderr
            timeout: timeout en secondes
            sudo: préfixer avec sudo
            cwd: répertoire de travail
            env: variables d'environnement supplémentaires
            dry_run: simuler sans exécuter
        """
        if dry_run is None:
            dry_run = self.context.get("dry_run", False) or self.params.get("dry_run", False)

        if isinstance(cmd, str):
            parts = shlex.split(cmd)
        else:
            parts = list(cmd)

        if sudo:
            parts = ["sudo", "-n"] + parts

        cmd_str = shlex.join(parts)

        if dry_run:
            result = CommandResult(
                cmd=cmd_str, returncode=0,
                stdout="[dry-run]", stderr="",
                duration=0.0,
            )
            self._cmd_log.append(result)
            return result

        start = time.monotonic()
        try:
            proc = subprocess.run(
                parts,
                capture_output=capture,
                text=True,
                timeout=timeout,
                cwd=str(cwd) if cwd else None,
                env=env,
            )
            duration = time.monotonic() - start

            result = CommandResult(
                cmd=cmd_str,
                returncode=proc.returncode,
                stdout=proc.stdout or "",
                stderr=proc.stderr or "",
                duration=duration,
            )
        except subprocess.TimeoutExpired:
            result = CommandResult(
                cmd=cmd_str, returncode=-1,
                stdout="", stderr=f"Timeout après {timeout}s",
                duration=float(timeout or 0),
                success=False,
            )
        except Exception as e:
            result = CommandResult(
                cmd=cmd_str, returncode=-1,
                stdout="", stderr=str(e),
                duration=time.monotonic() - start,
                success=False,
            )

        self._cmd_log.append(result)

        if check and not result.success:
            raise RuntimeError(
                f"Commande échouée (rc={result.returncode}): {cmd_str}\n"
                f"stderr: {result.stderr}"
            )

        return result

    # ── Introspection ─────────────────────────────────────────────────────────

    @property
    def command_log(self) -> list[CommandResult]:
        return self._cmd_log

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} id={self.id}>"
