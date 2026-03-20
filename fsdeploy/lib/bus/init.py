"""
fsdeploy.bus
=============
Sources d'événements pour le scheduler.

Chaque source tourne dans son propre thread et pousse des Events
dans l'EventQueue du Runtime.

Sources :
  - UdevSource      : ajout/retrait de devices
  - InotifySource   : changements fichiers (/boot, config)
  - SignalSource     : signaux POSIX
  - SocketSource     : commandes via socket Unix
  - TimerSource      : jobs périodiques (scrub, snapshots, coherence)
"""

import os
import time
import signal
import socket
import threading
import json
from pathlib import Path
from typing import Any, Callable, Optional

from scheduler.model.event import (
    Event, UdevEvent, InotifyEvent, TimerEvent, SignalEvent, CLIEvent,
)


class EventSource:
    """Classe de base pour les sources d'événements."""

    def __init__(self, event_queue):
        self.event_queue = event_queue
        self._thread: Optional[threading.Thread] = None
        self._running = False

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def _run(self) -> None:
        raise NotImplementedError

    def emit(self, event: Event) -> None:
        self.event_queue.put(event)


class TimerSource(EventSource):
    """
    Source d'événements périodiques.

    Exemple de jobs :
      - coherence_check toutes les heures
      - snapshot_auto toutes les 6h
      - scrub_check hebdomadaire
    """

    def __init__(self, event_queue):
        super().__init__(event_queue)
        self._jobs: list[dict] = []

    def add_job(self, name: str, interval: int, params: dict | None = None) -> None:
        """Ajoute un job périodique (interval en secondes)."""
        self._jobs.append({
            "name": name,
            "interval": interval,
            "params": params or {},
            "last_run": 0,
        })

    def _run(self) -> None:
        while self._running:
            now = time.time()
            for job in self._jobs:
                if now - job["last_run"] >= job["interval"]:
                    self.emit(TimerEvent(
                        job_name=job["name"],
                        params=job["params"],
                    ))
                    job["last_run"] = now
            time.sleep(1)


class InotifySource(EventSource):
    """
    Surveille des chemins via inotify (watchfiles si dispo, sinon polling).
    """

    def __init__(self, event_queue, watch_paths: list[str] | None = None):
        super().__init__(event_queue)
        self.watch_paths = watch_paths or ["/boot"]

    def _run(self) -> None:
        try:
            import watchfiles
            self._run_watchfiles()
        except ImportError:
            self._run_polling()

    def _run_watchfiles(self) -> None:
        import watchfiles
        paths = [p for p in self.watch_paths if Path(p).exists()]
        if not paths:
            return
        for changes in watchfiles.watch(*paths, stop_event=threading.Event()):
            if not self._running:
                break
            for change_type, path in changes:
                self.emit(InotifyEvent(
                    path=path,
                    change_type=change_type.name.lower(),
                ))

    def _run_polling(self) -> None:
        """Fallback polling si watchfiles n'est pas disponible."""
        state: dict[str, float] = {}
        # Init state
        for watch_path in self.watch_paths:
            p = Path(watch_path)
            if p.exists():
                for f in p.rglob("*"):
                    if f.is_file():
                        state[str(f)] = f.stat().st_mtime

        while self._running:
            for watch_path in self.watch_paths:
                p = Path(watch_path)
                if not p.exists():
                    continue
                for f in p.rglob("*"):
                    if not f.is_file():
                        continue
                    key = str(f)
                    mtime = f.stat().st_mtime
                    if key not in state:
                        self.emit(InotifyEvent(path=key, change_type="created"))
                    elif state[key] != mtime:
                        self.emit(InotifyEvent(path=key, change_type="modified"))
                    state[key] = mtime
            time.sleep(5)


class UdevSource(EventSource):
    """
    Écoute les événements udev (ajout/retrait de disques).
    Nécessite pyudev.
    """

    def _run(self) -> None:
        try:
            import pyudev
        except ImportError:
            return

        context = pyudev.Context()
        monitor = pyudev.Monitor.from_netlink(context)
        monitor.filter_by(subsystem="block")

        for device in iter(monitor.poll, None):
            if not self._running:
                break
            self.emit(UdevEvent(
                action=device.action or "unknown",
                device_path=device.device_path,
                subsystem=device.subsystem or "block",
                params={
                    "devname": device.get("DEVNAME", ""),
                    "devtype": device.get("DEVTYPE", ""),
                    "id_serial": device.get("ID_SERIAL", ""),
                },
            ))


class SocketSource(EventSource):
    """
    Écoute les commandes via socket Unix.
    Permet le contrôle par CLI externe.

    Protocole : une ligne JSON par commande.
    {"command": "snapshot", "args": {"dataset": "tank/home"}}
    """

    SOCKET_PATH = "/run/fsdeploy.sock"

    def __init__(self, event_queue, socket_path: str | None = None):
        super().__init__(event_queue)
        self.socket_path = socket_path or self.SOCKET_PATH

    def _run(self) -> None:
        sock_path = Path(self.socket_path)
        sock_path.unlink(missing_ok=True)

        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as srv:
            srv.bind(str(sock_path))
            sock_path.chmod(0o660)
            srv.listen(5)
            srv.settimeout(1.0)

            while self._running:
                try:
                    conn, _ = srv.accept()
                except socket.timeout:
                    continue
                except OSError:
                    break

                try:
                    data = conn.recv(4096).decode("utf-8").strip()
                    if data:
                        msg = json.loads(data)
                        command = msg.get("command", "")
                        args = msg.get("args", {})
                        self.emit(CLIEvent(command=command, args=args))
                        conn.sendall(b'{"status": "accepted"}\n')
                except Exception as e:
                    try:
                        conn.sendall(f'{{"error": "{e}"}}\n'.encode())
                    except Exception:
                        pass
                finally:
                    conn.close()

            sock_path.unlink(missing_ok=True)
