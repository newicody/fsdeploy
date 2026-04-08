"""
Vérification de l'intégration au démarrage (boot) pour le système d'initialisation détecté.
"""

import logging
import os
import subprocess
from fsdeploy.lib.scheduler.model.task import Task
from fsdeploy.lib.function.init_check import detect_init

from fsdeploy.lib.scheduler.decorators import retry_task, timeout_task

class BootIntegrationCheckTask(Task):
    def __init__(self, id, params, context):
        super().__init__(id=id, params=params, context=context)

    @retry_task(max_attempts=2, delay=0.5)
    @timeout_task(timeout_seconds=15)
    def execute(self):
        logger = self.context.logger if hasattr(self.context, 'logger') else logging.getLogger(__name__)
        logger.info("Vérification de l'intégration au démarrage")
        init_name, version = detect_init()
        # Vérifier si un service est déjà installé
        installed = False
        details = {}
        if init_name == 'systemd':
            # Vérifier si l'unité est présente et activée
            try:
                if os.path.exists('/etc/systemd/system/fsdeploy.service'):
                    installed = True
                    # Vérifier si activé
                    result = subprocess.run(['systemctl', 'is-enabled', 'fsdeploy.service'],
                                            capture_output=True, text=True)
                    details['enabled'] = result.returncode == 0
                    # Vérifier si actif
                    result_active = subprocess.run(['systemctl', 'is-active', 'fsdeploy.service'],
                                                   capture_output=True, text=True)
                    details['active'] = result_active.returncode == 0
                    # Obtenir la sortie de status pour plus de détails
                    try:
                        status_result = subprocess.run(['systemctl', 'status', '--no-pager', 'fsdeploy.service'],
                                                       capture_output=True, text=True, timeout=2)
                        details['status_output'] = status_result.stdout[:500] + (status_result.stdout[500:] and '...')
                    except subprocess.TimeoutExpired:
                        details['status_output'] = '(timeout)'
                    except Exception:
                        details['status_output'] = ''
                else:
                    installed = False
            except Exception as e:
                logger.warning("Erreur lors de la vérification systemd: %s", e)
        elif init_name == 'openrc':
            # Vérifier si le script init.d existe et est dans le runlevel
            if os.path.exists('/etc/init.d/fsdeploy'):
                installed = True
                # Vérifier si rc-update list contient fsdeploy
                try:
                    result = subprocess.run(['rc-update', 'show'], capture_output=True, text=True)
                    details['in_runlevel'] = 'fsdeploy' in result.stdout
                except Exception as e:
                    logger.warning("Erreur rc-update: %s", e)
                # Obtenir le statut rc-status
                try:
                    rc_status = subprocess.run(['rc-status'], capture_output=True, text=True)
                    details['rc_status_output'] = rc_status.stdout[:500] + (rc_status.stdout[500:] and '...')
                except Exception as e:
                    logger.warning("Erreur rc-status: %s", e)
            else:
                installed = False
        elif init_name == 'sysvinit':
            # Vérifier présence script
            if os.path.exists('/etc/init.d/fsdeploy'):
                installed = True
                # Vérifier les liens symboliques dans rc?.d (simplifié)
                try:
                    import glob
                    links = glob.glob('/etc/rc*.d/*fsdeploy*')
                    details['has_links'] = len(links) > 0
                    # Tenter d'exécuter le script avec l'argument status
                    status_result = subprocess.run(['service', 'fsdeploy', 'status'],
                                                   capture_output=True, text=True, timeout=2)
                    details['service_status_output'] = status_result.stdout[:300] + (status_result.stdout[300:] and '...')
                except Exception:
                    pass
            else:
                installed = False
        elif init_name == 'upstart':
            if os.path.exists('/etc/init/fsdeploy.conf'):
                installed = True
                details['config_present'] = True
                # Vérifier le statut avec initctl
                try:
                    initctl_status = subprocess.run(['initctl', 'status', 'fsdeploy'],
                                                    capture_output=True, text=True, timeout=2)
                    details['initctl_status_output'] = initctl_status.stdout[:300] + (initctl_status.stdout[300:] and '...')
                except Exception as e:
                    logger.warning("Erreur initctl status: %s", e)
            else:
                installed = False

        advice = ""
        if not installed:
            advice = f"Aucun service fsdeploy n'est installé pour {init_name}. Utilisez l'intent init.integration.install."
        else:
            advice = f"Service fsdeploy semble installé pour {init_name}. Vérifiez qu'il est activé pour le boot."

        result = {
            'init': init_name,
            'version': version,
            'installed': installed,
            'details': details,
            'advice': advice
        }
        logger.info("Résultat de la vérification boot: %s", result)
        # Émettre un événement via le bus global
        try:
            from fsdeploy.lib.bus import message_bus
            message_bus.emit('init.boot.checked', {
                'init': init_name,
                'installed': installed,
                'details': details,
                'advice': advice,
                'task_id': self.id
            })
        except ImportError:
            pass
        return result
