"""
Tâche de détection du système d'initialisation.
"""

import logging
from fsdeploy.lib.scheduler.model.task import Task
from fsdeploy.lib.function.init_check import detect_init, get_init_integration_advice
from fsdeploy.lib.scheduler.decorators import retry_task, timeout_task

class InitCheckTask(Task):
    def __init__(self, id, params, context):
        super().__init__(id=id, params=params, context=context)

    @retry_task(max_attempts=2, delay=0.5)
    @timeout_task(timeout_seconds=10)
    def execute(self):
        logger = self.context.logger if hasattr(self.context, 'logger') else logging.getLogger(__name__)
        logger.info("Début de la détection du système d'initialisation")
        init_name, version = detect_init()
        advice = get_init_integration_advice()
        logger.info(f"Système détecté: {init_name} version {version}")
        logger.info("Conseils d'intégration:\n%s", advice)
        # Stocker le résultat dans le contexte pour les éventuels consommateurs
        if hasattr(self.context, 'init_detection'):
            self.context.init_detection = {'name': init_name, 'version': version, 'advice': advice}
        # Émettre un événement via le bus global
        try:
            from fsdeploy.lib.bus import message_bus
            message_bus.emit('init.detected', {
                'init': init_name,
                'version': version,
                'advice': advice,
                'task_id': self.id
            })
        except ImportError:
            pass
        return {'name': init_name, 'version': version, 'advice': advice}
