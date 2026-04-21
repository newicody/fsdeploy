"""
fsdeploy.ui.app – Application Textual principale.
"""

from fsdeploy.lib.ui.bridge import SchedulerBridge

class FsDeployApp:
    """Application TUI principale."""
    
    def __init__(self, runtime=None, store=None):
        self.runtime = runtime
        self.store = store
        self.bridge = SchedulerBridge(runtime=self.runtime, store=self.store)
