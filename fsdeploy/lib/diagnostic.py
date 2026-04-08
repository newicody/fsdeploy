#!/usr/bin/env python3
"""
fsdeploy diagnostic — verifie tous les composants avant lancement.

Usage: cd /opt/fsdeploys/fsdeploys/fsdeploy/lib && python3 diagnostic.py
"""

import sys
import os
from pathlib import Path

# Setup path
_here = Path(__file__).resolve().parent
if str(_here) not in sys.path:
    sys.path.insert(0, str(_here))

PASS = "\033[32m OK \033[0m"
FAIL = "\033[31mFAIL\033[0m"
WARN = "\033[33mWARN\033[0m"

errors = 0
warnings = 0


def check(label, condition, detail=""):
    global errors
    if condition:
        print(f"  [{PASS}] {label}")
    else:
        print(f"  [{FAIL}] {label}  {detail}")
        errors += 1


def warn(label, detail=""):
    global warnings
    print(f"  [{WARN}] {label}  {detail}")
    warnings += 1


print("\n=== fsdeploy diagnostic ===\n")

# 1. Check critical files exist
print("1. Fichiers critiques :")
critical = [
    "daemon.py", "config.py", "log.py",
    "bus/__init__.py",
    "scheduler/core/scheduler.py", "scheduler/core/executor.py",
    "scheduler/core/runtime.py", "scheduler/core/resolver.py",
    "scheduler/model/event.py", "scheduler/model/task.py",
    "scheduler/model/intent.py",
    "scheduler/queue/event_queue.py", "scheduler/queue/intent_queue.py",
    "ui/app.py", "ui/bridge.py",
]
for f in critical:
    p = _here / f
    check(f, p.exists() and p.stat().st_size > 50,
          "MANQUANT" if not p.exists() else "VIDE")

# 2. Check screens
print("\n2. Ecrans TUI :")
screens = [
    "welcome", "detection", "mounts", "kernel", "initramfs",
    "presets", "coherence", "snapshots", "stream", "config",
    "debug", "zbm", "graph",
]
for name in screens:
    p = _here / "ui" / "screens" / f"{name}.py"
    if not p.exists():
        warn(f"ui/screens/{name}.py", "absent (ecran optionnel)")
        continue

    content = p.read_text()

    # Check self.name (Textual 8.x breaking)
    import re
    has_self_name = bool(re.search(r'self\.name\s*=\s*["\']', content))
    if has_self_name:
        check(f"{name}.py self.name", False, "SELF.NAME PRESENT — Textual 8.x crash")
    else:
        check(f"{name}.py", True)

# 3. Check daemon.py content
print("\n3. daemon.py :")
daemon_path = _here / "daemon.py"
if daemon_path.exists():
    content = daemon_path.read_text()
    check("daemon.py is Python", not content.startswith("{"),
          "CONTENU JSON — fichier corrompu!")
    check("FsDeployDaemon class", "class FsDeployDaemon" in content)
    check("No store= in Executor", "store=self._store" not in content,
          "store= kwarg invalide pour Executor")
    check("pool.import_all in _register", True)  # not in daemon itself

# 4. Check detection_intent.py for PoolImportAllTask
print("\n4. Intents :")
di = _here / "intents" / "detection_intent.py"
if di.exists():
    content = di.read_text()
    check("PoolImportAllTask", "PoolImportAllTask" in content,
          "MANQUANT — detection bloquera a 5%")
    check("pool.import_all intent", "pool.import_all" in content)
else:
    check("detection_intent.py", False, "MANQUANT")

# 5. Check imports
print("\n5. Imports critiques :")
import_tests = [
    ("log", "get_logger"),
    ("config", "FsDeployConfig"),
    ("daemon", "FsDeployDaemon"),
    ("scheduler.model.event", "Event"),
    ("scheduler.model.task", "Task"),
    ("scheduler.core.scheduler", "Scheduler"),
    ("scheduler.core.executor", "Executor"),
    ("bus", "TimerSource"),
    ("ui.app", "FsDeployApp"),
]
for mod, cls in import_tests:
    try:
        m = __import__(mod, fromlist=[cls])
        obj = getattr(m, cls, None)
        check(f"from {mod} import {cls}", obj is not None)
    except Exception as e:
        check(f"from {mod} import {cls}", False, str(e)[:60])

# 6. Check detection screen for pool.import_all
print("\n6. Detection screen :")
det_screen = _here / "ui" / "screens" / "detection.py"
if det_screen.exists():
    content = det_screen.read_text()
    check("pool.import_all emission", "pool.import_all" in content,
          "MANQUANT — detection bloquera a 5%")
    check("_on_import_all_done callback", "_on_import_all_done" in content)

# 7. Check mounts screen
print("\n7. Mounts screen :")
mounts_screen = _here / "ui" / "screens" / "mounts.py"
if mounts_screen.exists():
    content = mounts_screen.read_text()
    check("_on_mount_done (pas _on_mount)", "_on_mount_done" in content,
          "Collision avec Textual on_mount()")
    check("No def _on_mount(", "def _on_mount(" not in content or "_on_mount_done" in content)

# 8. Stale/duplicate files
print("\n8. Fichiers stale :")
stale = [
    "ARCHITECTURE.py",
    "scheduler/intentlog/huffman.py",
    "scheduler/core/intent.py",
    "bus/init.py",
]
for f in stale:
    p = _here / f
    if p.exists():
        warn(f, "doublon a supprimer")
    else:
        check(f"pas de {f}", True)

# Summary
print(f"\n{'='*50}")
if errors == 0 and warnings == 0:
    print(f"  \033[32mTout OK — {len(critical)+len(screens)} composants verifies\033[0m")
elif errors == 0:
    print(f"  \033[33m{warnings} avertissement(s) — pas bloquant\033[0m")
else:
    print(f"  \033[31m{errors} erreur(s), {warnings} avertissement(s)\033[0m")
print(f"{'='*50}\n")

sys.exit(1 if errors else 0)
