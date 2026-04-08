"""
Tâche de statut de sécurité.

Récupère les règles de sécurité définies dans fsdeploy.conf [security]
ainsi que l'état des décorateurs de sécurité enregistrés.
"""
from ..task import Task
import configobj
import os


class SecurityStatusTask(Task):
    """Fournit un rapport sur la configuration de sécurité."""

    def before_run(self) -> None:
        self.log("[SecurityStatusTask] Collecte des règles de sécurité")

    def run(self):
        config_path = self.params.get(
            "config_path",
            "/etc/fsdeploy/config.fsd"
        )
        if not os.path.exists(config_path):
            self.error = f"Fichier de configuration introuvable : {config_path}"
            return False

        try:
            cfg = configobj.ConfigObj(config_path, encoding="utf-8")
            security_section = cfg.get("security", {})
            # Conversion en dict plat pour l'affichage
            rules = {}
            for key, val in security_section.items():
                rules[key] = val

            # Récupération des décorateurs de sécurité enregistrés
            # (via le registre interne, optionnel)
            registered_decorators = []
            try:
                from scheduler.security.decorator import _SECURITY_REGISTRY
                registered_decorators = list(_SECURITY_REGISTRY.keys())
            except ImportError:
                registered_decorators = []

            self.result = {
                "rules": rules,
                "registered_decorators": registered_decorators,
                "config_path": config_path,
                "count": len(rules),
            }
            return True
        except Exception as e:
            self.error = f"Erreur lors de la lecture de la configuration : {e}"
            return False

    def after_run(self, result) -> None:
        if self.error:
            self.log(f"[SecurityStatusTask] Échec : {self.error}")
        else:
            self.log(
                f"[SecurityStatusTask] Terminé — {self.result['count']} règles trouvées"
            )
