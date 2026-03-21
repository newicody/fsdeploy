"""
fsdeploy.ui.app
================
Application Textual principale.

Architecture :
  - L'App tourne dans le processus TUI (enfant du daemon)
  - Communique avec le scheduler via une référence partagée au Runtime
    OU via la socket Unix (si processus séparé)
  - Refresh périodique depuis HuffmanStore.snapshot()
  - Gère le routing entre les écrans

Modes :
  - deploy : workflow linéaire (detection → mounts → kernel → ... → reboot)
  - booted : navigation libre entre tous les écrans
  - stream : affiche StreamScreen au démarrage

Usage :
  # Depuis le daemon (même processus)
  app = FsDeployApp(runtime=runtime, store=store, config=config)
  app.run()

  # Via textual-web (navigateur)
  textual-web --app "fsdeploy.ui.app:FsDeployApp" --port 8080
"""

import os
from typing import Any, Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header
from textual.screen import Screen

from ui.screens.welcome import WelcomeScreen
from ui.bridge import SchedulerBridge


# ── Détection framebuffer ─────────────────────────────────────────────────────

IS_FRAMEBUFFER = os.environ.get("TERM") == "linux"


# ── CSS ───────────────────────────────────────────────────────────────────────

APP_CSS = """
Screen {
    background: $surface;
}

/* Header personnalisé */
Header {
    dock: top;
    height: 1;
    background: $primary;
    color: $text;
}

/* Footer avec keybindings */
Footer {
    dock: bottom;
}

/* Conteneur principal des écrans */
#main-content {
    width: 100%;
    height: 1fr;
}

/* ── Composants réutilisables ─────────────────────────────────────── */

/* Panneau d'information */
.info-panel {
    border: solid $primary;
    padding: 1 2;
    margin: 1;
    height: auto;
}

/* Panneau d'avertissement */
.warn-panel {
    border: solid $warning;
    padding: 1 2;
    margin: 1;
    height: auto;
}

/* Panneau d'erreur */
.error-panel {
    border: solid $error;
    padding: 1 2;
    margin: 1;
    height: auto;
}

/* Panneau de succès */
.success-panel {
    border: solid $success;
    padding: 1 2;
    margin: 1;
    height: auto;
}

/* Section avec titre */
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

/* Barre de statut en bas des écrans */
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

    Routing des écrans :
      Mode deploy (depuis le live) :
        Welcome → Detection → Mounts → Kernel → Initramfs
        → Presets → Coherence → ZBM → Reboot

      Mode booted (système démarré) :
        Welcome → navigation libre via sidebar/keybindings

      Mode stream :
        Welcome → StreamScreen
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
        Binding("?", "toggle_help", "Aide", show=False),
    ]

    # Écrans disponibles — chargés dynamiquement
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

        # Bridge TUI → Scheduler
        if runtime:
            self.bridge = SchedulerBridge(runtime, store)
        else:
            self.bridge = None

    # ── Compose ───────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Footer()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def on_mount(self) -> None:
        """Appelé après le montage initial de l'app."""
        # Installer les écrans lazy
        self._register_screens()

        # Écran de démarrage selon le mode
        if self.deploy_mode == "stream":
            self._push_or_switch("stream")
        else:
            self.push_screen("welcome")

        # Refresh périodique depuis le store
        if self.store:
            self.set_interval(self._refresh_interval, self._refresh_from_store)

    def _register_screens(self) -> None:
        """
        Enregistre les écrans disponibles.

        Les écrans sont importés dynamiquement pour :
          1. Ne pas casser si un module manque
          2. Permettre le chargement conditionnel (mode deploy vs booted)
        """
        # WelcomeScreen est toujours disponible (importé en haut)
        self.install_screen(WelcomeScreen, name="welcome")

        # Les autres écrans sont chargés dynamiquement
        screen_map = {
            "detection":  ("ui.screens.detection", "DetectionScreen"),
            "mounts":     ("ui.screens.mounts", "MountsScreen"),
            "kernel":     ("ui.screens.kernel", "KernelScreen"),
            "initramfs":  ("ui.screens.initramfs", "InitramfsScreen"),
            "presets":    ("ui.screens.presets", "PresetsScreen"),
            "coherence":  ("ui.screens.coherence", "CoherenceScreen"),
            "zbm":        ("ui.screens.zbm", "ZBMScreen"),
            "snapshots":  ("ui.screens.snapshots", "SnapshotsScreen"),
            "stream":     ("ui.screens.stream", "StreamScreen"),
            "config":     ("ui.screens.config", "ConfigScreen"),
            "debug":      ("ui.screens.debug", "DebugScreen"),
        }

        for name, (module_path, class_name) in screen_map.items():
            try:
                import importlib
                mod = importlib.import_module(module_path)
                screen_cls = getattr(mod, class_name)
                self.install_screen(screen_cls, name=name)
            except (ImportError, AttributeError):
                # Écran pas encore implémenté — on l'ignore
                pass

    # ── Navigation ────────────────────────────────────────────────────────────

    def action_switch_screen(self, screen_name: str) -> None:
        """Action de navigation vers un écran."""
        self._push_or_switch(screen_name)

    def _push_or_switch(self, screen_name: str) -> None:
        """
        Navigue vers un écran.

        Si l'écran est installé, on le pousse.
        Sinon, notification d'erreur.
        """
        if screen_name in self.screen_stack_names:
            # Déjà dans la pile — on pop jusqu'à lui
            while self.screen.name != screen_name and len(self.screen_stack) > 1:
                self.pop_screen()
            return

        try:
            self.push_screen(screen_name)
        except Exception:
            self.notify(
                f"Ecran '{screen_name}' pas encore disponible.",
                severity="warning",
                timeout=3,
            )

    @property
    def screen_stack_names(self) -> list[str]:
        """Noms des écrans dans la pile."""
        return [s.name or "" for s in self.screen_stack if hasattr(s, "name")]

    def navigate_next(self) -> None:
        """
        Navigation linéaire pour le mode deploy.

        Appelé par WelcomeScreen et chaque écran du workflow
        pour passer à l'étape suivante.
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
                self.notify("Workflow terminé.", severity="information")
        except ValueError:
            # Écran hors workflow — retour accueil
            self._push_or_switch("welcome")

    def navigate_back(self) -> None:
        """Retour à l'écran précédent."""
        if len(self.screen_stack) > 1:
            self.pop_screen()

    # ── Refresh depuis le store ───────────────────────────────────────────────

    def _refresh_from_store(self) -> None:
        """
        Appelé périodiquement pour mettre à jour l'UI
        depuis le HuffmanStore.snapshot() et le bridge.

        Le bridge.poll() vérifie les tickets en cours contre runtime.state
        et déclenche les callbacks enregistrés via bridge.on_result().
        """
        # Poll le bridge — vérifie les tasks terminées, fire les callbacks
        if self.bridge:
            try:
                self.bridge.poll()
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
            "o=Config x=Debug q=Quitter",
            timeout=10,
        )

    def action_quit(self) -> None:
        """Quitter proprement."""
        self.exit(return_code=0)

    # ── Utilitaires pour les écrans ───────────────────────────────────────────

    def get_config_value(self, key: str, default: Any = None) -> Any:
        """Lecture sûre d'une valeur config."""
        if self.config:
            return self.config.get(key, default)
        return default

    def set_config_value(self, key: str, value: Any) -> None:
        """Écriture sûre d'une valeur config."""
        if self.config:
            self.config.set(key, value)

    def emit_event(self, name: str, **params) -> None:
        """Émet un événement dans le scheduler via le bridge."""
        if self.bridge:
            self.bridge.submit(name, params)
        elif self.runtime and hasattr(self.runtime, "event_queue"):
            from scheduler.model.event import CLIEvent
            self.runtime.event_queue.put(CLIEvent(
                command=name,
                args=params,
            ))

    def log_to_store(self, message: str, category: str = "tui") -> None:
        """Log un message dans le HuffmanStore."""
        if self.store:
            self.store.log_event(f"tui.{category}", source="tui", message=message)
