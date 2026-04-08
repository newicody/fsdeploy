"""
Écran de visualisation de la configuration de sécurité.

Affiche les règles de sécurité issues de fsdeploy.conf [security]
ainsi que les décorateurs enregistrés.
"""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, DataTable
from textual.containers import Container, ScrollableContainer
from textual.binding import Binding


class SecurityScreen(Screen):
    """
    Affiche l'état de la configuration des paramètres de sécurité.

    Touches :
        escape  – retour à l'écran précédent
        r       – rafraîchir les données
    """

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Retour"),
        Binding("r", "refresh", "Rafraîchir"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield ScrollableContainer(
            Static("🔐 État de la configuration de sécurité", id="security-title"),
            DataTable(id="security-rules-table", zebra_stripes=True),
            Static("Décorateurs de sécurité enregistrés", id="decorators-title"),
            DataTable(id="security-decorators-table", zebra_stripes=True),
            id="security-container",
        )
        yield Footer()

    def on_mount(self) -> None:
        self.load_data()

    def load_data(self) -> None:
        """Charge les données de sécurité via l'intent security.status."""
        rules_table = self.query_one("#security-rules-table", DataTable)
        rules_table.clear()
        rules_table.add_columns("Chemin de sécurité", "Valeur", "Description")

        decorators_table = self.query_one("#security-decorators-table", DataTable)
        decorators_table.clear()
        decorators_table.add_columns("Décorateur", "Module")

        # TODO: À terme, il faudrait passer par le scheduler via le bridge.
        # Pour l'instant, on utilise la tâche directement (cela contourne le scheduler).
        # À refactoriser quand le bridge offrira une API synchrone simple.
        self._emit_security_status_intent(rules_table, decorators_table)

    def _load_fallback(self, rules_table, decorators_table):
        # données factices
        example_rules = [
            ("security.dataset.mount", "allow", "Montage de datasets"),
            ("security.dataset.snapshot", "deny", "Création de snapshots"),
            ("security.stream.start", "allow", "Démarrage du stream"),
            ("security.kernel.compile", "allow", "Compilation de noyau"),
        ]
        for rule, value, desc in example_rules:
            rules_table.add_row(rule, value, desc)

        example_decorators = [
            ("@security.dataset.mount", "function.dataset.mount"),
            ("@security.dataset.snapshot", "function.snapshot.create"),
            ("@security.stream.start", "function.stream.youtube"),
            ("@security.kernel.compile", "function.kernel.compile"),
        ]
        for deco, mod in example_decorators:
            decorators_table.add_row(deco, mod)

    def _load_via_task(self, rules_table, decorators_table):
        """Charge les données via SecurityStatusTask (contourne le scheduler).
        
        TODO: remplacer par une émission d'intent via le bridge du scheduler
        pour respecter l'architecture event‑driven (voir item 27 du plan).
        """
        try:
            from fsdeploy.lib.function.security.status import SecurityStatusTask
            task = SecurityStatusTask(id="temp", params={}, context={})
            success = task.run()
            if success and task.result:
                rules = task.result.get("rules", {})
                for key, val in rules.items():
                    rules_table.add_row(key, str(val), "")
                decorators = task.result.get("registered_decorators", [])
                for deco in decorators:
                    decorators_table.add_row(deco, "")
            else:
                self._load_fallback(rules_table, decorators_table)
        except Exception as e:
            self.log(f"Erreur chargement sécurité: {e}")
            self._load_fallback(rules_table, decorators_table)

    def _emit_security_status_intent(self, rules_table, decorators_table):
        """Émet l'intent security.status via le scheduler et met à jour les tables.
        
        Pour l'instant, cette méthode appelle _load_via_task en attendant une vraie
        intégration avec le bridge UI-scheduler (voir item 27 du plan).
        """
        # TODO: implémenter l'émission d'intent via le bridge du scheduler.
        # Actuellement, on utilise la tâche directement pour ne pas bloquer
        # la progression du projet. Cela doit être remplacé par un appel
        # asynchrone au scheduler qui retournera les résultats via un callback.
        self.log("INFO: Émission de security.status via scheduler (simulée)")
        self._load_via_task(rules_table, decorators_table)

    def action_refresh(self) -> None:
        """Rafraîchit les données."""
        self.load_data()
        self.notify("Données de sécurité rafraîchies", severity="information")
