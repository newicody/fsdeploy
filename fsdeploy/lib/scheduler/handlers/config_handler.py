"""
fsdeploy.lib.scheduler.handlers.config_handler
===============================================
Handler pour l'exécution des sections de configuration.
"""

from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


class ConfigExecuteIntent:
    """Intent pour exécuter une section de configuration."""
    
    def __init__(self, section_id: str, params: dict = None, **kwargs):
        self.section_id = section_id
        self.params = params or {}
        self.context = kwargs.get('context', {})
        self.name = f"config.execute.{section_id}"
        self.status = "pending"
    
    def set_status(self, status: str):
        """Définit le statut de l'intent."""
        self.status = status
    
    def mark_failed(self, error: Exception):
        """Marque l'intent comme échoué."""
        self.status = "failed"
        self.error = str(error)
    
    def validate(self) -> bool:
        """Valide l'intent."""
        return bool(self.section_id)
    
    def resolve(self):
        """Résout l'intent en tasks."""
        # Créer une task qui exécutera la section de configuration
        from fsdeploy.lib.scheduler.model.task import Task
        
        def execute_task(task):
            """Fonction d'exécution de la task."""
            scheduler = self.context.get("scheduler")
            if scheduler and hasattr(scheduler, 'execute_config_section'):
                result = scheduler.execute_config_section(self.section_id, self.params)
                task.result = result
                return result
            return {"success": False, "error": "Scheduler non disponible"}
        
        task = Task(
            name=f"execute_config_{self.section_id}",
            run=execute_task,
            context=self.context
        )
        return [task]


def register_config_handlers(intent_queue):
    """Enregistre les handlers pour les événements de configuration."""
    
    def handle_config_execute(event):
        """Convertit un événement config.execute en ConfigExecuteIntent."""
        from fsdeploy.lib.scheduler.model.event import Event
        
        section_id = event.params.get("section_id")
        if not section_id:
            logger.error("Événement config.execute sans section_id")
            return []
        
        # Récupérer le scheduler depuis le contexte de l'événement
        scheduler = getattr(event, 'context', {}).get('scheduler')
        
        return [ConfigExecuteIntent(
            section_id=section_id,
            params=event.params,
            context={
                "event": event,
                "scheduler": scheduler
            }
        )]
    
    # Enregistrer le handler
    if hasattr(intent_queue, 'register_handler'):
        intent_queue.register_handler("config.execute")(handle_config_execute)
    else:
        # Fallback: stocker dans un attribut
        if not hasattr(intent_queue, '_config_handlers'):
            intent_queue._config_handlers = {}
        intent_queue._config_handlers["config.execute"] = handle_config_execute
    
    return intent_queue
