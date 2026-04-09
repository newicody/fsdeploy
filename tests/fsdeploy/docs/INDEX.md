# Index de la documentation fsdeploy

**Version** : 2.0  
**Date** : 21 mars 2026  
**Session** : Réécriture complète avec améliorations techniques

---

## 📚 Documents principaux (nouveaux)

### 1. FINAL_RECAP.md (16K) ⭐
**Document principal** — Répond à toutes les questions posées

**Contenu** :
- ✅ Import mountpoint et mount manuel — aucun problème ?
- ✅ Détection de rôle par scan de fichiers et structure
- ✅ Identification des partitions
- ✅ Recherche kernels doublons par MD5 et tri
- ✅ Test des squashfs et scan pour identification
- ✅ Graphiques descriptifs pour README
- Checklist complète (100% ✅)
- Points clés techniques
- Statistiques finales

**👉 COMMENCER PAR CE DOCUMENT**

---

### 2. IMPORT_VS_MOUNT.md (14K) 📖
**Document technique** — Import pools vs mount manuel

**Question traitée** :
> Peut-on importer des pools avec mountpoints configurés, puis monter manuellement ailleurs ?

**Réponse** : **OUI, absolument.**

**Sections** :
1. Principes ZFS (mountpoint property vs mount actuel)
2. Import avec no-mount (`zpool import -N`)
3. Mount manuel post-import (`mount -t zfs`)
4. Workflow fsdeploy détaillé (3 phases)
5. Pourquoi ça fonctionne
6. Cas limites et edge cases
7. Comparaison des approches
8. Vérification de l'état (commandes + script diagnostic)
9. Recommandations fsdeploy

**Code samples** : 15+

---

### 3. ADVANCED_DETECTION.md (27K) 📖
**Document technique** — Détection multi-stratégie

**Sections** :
1. Scan de structure (ROLE_PATTERNS)
   - 9 rôles définis
   - Algorithme de scoring
2. Scan de contenu (magic bytes)
   - Signatures binaires
   - Détection kernels
3. Identification des partitions
   - Par UUID et label
   - Scan du contenu
4. Déduplication kernels (MD5)
   - Détection doublons
   - Tri par version
5. Validation squashfs
   - Test de montage
   - Scan contenu
6. Scoring de confiance agrégé
   - Combinaison pondérée
   - Formule de calcul
7. Workflow complet de détection
8. Affichage dans la TUI

**Code samples** : 20+  
**Diagrammes** : 2

---

### 4. MOUNTING_STRATEGY.md (15K) 📖
**Document technique** — Stratégie de montage

**Sections** :
1. Problématique (conflits avec le live)
2. Stratégie d'isolation (`/mnt/`)
3. Propositions de montage par rôle
4. Cas pratiques (3 scénarios détaillés)
5. Code de montage canonique
6. Vérification post-montage
7. Workflow de montage dans la TUI
8. Gestion des conflits (matrice de décision)
9. Exemples pratiques (architectures simple + complexe)
10. Vérification de cohérence
11. Nettoyage

**Code samples** : 12+  
**Exemples** : 5

---

### 5. DIAGRAMS.md (40K) 🎨
**Documentation visuelle** — 5 diagrammes ASCII complets

**Diagrammes** :
1. **Architecture globale** — Vue d'ensemble complète
   - Debian Live → launch.sh → daemon
   - Config + Log + Runtime
   - Scheduler (EventQueue, IntentQueue, TaskGraph, ThreadPool)
   - Bus sources (Timer, Inotify, Udev, Socket)
   - TUI Textual (Bridge, 11 écrans)

2. **Pipeline Event → Intent → Task**
   - Sources (TUI, Timer, Inotify, Udev, Socket)
   - Event → Handler → Intent → Security Resolver → Task
   - Execution (ThreadPool)
   - RuntimeState (completed → callback → UI)

3. **Workflow de détection** — 4 phases
   - Phase 1 : Import pools (no-mount)
   - Phase 2 : Liste datasets
   - Phase 3 : Probe (mount temp + scan + umount)
   - Phase 4 : Résultat agrégé

4. **Stratégie de montage**
   - Système live vs montages fsdeploy
   - Workflow 5 étapes (détection → propositions → vérification → montage → vérification post)

5. **Flux de données complet** — Du boot au stream
   - 8 étapes : boot → détection → montages → kernel → presets → cohérence → ZBM → reboot
   - Deux chemins finaux : boot OS normal OU stream YouTube

**Format** : ASCII art pour compatibilité maximale

---

## 📚 Documents de référence (existants)

### fsdeploy_main_status.md (18K)
**Rapport de vérification** — État de la branche main

**Contenu** :
- Statut : COMPLET ET PRODUCTION-READY
- Métriques : 68 fichiers, 4870 lignes, 45/45 imports OK, 3/3 tests OK
- Architecture complète (8 sections)
- CLEANUP.md (fichiers à supprimer)

---

### DOCUMENTATION_SUMMARY.md (11K)
**Récapitulatif des améliorations** — Vue d'ensemble

**Contenu** :
- Documents produits (5)
- Améliorations clés (3)
- Statistiques (~2450 lignes)
- Intégration dans le dépôt
- Points clés vérifiés

---

## 📚 Documents obsolètes (à archiver)

Ces documents ont été remplacés par les nouveaux :

