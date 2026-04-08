"""
Tâche d'installation des scripts d'intégration pour le système d'initialisation.
"""

import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from fsdeploy.lib.scheduler.model.task import Task
from fsdeploy.lib.function.init_check import detect_init

from fsdeploy.lib.scheduler.decorators import retry_task, timeout_task

class InstallInitIntegrationTask(Task):
    def __init__(self, id, params, context):
        super().__init__(id=id, params=params, context=context)

    @retry_task(max_attempts=3, delay=1.0)
    @timeout_task(timeout_seconds=30)
    def execute(self):
        logger = self.context.logger if hasattr(self.context, 'logger') else logging.getLogger(__name__)
        logger.info("Début de l'installation des scripts d'intégration")

        init_name, version = detect_init()
        logger.info(f"Système détecté : {init_name}")

        # Emplacement des sources contrib
        contrib_root = Path(__file__).parent.parent.parent.parent / "contrib"
        if not contrib_root.exists():
            logger.error("Répertoire contrib introuvable : %s", contrib_root)
            return {'success': False, 'error': 'contrib directory missing'}

        # Mapping des sources par système
        mapping = {
            'systemd': ('systemd/fsdeploy.service', '/etc/systemd/system/fsdeploy.service'),
            'openrc': ('openrc/fsdeploy.initd', '/etc/init.d/fsdeploy'),
            'upstart': ('upstart/fsdeploy.conf', '/etc/init/fsdeploy.conf'),
            'sysvinit': ('sysvinit/fsdeploy.init', '/etc/init.d/fsdeploy'),
        }

        if init_name not in mapping:
            logger.warning("Aucun script d'intégration disponible pour %s", init_name)
            return {'success': False, 'error': f'No integration script for {init_name}'}

        src_rel, dst = mapping[init_name]
        src = contrib_root / src_rel

        if not src.exists():
            logger.error("Fichier source introuvable : %s", src)
            return {'success': False, 'error': f'Source file {src_rel} missing'}

        # En mode simulation (par défaut) nous affichons simplement les instructions
        simulate = self.params.get('simulate', True)
        advice = (
            f"Pour installer le service {init_name} :\n"
            f"  sudo cp {src} {dst}\n"
        )
        if init_name == 'systemd':
            advice += "  sudo systemctl daemon-reload\n  sudo systemctl enable fsdeploy.service\n"
        elif init_name == 'openrc':
            advice += "  sudo rc-update add fsdeploy default\n"
        elif init_name == 'sysvinit':
            advice += "  sudo update-rc.d fsdeploy defaults\n"
        elif init_name == 'upstart':
            advice += "  sudo initctl reload-configuration\n"

        logger.info("Instructions d'installation :\n%s", advice)

        if not simulate:
            try:
                shutil.copy2(src, dst)
                logger.info("Copié %s -> %s", src, dst)
                # Commandes supplémentaires
                if init_name == 'systemd':
                    subprocess.run(['systemctl', 'daemon-reload'], check=False)
                    subprocess.run(['systemctl', 'enable', 'fsdeploy.service'], check=False)
                elif init_name == 'openrc':
                    subprocess.run(['rc-update', 'add', 'fsdeploy', 'default'], check=False)
                elif init_name == 'sysvinit':
                    subprocess.run(['update-rc.d', 'fsdeploy', 'defaults'], check=False)
                elif init_name == 'upstart':
                    subprocess.run(['initctl', 'reload-configuration'], check=False)
            except Exception as e:
                logger.exception("Échec de l'installation")
                return {'success': False, 'error': str(e)}

        # Émettre un événement d'installation via le bus global
        try:
            from fsdeploy.lib.bus import message_bus
            message_bus.emit('init.integration.install', {
                'init': init_name,
                'success': True,
                'simulated': simulate,
                'advice': advice,
                'task_id': self.id
            })
        except ImportError:
            pass

        return {
            'success': True,
            'init': init_name,
            'advice': advice,
            'simulated': simulate,
        }
