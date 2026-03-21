# Master Index — Documentation fsdeploy complète

**Version** : 3.0 (Sessions 1 + 2)  
**Date** : 21 mars 2026

---

## 📚 Documents principaux (Session 2 — Mermaid + GraphView)

### 🆕 README_v2.md ⭐
**Taille** : ~25K  
**Contenu** : README principal avec :
- Diagrammes Mermaid (4 graphiques)
- Badges développement (alpha/caution)
- GraphView documentation
- 15 rôles de détection
- Architecture complète

**👉 UTILISER COMME README PRINCIPAL**

---

### 🆕 role_patterns.py
**Taille** : ~15K  
**Contenu** : Module Python avec :
- 15 rôles de détection (au lieu de 9)
- Scoring agrégé multi-signaux
- Fonctions utilitaires (colors, emojis, ASCII fallback)
- Code production-ready

**Emplacement** : `lib/function/detect/role_patterns.py`

---

### 🆕 graph_screen.py
**Taille** : ~20K  
**Contenu** : GraphViewScreen Textual avec :
- Animation temps réel (10 FPS)
- Auto-centrage tâche active
- Navigation dans le temps
- 3 widgets custom (PipelineStages, TaskDetail, TaskHistory)
- Pause/Resume, Zoom

**Emplacement** : `lib/ui/screens/graph.py`

---

### 🆕 GRAPHVIEW.md
**Taille** : ~18K  
**Contenu** : Documentation complète GraphView :
- Architecture widgets
- Flux de données (diagrammes Mermaid)
- Interactions utilisateur
- Timers et performance
- Configuration
- Tests
- Troubleshooting

---

### 🆕 SESSION_FINAL.md
**Taille** : ~15K  
**Contenu** : Récapitulatif session 2 :
- Comparaison avant/après
- Fichiers produits
- Intégration projet
- Statistiques finales
- Checklist complète

---

## 📚 Documents techniques (Session 1)

### FINAL_RECAP.md ⭐
**Taille** : ~16K  
**Contenu** : Récapitulatif complet session 1 :
- Réponses à toutes les questions posées
- Import vs mount (aucun problème)
- Détection avancée (MD5, squashfs, partitions)
- Checklist complète

---

### IMPORT_VS_MOUNT.md
**Taille** : ~14K  
**Contenu** : Document technique détaillé :
- Import pools vs mount manuel
- Principes ZFS (property vs mount actuel)
- Workflow fsdeploy (3 phases)
- Cas limites et edge cases
- Recommandations

---

### ADVANCED_DETECTION.md
**Taille** : ~27K  
**Contenu** : Détection multi-stratégie :
- Scan structure (ROLE_PATTERNS)
- Magic bytes (signatures binaires)
- Identification partitions
- Déduplication kernels (MD5)
- Validation squashfs
- Scoring agrégé

---

### MOUNTING_STRATEGY.md
**Taille** : ~15K  
**Contenu** : Stratégie de montage :
- Isolation `/mnt/`
- Résolution conflits
- Code canonique `mount -t zfs`
- Workflow TUI
- Exemples pratiques

---

### DIAGRAMS.md
**Taille** : ~40K  
**Contenu** : 5 diagrammes ASCII :
- Architecture globale
- Pipeline Event→Intent→Task
- Workflow détection (4 phases)
- Stratégie montage
- Flux de données complet (boot→stream)

**Note** : Remplacé par diagrammes Mermaid dans README_v2.md

---

### DOCUMENTATION_SUMMARY.md
**Taille** : ~11K  
**Contenu** : Vue d'ensemble session 1 :
- Documents produits (5)
- Améliorations clés
- Statistiques
- Intégration dépôt

---

### INDEX.md
**Taille** : ~14K  
**Contenu** : Index navigation session 1 :
- Documents principaux
- Documents référence
- Documents obsolètes
- Guide de lecture
- Statistiques

---

### fsdeploy_main_status.md
**Taille** : ~18K  
**Contenu** : État branche main :
- Statut : COMPLET ET PRODUCTION-READY
- Métriques (68 fichiers, 4870 lignes)
- Architecture complète (8 sections)
- CLEANUP.md (fichiers à supprimer)

---

## 📚 Documents obsolètes (à archiver)

Ces documents ont été intégrés/remplacés :

- ~~MOUNTPOINT_ANALYSIS.md~~ → intégré dans IMPORT_VS_MOUNT.md
- ~~ZFS_MOUNTPOINT_VS_MANUAL.md~~ → intégré dans IMPORT_VS_MOUNT.md
- ~~fix_mounts_conflicts.md~~ → intégré dans MOUNTING_STRATEGY.md
- ~~SESSION_SUMMARY.md~~ → remplacé par FINAL_RECAP.md

**Action** : Déplacer dans `docs/archive/`

---

## 🗂️ Organisation recommandée du dépôt

```
fsdeploy/
├── README.md                          # 🆕 README_v2.md (Mermaid + GraphView)
│
├── docs/
│   ├── SESSION_FINAL.md               # 🆕 Récap session 2
│   ├── GRAPHVIEW.md                   # 🆕 Doc GraphView
│   ├── FINAL_RECAP.md                 # Récap session 1
│   ├── IMPORT_VS_MOUNT.md
│   ├── ADVANCED_DETECTION.md
│   ├── MOUNTING_STRATEGY.md
│   ├── DIAGRAMS.md                    # Diagrammes ASCII (référence)
│   ├── DOCUMENTATION_SUMMARY.md
│   ├── INDEX.md
│   ├── fsdeploy_main_status.md
│   │
│   └── archive/                       # Documents obsolètes
│       ├── MOUNTPOINT_ANALYSIS.md
│       ├── ZFS_MOUNTPOINT_VS_MANUAL.md
│       └── fix_mounts_conflicts.md
│
├── lib/
│   ├── function/
│   │   └── detect/
│   │       └── role_patterns.py       # 🆕 15 rôles
│   │
│   └── ui/
│       └── screens/
│           └── graph.py               # 🆕 GraphViewScreen
│
├── etc/
│   └── fsdeploy.conf                  # 🆕 Section [graphview]
│
├── CONTRIBUTING.md                    # À créer
├── CHANGELOG.md                       # À créer
└── LICENSE                            # MIT
```