- ~~MOUNTPOINT_ANALYSIS.md~~ (12K) → remplacé par **IMPORT_VS_MOUNT.md**
- ~~ZFS_MOUNTPOINT_VS_MANUAL.md~~ (13K) → remplacé par **IMPORT_VS_MOUNT.md**
- ~~fix_mounts_conflicts.md~~ (7.3K) → intégré dans **MOUNTING_STRATEGY.md**
- ~~SESSION_SUMMARY.md~~ (4.6K) → remplacé par **FINAL_RECAP.md**

**Action recommandée** : déplacer dans `docs/archive/`

---

## 🗂️ Organisation recommandée du dépôt

```
fsdeploy/
├── README.md                          # Doc principale (à créer avec DIAGRAMS intégrés)
│
├── docs/
│   ├── FINAL_RECAP.md                 # ⭐ Récapitulatif de toutes les réponses
│   ├── IMPORT_VS_MOUNT.md             # Import pools vs mount manuel
│   ├── ADVANCED_DETECTION.md          # Détection multi-stratégie
│   ├── MOUNTING_STRATEGY.md           # Stratégie de montage
│   ├── DIAGRAMS.md                    # 5 diagrammes ASCII
│   ├── DOCUMENTATION_SUMMARY.md       # Vue d'ensemble améliorations
│   ├── fsdeploy_main_status.md        # État branche main
│   │
│   └── archive/                       # Documents obsolètes
│       ├── MOUNTPOINT_ANALYSIS.md
│       ├── ZFS_MOUNTPOINT_VS_MANUAL.md
│       ├── fix_mounts_conflicts.md
│       └── SESSION_SUMMARY.md
│
├── CONTRIBUTING.md                    # Guide contribution (à créer)
├── CHANGELOG.md                       # Historique versions (à créer)
├── LICENSE                            # MIT
│
├── fsdeploy/                          # Code Python
├── lib/                               # Modules
├── etc/                               # Configs
├── launch.sh                          # Bootstrap
└── requirements.txt                   # Dépendances
```

---

## 🎯 Guide de lecture

### Pour comprendre rapidement

1. **FINAL_RECAP.md** (16K) — Toutes les réponses en un seul document
2. **DIAGRAMS.md** (40K) — Visualisation complète de l'architecture

### Pour approfondir un sujet

- **Import vs mount** → **IMPORT_VS_MOUNT.md** (14K)
- **Détection avancée** → **ADVANCED_DETECTION.md** (27K)
- **Montage strategy** → **MOUNTING_STRATEGY.md** (15K)

### Pour développer

- **État du code** → **fsdeploy_main_status.md** (18K)
- **Vue d'ensemble** → **DOCUMENTATION_SUMMARY.md** (11K)

---

## 📊 Statistiques globales

```
Documents principaux (nouveaux)  : 5 docs, ~112K, ~2450 lignes
Documents référence (existants)  : 2 docs,  ~29K, ~650 lignes
Documents obsolètes (à archiver) : 4 docs,  ~47K, ~1000 lignes

TOTAL documentation utile        : 7 docs, ~141K, ~3100 lignes
```

---

## ✅ Checklist complète

### Questions posées ✅
- [x] Import mountpoint et mount manuel — aucun PB ?
- [x] Détection de rôle par scan de fichiers et structure
- [x] Identification des partitions
- [x] Recherche kernels doublons par MD5 et tri
- [x] Test des squashfs et scan pour identification
- [x] Graphiques descriptifs pour README

### Documentation produite ✅
- [x] FINAL_RECAP.md (récapitulatif complet)
- [x] IMPORT_VS_MOUNT.md (600 lignes)
- [x] ADVANCED_DETECTION.md (550 lignes)
- [x] MOUNTING_STRATEGY.md (450 lignes)
- [x] DIAGRAMS.md (5 diagrammes ASCII)
- [x] DOCUMENTATION_SUMMARY.md (vue d'ensemble)

### Code fourni ✅
- [x] Algorithmes de détection (ROLE_PATTERNS)
- [x] Scan magic bytes (signatures binaires)
- [x] Déduplication MD5 kernels
- [x] Validation squashfs
- [x] Scoring agrégé
- [x] Montage canonique

### Diagrammes créés ✅
- [x] Architecture globale
- [x] Pipeline Event → Intent → Task
- [x] Workflow de détection
- [x] Stratégie de montage
- [x] Flux de données complet

---

## 🚀 Prochaines étapes

1. **Intégrer les diagrammes** dans le README principal
2. **Créer README.md final** avec tous les schémas
3. **Archiver** les documents obsolètes
4. **Commit Git** avec message descriptif
5. **Push sur GitHub** branche main ou docs/update

---

## 📝 Notes importantes

### Import pools
**Clé** : `zpool import -N` → aucun montage auto  
**Bug ZFS** : `zfs mount` échoue pour `mountpoint=legacy`  
**Solution** : `mount -t zfs <dataset> <mountpoint>` toujours

### Détection
**Stratégie** : Multi-signaux (pattern 40% + magic 30% + content 20%)  
**MD5 kernels** : Détection doublons automatique  
**Squashfs** : Triple validation (magic + mount + contenu)

### Montage
**Isolation** : Tout dans `/mnt/`, jamais dans `/boot` du live  
**Vérification** : Toujours via `/proc/mounts` (source de vérité)  
**Thread-safe** : Locks sur tous montages/démontages

---

**Index fsdeploy Documentation v2.0**  
**Statut** : ✅ COMPLET  
**Date** : 21 mars 2026

---

## 📧 Contact

**Questions / Issues** : https://github.com/newicody/fsdeploy/issues  
**Discussions** : https://github.com/newicody/fsdeploy/discussions  
**Pull Requests** : https://github.com/newicody/fsdeploy/pulls
