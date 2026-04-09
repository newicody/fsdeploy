"""
Tâches d'installation et de configuration du système d'initialisation.
"""
import shutil
import os
import subprocess
from pathlib import Path
from ..scheduler.model.task import Task

class InitInstallTask(Task):
    """
    Installation des scripts d'intégration pour le système d'initialisation détecté.
    """
    def run(self):
        root = self.params.get('root')
        root_path = Path(root) if root else Path()
        # Détection du système d'initialisation
        init_system, init_version = self._detect_init(root)
        self.log_event("init.install.start",
                       init_system=init_system,
                       init_version=init_version,
                       root=str(root) if root else None)
        # Copier les scripts appropriés depuis contrib/
        contrib_dir = Path(__file__).parent.parent.parent / "contrib"
        target_dir = root_path / "etc/fsdeploy"
        target_dir.mkdir(parents=True, exist_ok=True)
        # Installation selon le système
        if init_system == "systemd":
            service_source = contrib_dir / "systemd" / "fsdeploy.service"
            if not service_source.exists():
                self.log_event("init.install.source_missing",
                               path=str(service_source))
                return {"init_system": init_system, "status": "failed", "reason": "source_missing"}
            enable = self.params.get('enable', True)
            # Copier dans /etc/systemd/system/ pour priorité sur le système
            systemd_dir = root_path / "etc/systemd/system"
            systemd_dir.mkdir(parents=True, exist_ok=True)
            target_service = systemd_dir / "fsdeploy.service"
            shutil.copy(service_source, target_service)
            self.log_event("init.install.service_copied",
                           service=str(target_service))
            # Recharger le démon systemd, avec --root si nécessaire
            cmd_daemon_reload = ['systemctl']
            if root:
                cmd_daemon_reload.extend(['--root', root])
            cmd_daemon_reload.append('daemon-reload')
            try:
                subprocess.run(cmd_daemon_reload, check=True, capture_output=True)
                self.log_event("init.install.daemon_reloaded")
            except subprocess.CalledProcessError as e:
                self.log_event("init.install.daemon_reload_failed",
                               error=str(e.stderr))
                # On continue malgré l'erreur
            if enable:
                cmd_enable = ['systemctl']
                if root:
                    cmd_enable.extend(['--root', root])
                cmd_enable.extend(['enable', 'fsdeploy.service'])
                try:
                    subprocess.run(cmd_enable, check=True, capture_output=True)
                    self.log_event("init.install.service_enabled")
                except subprocess.CalledProcessError as e:
                    self.log_event("init.install.enable_failed",
                                   error=str(e.stderr))
                    # On note l'échec mais on continue
        elif init_system == "openrc":
            openrc_source = contrib_dir / "openrc" / "fsdeploy.init"
            if not openrc_source.exists():
                self.log_event("init.install.source_missing",
                               path=str(openrc_source))
                return {"init_system": init_system, "status": "failed", "reason": "source_missing"}
            # Copier dans /etc/init.d/ pour OpenRC
            initd_dir = root_path / "etc/init.d"
            initd_dir.mkdir(parents=True, exist_ok=True)
            target_init = initd_dir / "fsdeploy"
            shutil.copy(openrc_source, target_init)
            os.chmod(target_init, 0o755)
            self.log_event("init.install.openrc_copied")
            enable = self.params.get('enable', True)
            if enable:
                # Si root est fourni, utiliser l'option -u (chroot) de rc-update si disponible
                # Sinon, exécuter normalement
                cmd = ['rc-update']
                if root:
                    # Certaines versions d'openrc acceptent '-u <chemin>' pour chroot
                    cmd.extend(['-u', root])
                cmd.extend(['add', 'fsdeploy', 'default'])
                try:
                    subprocess.run(cmd, check=True, capture_output=True)
                    self.log_event("init.install.openrc_enabled")
                except subprocess.CalledProcessError as e:
                    self.log_event("init.install.openrc_enable_failed",
                                   error=str(e.stderr))
        elif init_system == "upstart":
            upstart_source = contrib_dir / "upstart" / "fsdeploy.conf"
            if not upstart_source.exists():
                self.log_event("init.install.source_missing",
                               path=str(upstart_source))
                return {"init_system": init_system, "status": "failed", "reason": "source_missing"}
            # Copier dans /etc/init/
            init_dir = root_path / "etc/init"
            init_dir.mkdir(parents=True, exist_ok=True)
            target_conf = init_dir / "fsdeploy.conf"
            shutil.copy(upstart_source, target_conf)
            self.log_event("init.install.upstart_copied")
            enable = self.params.get('enable', True)
            if enable:
                try:
                    if root:
                        subprocess.run(['chroot', root, 'initctl', 'reload-configuration'],
                                       check=True, capture_output=True)
                    else:
                        subprocess.run(['initctl', 'reload-configuration'],
                                       check=True, capture_output=True)
                    self.log_event("init.install.upstart_reloaded")
                    # Démarrer le service
                    if root:
                        subprocess.run(['chroot', root, 'initctl', 'start', 'fsdeploy'],
                                       check=True, capture_output=True)
                    else:
                        subprocess.run(['initctl', 'start', 'fsdeploy'],
                                       check=True, capture_output=True)
                    self.log_event("init.install.upstart_started")
                except subprocess.CalledProcessError as e:
                    self.log_event("init.install.upstart_start_failed",
                                   error=str(e.stderr))
        elif init_system == "sysvinit":
            sysvinit_source = contrib_dir / "sysvinit" / "fsdeploy.init"
            if not sysvinit_source.exists():
                self.log_event("init.install.source_missing",
                               path=str(sysvinit_source))
                return {"init_system": init_system, "status": "failed", "reason": "source_missing"}
            # Copier dans /etc/init.d/
            initd_dir = root_path / "etc/init.d"
            initd_dir.mkdir(parents=True, exist_ok=True)
            target_init = initd_dir / "fsdeploy"
            shutil.copy(sysvinit_source, target_init)
            os.chmod(target_init, 0o755)
            self.log_event("init.install.sysvinit_copied")
            enable = self.params.get('enable', True)
            if enable:
                # Essayer update-rc.d (Debian) ou chkconfig (RHEL)
                try:
                    if root:
                        subprocess.run(['chroot', root, 'update-rc.d', 'fsdeploy', 'defaults'],
                                       check=True, capture_output=True)
                    else:
                        subprocess.run(['update-rc.d', 'fsdeploy', 'defaults'],
                                       check=True, capture_output=True)
                    self.log_event("init.install.sysvinit_enabled")
                except (subprocess.CalledProcessError, FileNotFoundError):
                    try:
                        if root:
                            subprocess.run(['chroot', root, 'chkconfig', '--add', 'fsdeploy'],
                                           check=True, capture_output=True)
                        else:
                            subprocess.run(['chkconfig', '--add', 'fsdeploy'],
                                           check=True, capture_output=True)
                        self.log_event("init.install.sysvinit_enabled_chkconfig")
                    except (subprocess.CalledProcessError, FileNotFoundError) as e:
                        self.log_event("init.install.sysvinit_enable_failed",
                                       error=str(e))
        # Autres actions possibles
        self.log_event("init.install.finish")
        return {"init_system": init_system, "status": "installed"}

    def _detect_init(self, root=None):
        """
        Détection simplifiée, utilise la fonction existante depuis init_check.
        Si root est fourni, les chemins de détection sont préfixés par root.
        """
        prefix = Path(root) if root else Path()
        # Si pas de root, on peut utiliser la fonction existante
        if root is None:
            try:
                from .init_check import detect_init
                return detect_init()
            except ImportError:
                pass
        # Fallback avec préfixe
        if (prefix / "run/systemd/system").exists():
            return "systemd", None
        elif (prefix / "sbin/openrc").exists():
            return "openrc", None
        elif (prefix / "sbin/initctl").exists():
            return "upstart", None
        else:
            return "sysvinit", None

    def log_event(self, name, **params):
        """Émet un événement via le bus global."""
        from ..bus.event_bus import MessageBus
        bus = MessageBus()
        bus.emit(name, source=self.id, **params)


