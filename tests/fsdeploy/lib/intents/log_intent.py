"""
Intent pour exporter les logs compressés (HuffmanStore) au format JSON.
"""

from ..intentlog.log import get_global_huffman_store
from ..scheduler.model.intent import Intent
from ..scheduler.core.registry import register_intent
from pathlib import Path


@register_intent("log.export")
class LogExportIntent(Intent):
    """
    Exporte les logs compressés dans un fichier JSON avec filtres optionnels.
    """

    def build_tasks(self):
        from ..scheduler.model.task import Task

        class LogExportTask(Task):
            def run(self):
                path = self.params.get("path")
                if not path:
                    raise ValueError("Le paramètre 'path' est obligatoire")
                path_obj = Path(path)
                table = self.params.get("table", "all")
                severity = self.params.get("severity")
                category = self.params.get("category")
                start_time = self.params.get("start_time")
                end_time = self.params.get("end_time")
                limit = self.params.get("limit", 10_000)

                store = get_global_huffman_store()
                store.export_json(
                    path=path_obj,
                    table=table,
                    severity=severity,
                    category=category,
                    start_time=start_time,
                    end_time=end_time,
                    limit=limit,
                )
                return {"exported_to": str(path_obj), "success": True}

        return [LogExportTask(id="log_export", params=self.params, context=self.context)]


@register_intent("log.stats")
class LogStatsIntent(Intent):
    """
    Retourne des statistiques sur les logs (compressés et non compressés).
    """

    def build_tasks(self):
        from ..scheduler.model.task import Task

        class LogStatsTask(Task):
            def run(self):
                from ..intentlog.log import intent_log
                from ..scheduler.metrics import get_log_severity_stats, get_log_export_stats
                stats = intent_log.stats()
                # Ajouter les stats des métriques (elles peuvent être redondantes, mais conservées pour compatibilité)
                stats["log_severity_stats"] = get_log_severity_stats()
                stats["log_export_stats"] = get_log_export_stats()
                return stats

        return [LogStatsTask(id="log_stats", params=self.params, context=self.context)]
