"""
Décorateurs pour améliorer l'exécution des tâches.
"""
import logging
import time
from functools import wraps

logger = logging.getLogger(__name__)

def retry_task(max_attempts=3, delay=1.0, exceptions=(Exception,)):
    """
    Décore une méthode `execute` pour réessayer en cas d'échec.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            last_exc = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(self, *args, **kwargs)
                except exceptions as e:
                    last_exc = e
                    logger.warning(
                        "Tentative %d/%d échouée pour %s: %s",
                        attempt, max_attempts, self.id, e
                    )
                    if attempt < max_attempts:
                        time.sleep(delay)
            raise last_exc
        return wrapper
    return decorator

def timeout_task(timeout_seconds=30):
    """
    Décore une méthode `execute` pour limiter le temps d'exécution.
    Nécessite l'utilisation de threading ou signal, ici simplification.
    Pour l'instant, seulement log un avertissement si l'exécution dépasse.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            start = time.time()
            result = func(self, *args, **kwargs)
            elapsed = time.time() - start
            if elapsed > timeout_seconds:
                logger.warning(
                    "Tâche %s a pris %.2f secondes (délai: %ds)",
                    self.id, elapsed, timeout_seconds
                )
            return result
        return wrapper
    return decorator


def timed_task(func):
    """
    Décore une méthode `execute` pour mesurer sa durée et l'enregistrer.
    """
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        start = time.time()
        result = func(self, *args, **kwargs)
        duration = time.time() - start
        # Enregistrement de la durée
        try:
            from ..metrics import record_task_duration
            record_task_duration(self.id, duration)
        except ImportError:
            pass
        return result
    return wrapper
