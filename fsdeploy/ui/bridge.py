"""
fsdeploy.ui.bridge – Pont UI/scheduler (façade du module lib).
"""

from fsdeploy.lib.ui.bridge import SchedulerBridge as LibSchedulerBridge

__all__ = ['SchedulerBridge']

class SchedulerBridge(LibSchedulerBridge):
    """Pont pour l'UI, compatible avec add.md 24.1."""
    pass
