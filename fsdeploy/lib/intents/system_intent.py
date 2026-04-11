"""
fsdeploy.intents.system_intent
================================
Intents pour les operations systeme declenchees par la TUI.

Events geres :
  preset.list / preset.save / preset.activate / preset.delete
  coherence.check
  snapshot.list / snapshot.create / snapshot.rollback
  stream.start / stream.stop / stream.status
  zbm.install / zbm.status
  config.reload / config.save
  debug.exec_cmd
"""

from typing import Any

from ..scheduler.model.intent import Intent
from ..scheduler.model.task import Task
from ..scheduler.model.resource import Resource, STREAM, NETWORK, EFI
from ..scheduler.model.lock import Lock
from ..scheduler.core.registry import register_intent
from ..scheduler.security.decorator import security


# ═══════════════════════════════════════════════════════════════════
# TASKS SUPPLEMENTAIRES
# ═══════════════════════════════════════════════════════════════════

@security.preset.list
class PresetListTask(Task):
    """Liste les presets depuis fsdeploy.conf [presets]."""

    def run(self) -> list[dict[str, Any]]:
        config_path = self.params.get("config_path", "")
        if not config_path:
            return []

        try:
            from configobj import ConfigObj
            cfg = ConfigObj(config_path, encoding="utf-8")
            presets_section = cfg.get("presets", {})
            active = presets_section.get("active", "")
            result = []
            for key, val in presets_section.items():
                if isinstance(val, dict):
                    entry = dict(val)
                    entry["name"] = key
                    entry["is_active"] = (key == active)
                    result.append(entry)
            return result
        except Exception as e:
            return [{"error": str(e)}]


@security.preset.save
class PresetSaveTask(Task):
    """Sauvegarde un preset dans fsdeploy.conf."""

    def required_locks(self):
        return [Lock("config", owner_id=str(self.id))]

    def run(self) -> dict[str, Any]:
        config_path = self.params.get("config_path", "")
        name = self.params.get("name", "")
        data = self.params.get("data", {})
        if not config_path or not name:
            raise ValueError("config_path and name required")

        from configobj import ConfigObj
        cfg = ConfigObj(config_path, encoding="utf-8")
        if "presets" not in cfg:
            cfg["presets"] = {}
        cfg["presets"][name] = data
        cfg.write()
        return {"name": name, "saved": True}


@security.preset.activate
class PresetActivateTask(Task):
    """Active un preset (ecrit presets.active)."""

    def required_locks(self):
        return [Lock("config", owner_id=str(self.id))]

    def run(self) -> dict[str, Any]:
        config_path = self.params.get("config_path", "")
        name = self.params.get("name", "")
        if not config_path or not name:
            raise ValueError("config_path and name required")

        from configobj import ConfigObj
        cfg = ConfigObj(config_path, encoding="utf-8")
        if "presets" not in cfg:
            cfg["presets"] = {}
        cfg["presets"]["active"] = name
        cfg.write()
        return {"name": name, "activated": True}


@security.preset.delete
class PresetDeleteTask(Task):
    """Supprime un preset."""

    def required_locks(self):
        return [Lock("config", owner_id=str(self.id))]

    def run(self) -> dict[str, Any]:
        config_path = self.params.get("config_path", "")
        name = self.params.get("name", "")
        if not config_path or not name:
            raise ValueError("config_path and name required")

        from configobj import ConfigObj
        cfg = ConfigObj(config_path, encoding="utf-8")
        presets = cfg.get("presets", {})
        if name in presets:
            del presets[name]
            if presets.get("active") == name:
                presets["active"] = ""
            cfg.write()
            return {"name": name, "deleted": True}
        return {"name": name, "deleted": False, "error": "not found"}


@security.zbm.install(require_root=True)
class ZBMInstallTask(Task):
    """Installe ZFSBootMenu EFI."""

    def required_resources(self):
        return [EFI]

    def required_locks(self):
        return [Lock("efi", owner_id=str(self.id), exclusive=True)]

    def run(self) -> dict[str, Any]:
        efi_device = self.params.get("efi_device", "")
        efi_mount = self.params.get("efi_mount", "/boot/efi")
        zbm_efi_path = self.params.get("zbm_efi_path", "EFI/ZBM/vmlinuz.EFI")
        cmdline = self.params.get("cmdline", "quiet loglevel=3 zbm.autosize=0")

        from pathlib import Path

        efi_dir = Path(efi_mount)
        if not efi_dir.is_dir():
            # Monter la partition EFI
            efi_dir.mkdir(parents=True, exist_ok=True)
            if efi_device:
                self.run_cmd(f"mount {efi_device} {efi_mount}", sudo=True)

        zbm_full = efi_dir / zbm_efi_path
        installed = zbm_full.exists()

        # Enregistrer dans EFI boot manager
        if installed:
            self.run_cmd(
                f"efibootmgr -c -d {efi_device} -p 1 "
                f'-L "ZFSBootMenu" -l "\\{zbm_efi_path.replace("/", "\\")}"',
                sudo=True, check=False,
            )

        return {
            "efi_path": str(zbm_full),
            "installed": installed,
            "efi_device": efi_device,
        }


