# Message de commit suggéré

## Titre court

```
feat: Add Mermaid diagrams, GraphView real-time visualization, and 15 detection roles
```

## Description complète

```
feat: Major documentation and visualization updates (v3.0)

## 🆕 Nouveautés

### Documentation
- README avec diagrammes Mermaid (4 graphiques interactifs GitHub-native)
- Badges développement (alpha/caution warnings)
- Architecture complète avec graphes colorés
- 11 documents techniques (~6200 lignes)

### Code Python
- `role_patterns.py`: 15 rôles de détection (au lieu de 9)
  - Nouveaux: home, archive, snapshot, data, cache, log
  - Scoring agrégé multi-signaux (pattern 40% + magic 30% + content 20%)
  - Fonctions utilitaires (colors, emojis, ASCII fallback TERM=linux)

- `graph.py`: GraphViewScreen Textual pour visualisation temps réel
  - Animation 10 FPS (flèches animées)
  - Mise à jour données 5 FPS (scheduler live)
  - Auto-centrage sur tâche active
  - Navigation temps (← historique / → futur)
  - Pause/Resume, Zoom
  - 3 widgets custom: PipelineStages, TaskDetail, TaskHistory
  - Binding global 'g' depuis n'importe quel écran

## 📦 Fichiers ajoutés

### Racine
- README.md (remplace l'ancien, avec Mermaid)
- MASTER_INDEX.md (index complet de toute la doc)

### docs/
- SESSION_FINAL.md (récapitulatif session)
- GRAPHVIEW.md (doc complète GraphView)
- FINAL_RECAP.md (récap questions/réponses)
- IMPORT_VS_MOUNT.md (import pools vs mount manuel)
- ADVANCED_DETECTION.md (détection multi-stratégie)
- MOUNTING_STRATEGY.md (stratégie montage)
- DIAGRAMS.md (diagrammes ASCII référence)
- DOCUMENTATION_SUMMARY.md (vue d'ensemble)
- INDEX.md (navigation docs)
- fsdeploy_main_status.md (état branche main)

### lib/function/detect/
- role_patterns.py (15 rôles de détection)

### lib/ui/screens/
- graph.py (GraphViewScreen temps réel)

## ⚙️ Configuration requise

Ajouter dans `etc/fsdeploy.conf`:

```ini
[graphview]
enabled = true
fps = 10
auto_center = true
history_size = 100
animation_speed = 1.0
color_scheme = auto
show_locks = true
show_thread_id = true
compact_mode = false
```

## 🔧 Modifications scheduler nécessaires

```python
# lib/scheduler/core/scheduler.py
def get_state_snapshot(self) -> dict:
    """Retourne snapshot thread-safe pour GraphView."""
    with self._state_lock:
        return {
            "event_count": self._event_queue.qsize(),
            "intent_count": self._intent_queue.qsize(),
            "task_count": len(self._running_tasks),
            "completed_count": len(self._completed_tasks),
            "active_task": self._get_active_task_data(),
            "recent_tasks": self._get_recent_tasks(limit=10),
        }

# lib/ui/bridge.py
def get_scheduler_state(self) -> dict:
    """Wrapper pour GraphView."""
    return self._scheduler.get_state_snapshot()

# lib/ui/app.py
BINDINGS = [
    Binding("g", "push_screen_graph", "GraphView", show=True),
]

def action_push_screen_graph(self):
    from ui.screens.graph import GraphViewScreen
    self.push_screen(GraphViewScreen())
```

## 📊 Statistiques

- Documents créés: 11
- Lignes de documentation: ~4700
- Lignes de code Python: ~1500
- Diagrammes: 9 (4 Mermaid + 5 ASCII)
- Rôles de détection: 15 (était 9)

## ⚠️ Breaking Changes

Aucun - Tous les changements sont additifs.

## 🧪 Tests

```bash
# Test GraphView visuel
python3 -m fsdeploy --graph-only --demo

# Test rôles de détection
python3 -m pytest lib/test/test_role_patterns.py
```

## 📝 Documentation

Voir MASTER_INDEX.md pour navigation complète de la documentation.

---

**Version**: 3.0
**Date**: 21 mars 2026
**Auteur**: Claude (Anthropic)
```

## Fichiers à vérifier avant commit

```bash
# Structure
tree fsdeploy-v3.0/

# Contenu README
head -50 fsdeploy-v3.0/README.md

# Code Python
python3 -m py_compile fsdeploy-v3.0/lib/function/detect/role_patterns.py
python3 -m py_compile fsdeploy-v3.0/lib/ui/screens/graph.py
```

## Commandes Git suggérées

```bash
# Copier dans le dépôt
cp -r fsdeploy-v3.0/* /path/to/fsdeploy/

# Ou extraire l'archive
tar xzf fsdeploy-v3.0.tar.gz -C /path/to/fsdeploy/ --strip-components=1

# Vérifier
git status
git diff README.md
git diff lib/function/detect/role_patterns.py
git diff lib/ui/screens/graph.py

# Commit
git add .
git commit -F COMMIT_MESSAGE.md

# Push
git push origin main
```
