"""
fsdeploy.ui.app
=================
Application Textual principale fsdeploy.
Mise à jour conforme à add.md 24.1.

Compatible : Textual >=8.2.1 / Rich >=14.3.3 / Python >=3.9

# NOTE: Migration des écrans selon add.md 24.1.
# Les appels self.app.bus.emit doivent être remplacés par self.bridge.emit.

Routing des ecrans :
  Mode deploy (depuis le live) :
    Welcome -> Detection -> Mounts -> Kernel -> Initramfs
    -> Presets -> Coherence -> ZBM -> Reboot

  Mode booted (systeme demarre) :
    Welcome -> navigation libre via sidebar/keybindings

  Mode stream :
    Welcome -> StreamScreen
"""

import os
import sys
from typing import Any, Optional, Callable

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Header, Footer

# ── Detection framebuffer ─────────────────────────────────────────────────────
IS_FRAMEBUFFER = os.environ.get("TERM") == "linux"

# ── Import dynamique des ecrans ──────────────────────────────────────────────
# Les ecrans sont importes a la demande pour eviter les erreurs de modules
# manquants et pour supporter le hot-reload.

from fsdeploy.lib.ui.screens.welcome import WelcomeScreen


# ── CSS ──────────────────────────────────────────────────────────────────────

APP_CSS = """
/* ── Base ──────────────────────────────────────────────────────────────── */

Screen {
    overflow-y: auto;
}

/* ── Panels informatifs ──────────────────────────────────────────────── */

.info-panel {
    padding: 1 2;
    border: solid $accent;
    margin: 1 0;
    height: auto;
}

.warn-panel {
    padding: 1 2;
    border: solid $warning;
    margin: 1 0;
    height: auto;
}

.error-panel {
    padding: 1 2;
    border: solid $error;
    margin: 1 0;
    height: auto;
}

.success-panel {
    padding: 1 2;
    border: solid $success;
    margin: 1 0;
    height: auto;
}

/* ── Section generique ─────────────────────────────────────────────── */

.section {
    margin: 1 0;
    padding: 1 2;
    border: solid $primary-background;
    height: auto;
}

.section-title {
    text-style: bold;
    margin-bottom: 1;
}

/* Bouton primaire */
.btn-primary {
    margin: 1 2;
}

/* Log de commandes */
.command-log {
    height: 1fr;
    border: solid $primary-background;
    padding: 0 1;
    overflow-y: auto;
}

/* Barre de statut en bas des ecrans */
.status-bar {
    dock: bottom;
    height: 1;
    background: $primary-background;
    color: $text-muted;
    padding: 0 2;
}

/* DataTable style */
DataTable {
    height: 1fr;
}

/* ── Framebuffer : remplacer les box-drawing si TERM=linux ─────── */
"""

# En framebuffer, les bordures fancy ne s'affichent pas bien
FRAMEBUFFER_CSS = """
.info-panel, .warn-panel, .error-panel, .success-panel, .section {
    border: ascii $primary;
}
.command-log {
    border: ascii $primary-background;
}
"""


# ── Application principale ────────────────────────────────────────────────────