@security.zbm.status
class ZBMStatusTask(Task):
    """Verifie le statut de ZFSBootMenu."""

    def run(self) -> dict[str, Any]:
        from pathlib import Path

        result = {"installed": False, "efi_entry": False, "paths_found": []}

        # Chercher le binaire
        for path in ["/boot/efi/EFI/ZBM/vmlinuz.EFI",
                     "/boot/efi/EFI/ZBM/VMLINUZ.EFI",
                     "/boot/EFI/ZBM/vmlinuz.EFI"]:
            if Path(path).exists():
                result["installed"] = True
                result["paths_found"].append(path)

        # Verifier l'entree EFI
        r = self.run_cmd("efibootmgr -v", sudo=True, check=False)
        if r.success and "ZFSBootMenu" in r.stdout:
            result["efi_entry"] = True
            for line in r.stdout.splitlines():
                if "ZFSBootMenu" in line:
                    result["efi_line"] = line.strip()
                    break

        return result


@security.debug.exec_cmd
class DebugExecTask(Task):
    """Execute une commande arbitraire (mode debug)."""

    def run(self) -> dict[str, str]:
        cmd = self.params.get("cmd", "")
        use_sudo = self.params.get("sudo", False)
        if not cmd:
            raise ValueError("cmd required")

        r = self.run_cmd(cmd, sudo=use_sudo, check=False, timeout=30)
        return {
            "cmd": cmd,
            "stdout": r.stdout,
            "stderr": r.stderr,
            "returncode": str(r.returncode),
            "success": str(r.success),
        }


# ═══════════════════════════════════════════════════════════════════
# INTENTS
# ═══════════════════════════════════════════════════════════════════

# ── Presets ─────────────────────────────────────────────────────────

@register_intent("preset.list")
class PresetListIntent(Intent):
    def build_tasks(self):
        return [PresetListTask(id="preset_list", params=self.params,
                               context=self.context)]

@register_intent("preset.save")
class PresetSaveIntent(Intent):
    def build_tasks(self):
        return [PresetSaveTask(id="preset_save", params=self.params,
                               context=self.context)]

@register_intent("preset.activate")
class PresetActivateIntent(Intent):
    def build_tasks(self):
        return [PresetActivateTask(id="preset_activate", params=self.params,
                                   context=self.context)]

@register_intent("preset.delete")
class PresetDeleteIntent(Intent):
    def build_tasks(self):
        return [PresetDeleteTask(id="preset_delete", params=self.params,
                                 context=self.context)]

# ── Coherence ───────────────────────────────────────────────────────

@register_intent("coherence.check")
class CoherenceCheckIntent(Intent):
    def build_tasks(self):
        from ..function.coherence.check import CoherenceCheckTask
        return [CoherenceCheckTask(id="coherence_check", params=self.params,
                                   context=self.context)]

@register_intent("coherence.quick")
class CoherenceQuickIntent(Intent):
    """Vérification de cohérence rapide (seulement les points critiques)."""
    def build_tasks(self):
        from ..function.coherence.check import CoherenceCheckTask
        # Passer un paramètre pour indiquer de ne faire que les vérifications critiques
        params = dict(self.params)
        params["quick_mode"] = True
        return [CoherenceCheckTask(id="coherence_quick", params=params,
                                   context=self.context)]

@register_intent("coherence.verify")
class CoherenceVerifyIntent(Intent):
    """Vérification de cohérence rapide retournant un résultat simple (pour scripts)."""
    def build_tasks(self):
        from ..function.coherence.check import CoherenceCheckTask
        params = dict(self.params)
        params["quick_mode"] = True
        return [CoherenceCheckTask(id="coherence_verify", params=params,
                                   context=self.context)]

# ── Snapshots ───────────────────────────────────────────────────────

