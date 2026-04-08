"""
fsdeploy.scheduler.core.registry
=================================
Registres globaux des types de tasks et d'executors.

Permet le dispatch dynamique et l'extensibilité.
"""

from typing import Any, Callable, Optional


TASK_REGISTRY: dict[str, type] = {}
EXECUTOR_REGISTRY: dict[str, type] = {}
INTENT_REGISTRY: dict[str, type] = {}


def register_task(name: str) -> Callable:
    """Décorateur pour enregistrer un type de task."""
    def decorator(cls):
        TASK_REGISTRY[name] = cls
        return cls
    return decorator


def register_executor(name: str) -> Callable:
    """Décorateur pour enregistrer un type d'executor."""
    def decorator(cls):
        EXECUTOR_REGISTRY[name] = cls
        return cls
    return decorator


def register_intent(event_name: str) -> Callable:
    """
    Décorateur pour enregistrer un Intent associé à un event name.
    Utilisé par IntentQueue pour le dispatch automatique.
    """
    def decorator(cls):
        INTENT_REGISTRY[event_name] = cls
        return cls
    return decorator


def get_task(name: str) -> type | None:
    return TASK_REGISTRY.get(name)


def get_executor(name: str) -> type | None:
    return EXECUTOR_REGISTRY.get(name)


def get_intent_for_event(event_name: str) -> type | None:
    return INTENT_REGISTRY.get(event_name)