class FsDeployApp(App):
    """
    Application Textual fsdeploy.

    Routing des ecrans :
      Mode deploy (depuis le live) :
        Welcome -> Detection -> Mounts -> Kernel -> Initramfs
        -> Presets -> Coherence -> ZBM -> Reboot

      Mode booted (systeme demarre) :
        Welcome -> navigation libre via sidebar/keybindings

      Mode stream :
        Welcome -> StreamScreen
    """

    TITLE = "fsdeploy"
    SUB_TITLE = "ZFS Boot Manager"

    CSS = APP_CSS + (FRAMEBUFFER_CSS if IS_FRAMEBUFFER else "")

    BINDINGS = [
        Binding("q", "quit", "Quitter", show=True, priority=True),
        Binding("d", "switch_screen('detection')", "Detection", show=True),
        Binding("m", "switch_screen('mounts')", "Montages", show=True),
        Binding("k", "switch_screen('kernel')", "Kernel", show=True),
        Binding("i", "switch_screen('initramfs')", "Initramfs", show=True),
        Binding("p", "switch_screen('presets')", "Presets", show=True),
        Binding("c", "switch_screen('coherence')", "Coherence", show=True),
        Binding("s", "switch_screen('snapshots')", "Snapshots", show=True),
        Binding("y", "switch_screen('stream')", "Stream", show=True),
        Binding("o", "switch_screen('config')", "Config", show=True),
        Binding("x", "switch_screen('debug')", "Debug", show=True),
        Binding("h", "switch_screen('welcome')", "Accueil", show=True),
        Binding("g", "push_screen_graph", "GraphView", show=True),
        Binding("M", "switch_screen('modules')", "Modules", show=True),
        Binding("?", "toggle_help", "Aide", show=False),
    ]

    # Ecrans disponibles — charges dynamiquement
    SCREENS = {
        "welcome": WelcomeScreen,
    }

    def __init__(
        self,
        runtime=None,
        store=None,
        config=None,
        mode: str = "deploy",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.runtime = runtime     # scheduler.core.runtime.Runtime
        self.store = store         # intentlog.codec.HuffmanStore
        self.config = config       # config.FsDeployConfig
        self.deploy_mode = mode    # deploy | booted | stream
        self._refresh_interval = 2.0  # secondes entre les refresh TUI
        self.sudo_requests = {}    # stocke les demandes sudo en attente

        # Bridge TUI -> Scheduler
        from .bridge import SchedulerBridge
        # Utiliser l'instance singleton pour garantir la cohérence entre tous les écrans
        self.bridge = SchedulerBridge.default(runtime=self.runtime, store=self.store)
        self.bridge.set_app(self)   # <-- AJOUTER CETTE LIGNE

    # ── Compose ───────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Footer()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def on_mount(self) -> None:
        """Appele apres le montage initial de l'app."""
        # Installer les ecrans lazy
        self._register_screens()

        # Ecran de demarrage selon le mode
        if self.deploy_mode == "stream":
            self._push_or_switch("stream")
        else:
            self.push_screen("welcome")

        # Connecter le scheduler au bridge global pour les logs
        self._connect_scheduler_to_bridge()

        # Refresh periodique depuis le store
        if self.store:
            self.set_interval(self._refresh_interval, self._refresh_from_store)

    def _register_screens(self) -> None:
        """
        Enregistre les ecrans disponibles.

        Les ecrans sont importes dynamiquement pour :
          1. Ne pas casser si un module manque
          2. Supporter le hot-reload via textual-dev
          3. Reduire le temps de demarrage
        """
        screen_map = {
            "detection": ("fsdeploy.lib.ui.screens.detection", "DetectionScreen"),
            "mounts": ("fsdeploy.lib.ui.screens.mounts", "MountsScreen"),
            "kernel": ("fsdeploy.lib.ui.screens.kernel", "KernelScreen"),
            "initramfs": ("fsdeploy.lib.ui.screens.initramfs", "InitramfsScreen"),
            "presets": ("fsdeploy.lib.ui.screens.presets", "PresetsScreen"),
            "coherence": ("fsdeploy.lib.ui.screens.coherence", "CoherenceScreen"),
            "snapshots": ("fsdeploy.lib.ui.screens.snapshots", "SnapshotsScreen"),
            "stream": ("fsdeploy.lib.ui.screens.stream", "StreamScreen"),
            "config": ("fsdeploy.lib.ui.screens.config", "ConfigScreen"),
            "debug": ("fsdeploy.lib.ui.screens.debug", "DebugScreen"),
            "zbm": ("fsdeploy.lib.ui.screens.zbm", "ZBMScreen"),
            "graph": ("fsdeploy.lib.ui.screens.graph", "GraphScreen"),
            "crosscompile": ("fsdeploy.lib.ui.screens.crosscompile", "CrossCompileScreen"),
            "multiarch": ("fsdeploy.lib.ui.screens.multiarch", "MultiArchScreen"),
            "security": ("fsdeploy.lib.ui.screens.security", "SecurityScreen"),
            "intentlog": ("fsdeploy.lib.ui.screens.intentlog", "IntentLogScreen"),
            "metrics": ("fsdeploy.lib.ui.screens.metrics", "MetricsScreen"),
            "modules": ("fsdeploy.lib.ui.screens.module_registry", "ModuleRegistryScreen"),
            "config_snapshot": ("fsdeploy.lib.ui.screens.config_snapshot", "ConfigSnapshotScreen"),
            "error_log": ("fsdeploy.lib.ui.screens.error_log", "ErrorLogScreen"),
            "history": ("fsdeploy.lib.ui.screens.history", "HistoryScreen"),
            "monitoring": ("fsdeploy.lib.ui.screens.monitoring", "MonitoringScreen"),
        }

        for name, (module_path, class_name) in screen_map.items():
            try:
                import importlib
                mod = importlib.import_module(module_path)
                cls = getattr(mod, class_name)
                self.install_screen(cls, name=name)
            except (ImportError, AttributeError) as exc:
                # Silencieux — l'ecran sera indisponible
                pass

    # ── Navigation ────────────────────────────────────────────────────────────

    def action_switch_screen(self, screen_name: str) -> None:
        """Bascule vers un ecran par nom."""
        self._push_or_switch(screen_name)

    def action_push_screen_graph(self) -> None:
        """Ouvre GraphView en overlay."""
        self._push_or_switch("graph")

    def _push_or_switch(self, name: str) -> None:
        """Navigue vers un ecran, push ou switch selon le contexte."""
        try:
            if name in [s.name for s in self.screen_stack if hasattr(s, "name")]:
                # L'ecran est deja dans la pile — switch
                self.switch_screen(name)
            else:
                self.push_screen(name)
        except Exception as exc:
            self.notify(
                f"Ecran '{name}' non disponible : {exc}",
                severity="warning",
                timeout=3,
            )

    @property
    def screen_stack_names(self) -> list[str]:
        """Noms des ecrans dans la pile."""
        return [s.name or "" for s in self.screen_stack if hasattr(s, "name")]

    def navigate_next(self) -> None:
        """
        Navigation lineaire pour le mode deploy.

        Appele par WelcomeScreen et chaque ecran du workflow
        pour passer a l'etape suivante.
        """
        deploy_order = [
            "welcome", "detection", "mounts", "kernel", "initramfs",
            "presets", "coherence", "zbm",
        ]

        current = self.screen.name or "welcome"
        try:
            idx = deploy_order.index(current)
            if idx + 1 < len(deploy_order):
                next_screen = deploy_order[idx + 1]
                self._push_or_switch(next_screen)
            else:
                self.notify("Workflow termine.", severity="information")
        except ValueError:
            # Ecran hors workflow — retour accueil
            self._push_or_switch("welcome")

    def navigate_back(self) -> None:
        """Retour a l'ecran precedent."""
        if len(self.screen_stack) > 1:
            self.pop_screen()

    # ── Refresh depuis le store ───────────────────────────────────────────────

    def _refresh_from_store(self) -> None:
        """
        Appele periodiquement pour mettre a jour l'UI
        depuis le HuffmanStore.snapshot() et le bridge.

        Le bridge.poll() verifie les tickets en cours contre runtime.state
        et declenche les callbacks enregistres via bridge.on_result().
        """
        # Poll le bridge — verifie les tasks terminees, fire les callbacks
        if self.bridge:
            try:
                just_done = self.bridge.poll()
                if isinstance(just_done, list):
                    for ticket in just_done:
                        if hasattr(ticket, 'status'):
                            if ticket.status == "failed":
                                self.notify(
                                    f"Echec: {getattr(ticket, 'event_name', 'tâche')} — {getattr(ticket, 'error', '')}",
                                    severity="error", timeout=5,
                                )
                            elif ticket.status == "completed":
                                self.notify(
                                    f"OK: {getattr(ticket, 'event_name', 'tâche')}",
                                    severity="information", timeout=3,
                                )
            except Exception:
                pass

        # Refresh depuis le store
        if not self.store:
            return

        try:
            snapshot = self.store.snapshot()
            screen = self.screen
            if hasattr(screen, "update_from_snapshot"):
                screen.update_from_snapshot(snapshot)
        except Exception:
            pass

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_toggle_help(self) -> None:
        """Affiche/masque l'aide."""
        self.notify(
            "Raccourcis : h=Accueil d=Detection m=Montages k=Kernel "
            "i=Initramfs p=Presets c=Coherence s=Snapshots y=Stream "
            "o=Config x=Debug g=GraphView q=Quitter",
            timeout=10,
        )

    def action_quit(self) -> None:
        """Quitter proprement."""
        self.exit(return_code=0)

    # ── Utilitaires pour les ecrans ───────────────────────────────────────────

    def get_config_value(self, key: str, default: Any = None) -> Any:
        """Lecture sure d'une valeur config."""
        if self.config:
            return self.config.get(key, default)
        return default

    def set_config_value(self, key: str, value: Any) -> None:
        """Ecriture sure d'une valeur config."""
        if self.config:
            self.config.set(key, value)

    def request_sudo_password(self, section_id: str, action: str = "", 
                             callback: Optional[Callable] = None) -> None:
        """
        Affiche un modal pour demander le mot de passe sudo.
        
        Args:
            section_id: ID de la section de configuration
            action: Description de l'action
            callback: Fonction à appeler avec le mot de passe
        """
        from .screens.sudo_modal import SudoModal
        
        def handle_password(password: str) -> None:
            """Gère la réponse du modal."""
            if callback:
                if password:
                    # Le mot de passe a été fourni
                    callback(password)
                else:
                    # L'utilisateur a annulé
                    callback(None)
        
        # Afficher le modal
        self.push_screen(
            SudoModal(section_id=section_id, action=action),
            handle_password
        )

    # ── Connexion du scheduler au bridge ──────────────────────────────────────

    def _connect_scheduler_to_bridge(self) -> None:
        """Connecte le scheduler au bridge global pour l'émission de logs."""
        try:
            # Obtenir le scheduler global
            from fsdeploy.lib.scheduler.core.scheduler import Scheduler
            scheduler = Scheduler.global_instance()
            
            # Obtenir le bridge global
            from fsdeploy.lib.scheduler.bridge import SchedulerBridge as GlobalSchedulerBridge
            global_bridge = GlobalSchedulerBridge.default()
            
            # Connecter le scheduler au bridge global
            if hasattr(scheduler, 'set_bridge'):
                scheduler.set_bridge(global_bridge)
                self.log(f"Scheduler connecté au bridge global pour les logs")
            else:
                self.log(f"Le scheduler n'a pas de méthode set_bridge")
                
        except ImportError as e:
            self.log(f"Impossible d'importer les modules nécessaires: {e}")
        except Exception as e:
            self.log(f"Erreur lors de la connexion du scheduler: {e}")
    
    def log(self, message: str) -> None:
        """Méthode utilitaire pour journaliser."""
        import logging
        logging.info(f"[FsDeployApp] {message}")