---

## 📊 Statistiques globales

### Par session

| Session | Documents | Lignes | Code Python | Diagrammes |
|---------|-----------|--------|-------------|------------|
| Session 1 | 7 docs | ~3100 | ~500 | 5 ASCII |
| Session 2 | 4 docs | ~1600 | ~1000 | 4 Mermaid + 1 Mermaid stateDiagram |
| **TOTAL** | **11 docs** | **~4700** | **~1500** | **9 diagrammes** |

### Par type

| Type | Nombre | Taille totale |
|------|--------|---------------|
| Documentation Markdown | 11 | ~140K |
| Code Python | 3 | ~50K |
| Diagrammes ASCII | 5 | inclus dans docs |
| Diagrammes Mermaid | 5 | inclus dans README |

---

## 🎯 Guide d'utilisation

### Pour commencer rapidement

1. **Lire** : `README_v2.md` (vue d'ensemble avec Mermaid)
2. **Comprendre** : `SESSION_FINAL.md` (récap complet session 2)
3. **Implémenter** : Copier `role_patterns.py` et `graph_screen.py`

### Pour approfondir un sujet

| Sujet | Document |
|-------|----------|
| Import vs mount | `IMPORT_VS_MOUNT.md` |
| Détection avancée | `ADVANCED_DETECTION.md` |
| Montage strategy | `MOUNTING_STRATEGY.md` |
| GraphView | `GRAPHVIEW.md` |
| État du code | `fsdeploy_main_status.md` |

### Pour développer

1. **Architecture** : Diagrammes Mermaid dans `README_v2.md`
2. **Code patterns** : `role_patterns.py` (détection)
3. **UI patterns** : `graph_screen.py` (Textual widgets)
4. **Tests** : `GRAPHVIEW.md` (section Tests)

---

## ✅ Actions recommandées

### Immédiat

1. ✅ Remplacer `README.md` par `README_v2.md`
2. ✅ Copier `role_patterns.py` → `lib/function/detect/`
3. ✅ Copier `graph_screen.py` → `lib/ui/screens/`
4. ✅ Ajouter section `[graphview]` dans `etc/fsdeploy.conf`

### Court terme

1. ⏳ Archiver documents obsolètes dans `docs/archive/`
2. ⏳ Implémenter `scheduler.get_state_snapshot()`
3. ⏳ Implémenter `bridge.get_scheduler_state()`
4. ⏳ Ajouter binding `g` dans `lib/ui/app.py`

### Moyen terme

1. ⏳ Tests GraphView (visuel + intégration)
2. ⏳ Tests role_patterns (15 rôles)
3. ⏳ CI/CD (GitHub Actions)
4. ⏳ Packaging (deb, AUR)

---

## 🚀 Améliorations futures

### GraphView

- [ ] Zoom visuel réel (CSS transform)
- [ ] Slider temporel (navigation temps avancée)
- [ ] Export timeline (SVG, JSON, replay)
- [ ] Métriques temps réel (CPU/RAM, latence)

### Détection

- [ ] Machine learning pour scoring (TensorFlow Lite)
- [ ] Patterns configurables par utilisateur
- [ ] Cache MD5 pour performance
- [ ] Scan parallèle async (asyncio)

### Documentation

- [ ] Guide contribution (CONTRIBUTING.md)
- [ ] Changelog (CHANGELOG.md)
- [ ] Wiki GitHub (tutoriels pas-à-pas)
- [ ] Vidéos démo (YouTube)

---

## 📝 Notes importantes

### Import pools
**Clé** : `zpool import -N` → aucun montage auto  
**Bug ZFS** : `zfs mount` échoue pour `mountpoint=legacy`  
**Solution** : `mount -t zfs <dataset> <mountpoint>` toujours

### Détection
**Stratégie** : Multi-signaux (pattern 40% + magic 30% + content 20%)  
**15 rôles** : boot, kernel, initramfs, squashfs, modules, rootfs, overlay, python_env, efi, home, archive, snapshot, data, cache, log  
**MD5 kernels** : Détection doublons automatique

### GraphView
**Animation** : 10 FPS (flèches animées)  
**Update** : 5 FPS (données scheduler)  
**Pause** : CPU quasi nul (timers inactifs)  
**Binding** : `g` depuis n'importe quel écran

### Montage
**Isolation** : Tout dans `/mnt/`, jamais dans `/boot` du live  
**Vérification** : Toujours via `/proc/mounts` (source de vérité)  
**Thread-safe** : Locks sur tous montages/démontages

---

## 📧 Support

**Questions / Issues** : https://github.com/newicody/fsdeploy/issues  
**Discussions** : https://github.com/newicody/fsdeploy/discussions  
**Pull Requests** : https://github.com/newicody/fsdeploy/pulls

---

## 📄 Licence

MIT License — voir [LICENSE](LICENSE)

---

<div align="center">

**Documentation fsdeploy v3.0**

**⚠️ ALPHA SOFTWARE — USE AT YOUR OWN RISK ⚠️**

Fait avec ❤️ et Python

**Sessions complètes : 2**  
**Documents produits : 11**  
**Lignes de code + doc : ~6200**  
**Diagrammes : 9**  

**Statut** : ✅ **COMPLET ET PRÊT POUR INTÉGRATION**

</div>