class InitConfigDetectTask(Task):
    """
    Détection avancée du système d'initialisation (cible et live).
    """
    def run(self):
        from pathlib import Path

        root = self.params.get('root')
        root_path = Path(root) if root else Path()
        init_system, init_version = self._detect_init(root)
        is_live = False
        live_medium = None
        # Détection d'environnement live (live CD/USB) par rapport à root
        live_paths = [
            "run/initramfs/live",
            "run/live/medium",
            "cdrom",
            "lib/live/mount/medium",
        ]
        for rel in live_paths:
            path = root_path / rel
            if path.exists():
                is_live = True
                live_medium = str(path)
                break
        # Détection de l'environnement cible (installé)
        target_installed = (root_path / "etc/fsdeploy").exists()
        self.log_event("init.config.detect",
                       init_system=init_system,
                       init_version=init_version,
                       is_live=is_live,
                       live_medium=live_medium,
                       target_installed=target_installed,
                       root=str(root) if root else None)
        return {
            "init_system": init_system,
            "init_version": init_version,
            "is_live": is_live,
            "live_medium": live_medium,
            "target_installed": target_installed,
        }

    def _detect_init(self, root=None):
        prefix = Path(root) if root else Path()
        if root is None:
            try:
                from .init_check import detect_init
                return detect_init()
            except ImportError:
                pass
        if (prefix / "run/systemd/system").exists():
            return "systemd", None
        elif (prefix / "sbin/openrc").exists():
            return "openrc", None
        elif (prefix / "sbin/initctl").exists():
            return "upstart", None
        else:
            return "sysvinit", None

    def log_event(self, name, **params):
        from ..bus.event_bus import MessageBus
        bus = MessageBus()
        bus.emit(name, source=self.id, **params)


