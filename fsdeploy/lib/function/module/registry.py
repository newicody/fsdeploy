"""
Module de registre distant (désactivé).
Le système de modules dynamiques a été jugé non nécessaire pour le moment.
"""

__all__ = ["ModuleRegistry"]


class ModuleRegistry:
    """Stub pour le registre de modules."""

    def list_remote(self):
        """Retourne une liste fictive de modules."""
        return [
            {"name": "example-module", "version": "1.0", "description": "Module d'exemple"},
            {"name": "test-tool", "version": "2.3", "description": "Outil de test"},
        ]

    def is_installed(self, name: str) -> bool:
        """Simule la vérification d'installation."""
        return False

    def install(self, name: str) -> None:
        """Simule l'installation."""
        pass
