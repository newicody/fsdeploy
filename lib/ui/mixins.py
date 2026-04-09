"""
Mixin pour uniformiser la connexion au bridge (MessageBus) dans les écrans TUI.
"""

from typing import Any, Optional

class BridgeScreenMixin:
    """
    Mixin à hériter par tout écran qui a besoin d'émettre des événements ou de
    rafraîchir son interface depuis le store du scheduler.

    L'écran doit définir `self.bridge` (une instance de MessageBus) avant d'utiliser
    les méthodes, typiquement via `self.set_bridge(bridge)`.
    """

    bridge: Any = None

    def emit(self, event_name: str, **params) -> str:
        """
        Émet un événement vers le bridge.

        :param event_name: nom de l'événement (ex: "screen.mounts.updated")
        :param params: paramètres supplémentaires passés à l'événement
        :return: l'identifiant de l'intent généré (chaîne)
        """
        if self.bridge is None:
            raise RuntimeError(
                "Bridge non défini. Assurez-vous que self.bridge est initialisé."
            )
        # On suppose que le bridge possède une méthode `emit`
        return self.bridge.emit(event_name, **params)

    async def _refresh_from_store(self, store_key: Optional[str] = None) -> None:
        """
        Rafraîchit l'interface à partir du store partagé.

        Cette méthode doit être surchargée par les écrans pour refléter les données
        mises à jour.

        :param store_key: clé facultative identifiant le store à rafraîchir
        """
        # Par défaut, ne rien faire ; les sous-classes implémenteront la logique.
        pass

    def set_bridge(self, bridge: Any) -> None:
        """
        Injecte le bridge dans le mixin.
        À appeler typiquement dans on_mount() de l'écran.
        """
        self.bridge = bridge