@register_intent("snapshot.list")
class SnapshotListIntent(Intent):
    def build_tasks(self):
        from ..function.snapshot.create import SnapshotListTask
        return [SnapshotListTask(id="snap_list", params=self.params,
                                 context=self.context)]

@register_intent("snapshot.create")
class SnapshotCreateIntent(Intent):
    def build_tasks(self):
        from ..function.snapshot.create import SnapshotCreateTask
        return [SnapshotCreateTask(id="snap_create", params=self.params,
                                   context=self.context)]

@register_intent("snapshot.rollback")
class SnapshotRollbackIntent(Intent):
    def build_tasks(self):
        from ..function.snapshot.create import SnapshotRollbackTask
        return [SnapshotRollbackTask(id="snap_rollback", params=self.params,
                                     context=self.context)]

# ── Stream ──────────────────────────────────────────────────────────

@register_intent("stream.start")
class StreamStartIntent(Intent):
    def build_tasks(self):
        from ..function.stream.youtube import StreamStartTask
        return [StreamStartTask(id="stream_start", params=self.params,
                                context=self.context)]

@register_intent("stream.stop")
class StreamStopIntent(Intent):
    def build_tasks(self):
        from ..function.stream.youtube import StreamStopTask
        return [StreamStopTask(id="stream_stop", params=self.params,
                               context=self.context)]

@register_intent("stream.status")
class StreamStatusIntent(Intent):
    def build_tasks(self):
        from ..function.stream.youtube import StreamStatusTask
        return [StreamStatusTask(id="stream_status", params=self.params,
                                 context=self.context)]

# ── ZBM ─────────────────────────────────────────────────────────────

@register_intent("zbm.install")
class ZBMInstallIntent(Intent):
    def build_tasks(self):
        return [ZBMInstallTask(id="zbm_install", params=self.params,
                               context=self.context)]

@register_intent("zbm.status")
class ZBMStatusIntent(Intent):
    def build_tasks(self):
        return [ZBMStatusTask(id="zbm_status", params=self.params,
                              context=self.context)]

# ── Debug ───────────────────────────────────────────────────────────

@register_intent("debug.exec")
class DebugExecIntent(Intent):
    def build_tasks(self):
        return [DebugExecTask(id="debug_exec", params=self.params,
                              context=self.context)]


@register_intent("config.snapshot.save")
class ConfigSnapshotSaveIntent(Intent):
    """Prendre un snapshot de la configuration actuelle."""
    def build_tasks(self):
        from ..function.config.snapshot import ConfigSnapshotTask
        return [ConfigSnapshotTask(id="config_snapshot_save", params=self.params,
                                   context=self.context)]


@register_intent("config.snapshot.restore")
class ConfigSnapshotRestoreIntent(Intent):
    """Restaurer une configuration à partir d'un snapshot."""
    def build_tasks(self):
        from ..function.config.restore import ConfigRestoreTask
        return [ConfigRestoreTask(id="config_snapshot_restore", params=self.params,
                                  context=self.context)]


@register_intent("config.snapshot.list")
class ConfigSnapshotListIntent(Intent):
    """Lister les snapshots de configuration disponibles."""
    def build_tasks(self):
        from ..function.config.restore import ConfigSnapshotListTask
        return [ConfigSnapshotListTask(id="config_snapshot_list", params=self.params,
                                       context=self.context)]


@register_intent("scheduler.verify")
class SchedulerVerifyIntent(Intent):
    """Vérifier l'intégration des tâches avec le scheduler."""
    def build_tasks(self):
        from ..function.scheduler.verify import SchedulerVerifyTask
        return [SchedulerVerifyTask(id="scheduler_verify", params=self.params,
                                    context=self.context)]


@register_intent("security.status")
class SecurityStatusIntent(Intent):
    """Récupérer l'état de la configuration de sécurité."""
    def build_tasks(self):
        from ..function.security.status import SecurityStatusTask
        return [SecurityStatusTask(id="security_status", params=self.params,
                                   context=self.context)]


@register_intent("init.detect")
class InitDetectIntent(Intent):
    """Détecte le système d'initialisation en cours."""
    def build_tasks(self):
        from ..function.init_check import InitDetectTask
        return [InitDetectTask(id="init_detect", params=self.params,
                               context=self.context)]

@register_intent("health.check")
class HealthCheckIntent(Intent):
    """Vérification de santé du système."""
    def build_tasks(self):
        from ..function.health.check import HealthCheckTask
        return [HealthCheckTask(id="health_check", params=self.params,
                                context=self.context)]