class InitServiceControlTask(Task):
    """
    Contrôle (start/stop/restart) du service fsdeploy.
    """
    def run(self):
        root = self.params.get('root')
        action = self.params.get('action', 'start')  # start, stop, restart, status
        init_system, _ = self._detect_init(root)
        self.log_event("init.service.control.start",
                       init_system=init_system,
                       action=action,
                       root=str(root) if root else None)
        success = False
        if init_system == "systemd":
            cmd = ['systemctl']
            if root:
                cmd.extend(['--root', root])
            cmd.extend([action, 'fsdeploy.service'])
            try:
                subprocess.run(cmd, check=True, capture_output=True)
                success = True
                self.log_event("init.service.control.success",
                               action=action)
            except subprocess.CalledProcessError as e:
                self.log_event("init.service.control.failed",
                               error=str(e.stderr))
        elif init_system == "openrc":
            # openrc utilise /etc/init.d/fsdeploy {action}
            service_path = Path(root if root else '') / "etc/init.d/fsdeploy"
            if service_path.exists():
                cmd = [str(service_path), action]
                try:
                    subprocess.run(cmd, check=True, capture_output=True)
                    success = True
                    self.log_event("init.service.control.success",
                                   action=action)
                except subprocess.CalledProcessError as e:
                    self.log_event("init.service.control.failed",
                                   error=str(e.stderr))
            else:
                self.log_event("init.service.control.service_not_found")
        elif init_system == "sysvinit":
            # similaire openrc
            service_path = Path(root if root else '') / "etc/init.d/fsdeploy"
            if service_path.exists():
                cmd = [str(service_path), action]
                try:
                    subprocess.run(cmd, check=True, capture_output=True)
                    success = True
                    self.log_event("init.service.control.success",
                                   action=action)
                except subprocess.CalledProcessError as e:
                    self.log_event("init.service.control.failed",
                                   error=str(e.stderr))
            else:
                self.log_event("init.service.control.service_not_found")
        elif init_system == "upstart":
            if action in ('start', 'stop', 'restart'):
                cmd = ['initctl']
                if root:
                    cmd = ['chroot', root, 'initctl']
                cmd.append(action)
                cmd.append('fsdeploy')
                try:
                    subprocess.run(cmd, check=True, capture_output=True)
                    success = True
                    self.log_event("init.service.control.success",
                                   action=action)
                except subprocess.CalledProcessError as e:
                    self.log_event("init.service.control.failed",
                                   error=str(e.stderr))
            else:
                self.log_event("init.service.control.unsupported_action")
        self.log_event("init.service.control.finish")
        return {
            "init_system": init_system,
            "action": action,
            "success": success
        }

    def _detect_init(self, root=None):
        prefix = Path(root) if root else Path()
        if root is None:
            try:
                from .init_check import detect_init
                return detect_init()
            except ImportError:
                pass
        if (prefix / "run/systemd/system").exists():
            return "systemd", None
        elif (prefix / "sbin/openrc").exists():
            return "openrc", None
        elif (prefix / "sbin/initctl").exists():
            return "upstart", None
        else:
            return "sysvinit", None

    def log_event(self, name, **params):
        from ..bus.event_bus import MessageBus
        bus = MessageBus()
        bus.emit(name, source=self.id, **params)


