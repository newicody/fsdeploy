"""
Bus de messages global pour la communication découplée entre composants.
Permet l'abonnement et l'émission d'événements.
"""
import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# Référence vers la file d'événements du scheduler pour intégration
_event_queue_ref = None

def set_event_queue(queue):
    """Configure la file d'événements du scheduler pour recevoir les émissions du bus."""
    global _event_queue_ref
    _event_queue_ref = queue
    logger.debug("File d'événements du scheduler connectée au bus")

class MessageBus:
    _global_instance = None

    @classmethod
    def global_instance(cls) -> "MessageBus":
        """Retourne l'instance globale unique du bus."""
        if cls._global_instance is None:
            cls._global_instance = cls()
        return cls._global_instance

    def __init__(self):
        self._subscribers: Dict[str, List[Callable[[Any], None]]] = {}

    def subscribe(self, event_type: str, callback: Callable[[Any], None]) -> None:
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)
        logger.debug("Abonnement à %s", event_type)

    def unsubscribe(self, event_type: str, callback: Callable[[Any], None]) -> None:
        if event_type in self._subscribers:
            try:
                self._subscribers[event_type].remove(callback)
            except ValueError:
                pass

    def emit(self, event_type: str, data: Any = None) -> None:
        logger.debug("Émission %s : %s", event_type, data)
        if event_type in self._subscribers:
            for cb in self._subscribers[event_type]:
                try:
                    cb(data)
                except Exception as e:
                    logger.error("Callback erreur pour %s: %s", event_type, e)
        # Relay vers l'EventQueue du scheduler si configurée
        if _event_queue_ref is not None:
            try:
                # Import local pour éviter les dépendances circulaires
                from fsdeploy.lib.scheduler.model.event import Event
                event_obj = Event(
                    name=event_type,
                    params=data if isinstance(data, dict) else {"payload": data},
                    source="bus"
                )
                _event_queue_ref.push(event_obj)
            except ImportError:
                logger.warning(
                    "Impossible d'importer Event depuis scheduler.model.event"
                )
            except Exception as e:
                logger.error("Erreur lors de l'envoi à l'EventQueue: %s", e)

# Instance globale
message_bus = MessageBus()
MessageBus._global_instance = message_bus
