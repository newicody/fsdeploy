"""
fsdeploy.scheduler.model.event
==============================
Événement dans le système fsdeploy.

Flux : event → intent → task → execution

Sources : scheduler, cli, bus (socket/dbus/udev/inotify/netlink), init system, cron.
"""

import time
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Event:
    """Événement déclenché dans le système."""

    name: str
    params: dict[str, Any] = field(default_factory=dict)
    source: Optional[str] = None
    parent_id: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    priority: int = 0  # 0=normal, négatif=urgent, positif=basse priorité

    def set_time(self, ts: float) -> None:
        self.timestamp = ts

    def to_intents(self):
        """
        Hook extensible : convertit cet événement en liste d'intents.
        Les sous-classes peuvent override pour produire des intents spécifiques.
        Par défaut retourne une liste vide — le Scheduler ignore l'event.
        """
        return []

    def __repr__(self) -> str:
        return f"<Event {self.name} src={self.source} t={self.timestamp:.0f}>"


# ─── Événements spécialisés ──────────────────────────────────────────────────

class BootRequestEvent(Event):
    """Demande de boot d'un preset."""

    def __init__(self, preset_name: str, **kwargs):
        super().__init__(
            name="boot.request",
            params={"preset": preset_name, **kwargs.pop("params", {})},
            source=kwargs.pop("source", "cli"),
            **kwargs,
        )


class UdevEvent(Event):
    """Événement udev (ajout/retrait de device)."""

    def __init__(self, action: str, device_path: str, subsystem: str = "", **kwargs):
        super().__init__(
            name=f"udev.{action}",
            params={
                "device": device_path,
                "subsystem": subsystem,
                **kwargs.pop("params", {}),
            },
            source="udev",
            **kwargs,
        )


class InotifyEvent(Event):
    """Changement fichier détecté par inotify/watchfiles."""

    def __init__(self, path: str, change_type: str = "modified", **kwargs):
        super().__init__(
            name=f"inotify.{change_type}",
            params={"path": path, **kwargs.pop("params", {})},
            source="inotify",
            **kwargs,
        )


class TimerEvent(Event):
    """Événement périodique du scheduler interne."""

    def __init__(self, job_name: str, **kwargs):
        super().__init__(
            name=f"timer.{job_name}",
            params=kwargs.pop("params", {}),
            source="scheduler",
            **kwargs,
        )


class SignalEvent(Event):
    """Signal POSIX reçu."""

    def __init__(self, signum: int, signame: str = "", **kwargs):
        super().__init__(
            name=f"signal.{signame or signum}",
            params={"signum": signum, **kwargs.pop("params", {})},
            source="signal",
            **kwargs,
        )


class CLIEvent(Event):
    """Commande CLI reçue."""

    def __init__(self, command: str, args: dict | None = None, **kwargs):
        super().__init__(
            name=f"cli.{command}",
            params={"command": command, **(args or {}), **kwargs.pop("params", {})},
            source="cli",
            **kwargs,
        )


# ─── Gestionnaire d'événements du bridge UI ─────────────────────────────────

import threading
_bridge_event_handlers_lock = threading.RLock()
_bridge_event_handlers = {}


def register_bridge_event_handler(event_name: str, handler):
    """Enregistre un handler pour un événement émis par le bridge.

    Le handler sera invoqué lorsque un `BridgeEvent` avec le nom `event_name`
    sera converti en intents via sa méthode `to_intents`. Le handler doit
    accepter un argument (l'instance de BridgeEvent) et retourner une liste
    d'intents (ou un seul intent).

    Args:
        event_name: Nom de l'événement, par exemple "detection.start".
        handler: Fonction ou appelable prenant un BridgeEvent et retournant
                 un ou plusieurs objets Intent.
    """
    with _bridge_event_handlers_lock:
        _bridge_event_handlers[event_name] = handler


class BridgeEvent(Event):
    """Événement émis par le bridge UI/scheduler.

    Sa méthode `to_intents` interroge le registre des handlers pour produire
    les intents correspondants.

    Un handler peut être enregistré via `register_bridge_event_handler` pour
    associer un nom d'événement à une fonction de conversion. Si aucun handler
    n'est trouvé, `to_intents` retourne une liste vide (l'événement est ignoré).

    Les BridgeEvents sont typiquement émis par le SchedulerBridge lorsque
    l'UI (ou un autre client) appelle `submit_event`. Ils sont placés dans
    la file d'événements du scheduler et traités lors du prochain cycle.
    """

    def to_intents(self):
        with _bridge_event_handlers_lock:
            handler = _bridge_event_handlers.get(self.name)
        if handler:
            intents = handler(self)
            if isinstance(intents, list):
                return intents
            else:
                return [intents]
        # Aucun handler → retourner une liste vide, l'événement sera ignoré.
        return []
