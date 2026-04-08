"""
fsdeploy.ui.screens
====================
Écrans de la TUI.

Écrans disponibles (11 + GraphView) :
  h: WelcomeScreen     → Mode deploy/gestion
  d: DetectionScreen   → Pools/datasets/partitions + confiance
  m: MountsScreen      → Validation/modification montages
  k: KernelScreen      → Sélection/compilation kernel
  i: InitramfsScreen   → Type zbm/minimal/stream
  p: PresetsScreen     → CRUD presets JSON
  c: CoherenceScreen   → Vérification complète système
  s: SnapshotsScreen   → Gestion snapshots
  y: StreamScreen      → Config YouTube
  o: ConfigScreen      → Éditeur fsdeploy.conf
  x: DebugScreen       → Logs/tasks/state
  g: GraphViewScreen   → Visualisation scheduler temps réel
"""

# Import conditionnel pour éviter les erreurs si un module manque
try:
    from ui.screens.welcome import WelcomeScreen
except ImportError:
    WelcomeScreen = None

try:
    from ui.screens.detection import DetectionScreen
except ImportError:
    DetectionScreen = None

try:
    from ui.screens.mounts import MountsScreen
except ImportError:
    MountsScreen = None

try:
    from ui.screens.kernel import KernelScreen
except ImportError:
    KernelScreen = None

try:
    from ui.screens.initramfs import InitramfsScreen
except ImportError:
    InitramfsScreen = None

try:
    from ui.screens.presets import PresetsScreen
except ImportError:
    PresetsScreen = None

try:
    from ui.screens.coherence import CoherenceScreen
except ImportError:
    CoherenceScreen = None

try:
    from ui.screens.snapshots import SnapshotsScreen
except ImportError:
    SnapshotsScreen = None

try:
    from ui.screens.stream import StreamScreen
except ImportError:
    StreamScreen = None

try:
    from ui.screens.config import ConfigScreen
except ImportError:
    ConfigScreen = None

try:
    from ui.screens.debug import DebugScreen
except ImportError:
    DebugScreen = None

try:
    from ui.screens.graph import GraphViewScreen
except ImportError:
    GraphViewScreen = None

__all__ = [
    "WelcomeScreen",
    "DetectionScreen",
    "MountsScreen",
    "KernelScreen",
    "InitramfsScreen",
    "PresetsScreen",
    "CoherenceScreen",
    "SnapshotsScreen",
    "StreamScreen",
    "ConfigScreen",
    "DebugScreen",
    "GraphViewScreen",
]