class InitConfigureTask(Task):
    """
    Configuration fine du système d'initialisation (ex: paramètres de boot).
    """
    def run(self):
        root = self.params.get('root')
        root_path = Path(root) if root else Path()
        init_system, _ = self._detect_init(root)
        self.log_event("init.configure.start",
                       init_system=init_system,
                       params=self.params,
                       root=str(root) if root else None)
        # Créer /etc/fsdeploy/init.conf avec les paramètres
        import json
        config_dir = root_path / "etc/fsdeploy"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_file = config_dir / "init.conf"
        with open(config_file, 'w') as f:
            json.dump(self.params, f, indent=2)
        self.log_event("init.configure.config_written",
                       path=str(config_file))
        # Si des paramètres spécifiques sont présents, ajuster les fichiers du système
        # Exemple: timeout de boot pour systemd
        if init_system == "systemd":
            self._configure_systemd(root_path)
        elif init_system == "openrc":
            self._configure_openrc(root_path)
        elif init_system == "sysvinit":
            self._configure_sysvinit(root_path)
        elif init_system == "upstart":
            self._configure_upstart(root_path)
        self.log_event("init.configure.finish")
        return {"init_system": init_system, "configured": True}

    def _write_config_file(self, path: Path, content: str):
        """Écrit un fichier de configuration avec les permissions appropriées."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            f.write(content)
        os.chmod(path, 0o644)
        self.log_event("init.configure.config_file_written", path=str(path))

    def _configure_systemd(self, root_path: Path):
        """Configurations spécifiques à systemd."""
        # Créer un drop-in pour surcharger le service
        dropin_dir = root_path / "etc/systemd/system/fsdeploy.service.d"
        dropin_dir.mkdir(parents=True, exist_ok=True)
        override = dropin_dir / "override.conf"
        # Récupérer les paramètres pertinents
        timeout = self.params.get('timeout', 30)
        restart_sec = self.params.get('restart_sec', 5)
        user = self.params.get('user')
        group = self.params.get('group')
        env = self.params.get('env', {})
        working_dir = self.params.get('working_dir')
        restart_policy = self.params.get('restart', 'on-failure')
        lines = []
        lines.append('[Service]')
        lines.append(f'TimeoutStartSec={timeout}')
        lines.append(f'RestartSec={restart_sec}')
        if user:
            lines.append(f'User={user}')
        if group:
            lines.append(f'Group={group}')
        if working_dir:
            lines.append(f'WorkingDirectory={working_dir}')
        if env:
            for key, val in env.items():
                lines.append(f'Environment={key}={val}')
        lines.append(f'Restart={restart_policy}')
        content = '\n'.join(lines) + '\n'
        self._write_config_file(override, content)
        # Recharger systemd
        cmd = ['systemctl']
        if root_path != Path():
            cmd.extend(['--root', str(root_path)])
        cmd.append('daemon-reload')
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            self.log_event("init.configure.systemd_daemon_reloaded")
        except subprocess.CalledProcessError as e:
            self.log_event("init.configure.systemd_reload_failed", error=str(e.stderr))

    def _configure_openrc(self, root_path: Path):
        """Configurations spécifiques à OpenRC."""
        # Écrire /etc/conf.d/fsdeploy
        confd = root_path / "etc/conf.d/fsdeploy"
        opts = self.params.get('opts', '')
        user = self.params.get('user')
        group = self.params.get('group')
        env = self.params.get('env', {})
        lines = []
        lines.append('# Configuration for fsdeploy service')
        lines.append(f'OPTS="{opts}"')
        if user:
            lines.append(f'USER="{user}"')
        if group:
            lines.append(f'GROUP="{group}"')
        if env:
            for key, val in env.items():
                lines.append(f'{key}="{val}"')
        content = '\n'.join(lines) + '\n'
        self._write_config_file(confd, content)

    def _configure_sysvinit(self, root_path: Path):
        """Configurations spécifiques à SysVinit."""
        # Écrire /etc/default/fsdeploy
        default = root_path / "etc/default/fsdeploy"
        opts = self.params.get('opts', '')
        user = self.params.get('user')
        group = self.params.get('group')
        env = self.params.get('env', {})
        lines = []
        lines.append('# Configuration for fsdeploy service')
        lines.append(f'OPTS="{opts}"')
        if user:
            lines.append(f'USER="{user}"')
        if group:
            lines.append(f'GROUP="{group}"')
        if env:
            for key, val in env.items():
                lines.append(f'{key}="{val}"')
        content = '\n'.join(lines) + '\n'
        self._write_config_file(default, content)

    def _configure_upstart(self, root_path: Path):
        """Configurations spécifiques à Upstart."""
        # Upstart n'a pas de fichier de configuration supplémentaire typique.
        # On peut éventuellement ajuster /etc/init/fsdeploy.conf mais il vaut mieux
        # ne pas modifier le fichier installé.
        pass

    def _detect_init(self, root=None):
        # Même que ci-dessus
        prefix = Path(root) if root else Path()
        if root is None:
            try:
                from .init_check import detect_init
                return detect_init()
            except ImportError:
                pass
        if (prefix / "run/systemd/system").exists():
            return "systemd", None
        elif (prefix / "sbin/openrc").exists():
            return "openrc", None
        elif (prefix / "sbin/initctl").exists():
            return "upstart", None
        else:
            return "sysvinit", None

    def log_event(self, name, **params):
        from ..bus.event_bus import MessageBus
        bus = MessageBus()
        bus.emit(name, source=self.id, **params)


class InitPostInstallCheckTask(Task):
    """
    Vérification post‑installation du service fsdeploy.
    """
    def run(self):
        root = self.params.get('root')
        root_path = Path(root) if root else Path()
        init_system, _ = self._detect_init(root)
        self.log_event("init.postinstall.check.start",
                       init_system=init_system,
                       root=str(root) if root else None)
        checks = []
        # Vérifier que le service est activé (selon le système)
        if init_system == "systemd":
            try:
                cmd = ['systemctl']
                if root:
                    cmd.extend(['--root', root])
                cmd.extend(['is-enabled', 'fsdeploy.service'])
                result = subprocess.run(cmd, capture_output=True, text=True)
                enabled = result.returncode == 0
                checks.append(('service_enabled', enabled))
                if enabled:
                    self.log_event("init.postinstall.check.service_enabled")
                else:
                    self.log_event("init.postinstall.check.service_not_enabled")
            except Exception as e:
                self.log_event("init.postinstall.check.systemd_check_failed",
                               error=str(e))
        elif init_system == "openrc":
            try:
                # Vérifier si le service est dans le niveau par défaut
                cmd = ['rc-update']
                if root:
                    cmd.extend(['-u', root])
                cmd.extend(['show', 'default'])
                result = subprocess.run(cmd, capture_output=True, text=True)
                enabled = 'fsdeploy' in result.stdout
                checks.append(('service_enabled', enabled))
                self.log_event("init.postinstall.check.openrc_enabled",
                               enabled=enabled)
            except Exception as e:
                self.log_event("init.postinstall.check.openrc_check_failed",
                               error=str(e))
        # Vérifier que le binaire principal existe
        bin_path = root_path / "usr/bin/fsdeploy"
        bin_exists = bin_path.exists()
        checks.append(('binary_exists', bin_exists))
        if bin_exists:
            self.log_event("init.postinstall.check.binary_exists")
        else:
            self.log_event("init.postinstall.check.binary_missing")
        # Vérifier les permissions du binaire (exécutable)
        if bin_exists:
            import stat
            mode = bin_path.stat().st_mode
            is_exec = bool(mode & stat.S_IXUSR)
            checks.append(('binary_executable', is_exec))
            if is_exec:
                self.log_event("init.postinstall.check.binary_executable")
            else:
                self.log_event("init.postinstall.check.binary_not_executable")
        # Vérifier que le fichier de configuration existe
        config_path = root_path / "etc/fsdeploy/init.conf"
        config_exists = config_path.exists()
        checks.append(('config_exists', config_exists))
        if config_exists:
            self.log_event("init.postinstall.check.config_exists")
        else:
            self.log_event("init.postinstall.check.config_missing")
        self.log_event("init.postinstall.check.finish")
        return {
            "init_system": init_system,
            "checks": checks,
            "all_passed": all(c[1] for c in checks) if checks else True
        }

    def _detect_init(self, root=None):
        prefix = Path(root) if root else Path()
        if root is None:
            try:
                from .init_check import detect_init
                return detect_init()
            except ImportError:
                pass
        if (prefix / "run/systemd/system").exists():
            return "systemd", None
        elif (prefix / "sbin/openrc").exists():
            return "openrc", None
        elif (prefix / "sbin/initctl").exists():
            return "upstart", None
        else:
            return "sysvinit", None

    def log_event(self, name, **params):
        from ..bus.event_bus import MessageBus
        bus = MessageBus()
        bus.emit(name, source=self.id, **params)
