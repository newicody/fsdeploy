"""
Intents de sauvegarde/restauration de configuration.
"""

from fsdeploy.lib.scheduler.model.intent import Intent, register_intent


@register_intent("config.snapshot.save")
class ConfigSnapshotSaveIntent(Intent):
    """Sauvegarde la configuration courante dans un snapshot nommé."""

    def build_tasks(self):
        from fsdeploy.lib.function.config.snapshot import ConfigSnapshotTask
        name = self.params.get("name", "")
        desc = self.params.get("description", "")
        return [
            ConfigSnapshotTask(
                id=f"config_save_{name}",
                params={"action": "save", "name": name, "description": desc},
                context=self.context,
            )
        ]


@register_intent("config.snapshot.restore")
class ConfigSnapshotRestoreIntent(Intent):
    """Restaure la configuration à partir d'un snapshot existant."""

    def build_tasks(self):
        from fsdeploy.lib.function.config.snapshot import ConfigSnapshotTask
        name = self.params.get("name", "")
        return [
            ConfigSnapshotTask(
                id=f"config_restore_{name}",
                params={"action": "restore", "name": name},
                context=self.context,
            )
        ]


@register_intent("config.snapshot.list")
class ConfigSnapshotListIntent(Intent):
    """Liste les snapshots de configuration disponibles."""

    def build_tasks(self):
        from fsdeploy.lib.function.config.snapshot import ConfigSnapshotTask
        return [
            ConfigSnapshotTask(
                id="config_list",
                params={"action": "list"},
                context=self.context,
            )
        ]
