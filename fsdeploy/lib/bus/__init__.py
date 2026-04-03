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
