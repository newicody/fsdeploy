"""
Package de gestion des modules fsdeploy.
Permet d'étendre les fonctionnalités via des plugins.
"""

from .loader import ModuleLoader
from .registry import ModuleRegistry

__all__ = ["ModuleLoader", "ModuleRegistry"]
