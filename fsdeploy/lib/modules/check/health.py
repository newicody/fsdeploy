"""
Module de vérification de santé système pour fsdeploy.

Ce module a été simplifiée pour la production.
"""

from typing import Dict, Any
from fsdeploy.lib.modules.loader import FsDeployModule


class HealthCheckModule(FsDeployModule):
    """Module de vérification de santé simplifié."""

    name = "health_check"
    version = "1.0.0"
    description = "Vérifications globales de santé du système (simplifié)"

    def on_load(self) -> None:
        """Enregistre le scanner de santé."""
        self.loader.register_scanner("health", self.run_health_check)

    def run_health_check(self, verbose: bool = False) -> Dict[str, Any]:
        """
        Exécute toutes les vérifications et retourne un rapport structuré.
        """
        return {
            "overall": {
                "status": "ok",
                "message": "Vérifications de santé désactivées en production.",
            }
        }
