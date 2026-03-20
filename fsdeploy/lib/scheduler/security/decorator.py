"""
fsdeploy.scheduler.security.decorator
======================================
Décorateur DSL pour annoter les Tasks avec des métadonnées de sécurité.

Usage :
    security = SecurityDecorator()

    @security.dataset.snapshot
    class SnapshotCreateTask(Task):
        ...

    @security.kernel.install(require_root=True)
    class KernelInstallTask(Task):
        ...

Le décorateur NE CONTIENT PAS la logique de sécurité.
Il expose : un chemin hiérarchique (path) + des options locales.
Le SecurityResolver combine ensuite : decorator metadata + config → règles effectives.
"""

from typing import Any, Callable


class SecurityNode:
    """
    Nœud dans la hiérarchie du décorateur.
    Chaque accès d'attribut crée un sous-nœud.
    L'appel terminal décore la classe.
    """

    def __init__(self, path: list[str] | None = None):
        self.path = path or []

    def __getattr__(self, name: str) -> "SecurityNode":
        """Étend le chemin : dataset → snapshot → create."""
        if name.startswith("_"):
            raise AttributeError(name)
        return SecurityNode(self.path + [name])

    def __call__(self, target=None, **options):
        """
        Deux usages :

        1. @security.dataset.snapshot        (target = la classe)
        2. @security.dataset.snapshot(opt=v)  (target = None, retourne un wrapper)
        """
        if target is not None and callable(target):
            # Usage sans parenthèses : @security.dataset.snapshot
            return self._apply(target, options)

        # Usage avec options : @security.dataset.snapshot(require_root=True)
        def wrapper(cls):
            return self._apply(cls, options)
        return wrapper

    def _apply(self, cls, options: dict) -> type:
        """Injecte les métadonnées de sécurité dans la classe."""
        cls._security_path = ".".join(self.path)
        cls._security_options = options
        return cls

    def __repr__(self) -> str:
        return f"SecurityNode({'.'.join(self.path)})"


class SecurityDecorator:
    """
    Point d'entrée du décorateur.

    Usage :
        security = SecurityDecorator()

        @security.dataset.snapshot
        class MyTask: ...
    """

    def __getattr__(self, name: str) -> SecurityNode:
        if name.startswith("_"):
            raise AttributeError(name)
        return SecurityNode([name])

    def __call__(self, **options):
        """Usage direct : @security(require_root=True)."""
        return SecurityNode([]).__call__(**options)


# Singleton global
security = SecurityDecorator()
