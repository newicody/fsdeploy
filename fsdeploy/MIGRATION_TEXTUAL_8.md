# MIGRATION — Textual 8.2.1 / Rich 14.3.3 / textual-dev 1.8.0
# ==============================================================
# Date : 03 avril 2026
# Cible : fsdeploy main branch

---

## 1. CHANGEMENTS CRITIQUES (breaking)

### 1.1 requirements.txt — REFAIT
- `textual-web>=0.5.0` → `textual>=8.2.1` (dépendance directe)
- `rich>=13.0.0` → `rich>=14.3.3` (Textual 8.x exige >=14.2.0)
- Ajout `textual-dev>=1.8.0` (remplace textual-web pour `textual serve`)
- Ajout `platformdirs>=3.6.0` (nouvelle dépendance Textual 8.x)
- `structlog>=23.0.0` → `>=24.0.0` (plus récent, API stable)

### 1.2 Select.BLANK → Select.NULL
- **Fichier** : `lib/ui/screens/presets.py`
- **Impact** : `Select.BLANK` renommé `Select.NULL` dans Textual 8.x
- **Correctif** : Ajouter compatibilité :
  ```python
  _SELECT_BLANK = getattr(Select, "NULL", getattr(Select, "BLANK", None))
  ```

### 1.3 OptionList.Separator supprimé
- **Impact** : `OptionList` n'accepte plus `Separator` comme entrée
- **Correctif** : Utiliser `None` pour les séparateurs
- **Fichiers touchés** : Aucun dans le code actuel (non utilisé)

### 1.4 DataTable — comportement Selected modifié
- **Impact** : `DataTable` n'émet `*Selected` qu'au 2ème clic (pas au 1er)
- **Fichiers** : detection.py, mounts.py, kernel.py, snapshots.py, presets.py
- **Correctif** : Utiliser `on_data_table_row_highlighted` au lieu de
  `on_data_table_row_selected` pour la sélection au premier clic

### 1.5 query_one breadth-first
- **Impact** : `query_one` cherche en largeur d'abord au lieu de profondeur
- **Correctif** : Aucun nécessaire — le code utilise des IDs uniques (#xxx)

---

## 2. CHANGEMENTS LAUNCH.SH

### 2.1 Dépendance textual-web → textual + textual-dev
- `textual-web` n'est plus le point d'entrée
- `textual serve` (fourni par textual-dev) remplace `textual-web --app`
- Le venv installe maintenant `textual` directement

### 2.2 Mode web
- Ancien : `textual-web --app "fsdeploy:FsDeployApp" --port 8080`
- Nouveau : `textual serve "python3 -m fsdeploy" --port 8080`
- Ou via `textual-dev` : `textual run --dev fsdeploy.ui.app:FsDeployApp`

### 2.3 Cross-compilateurs
- launch.sh installe déjà tous les paquets nécessaires
- Pas de changement requis pour les cross-compilateurs

---

## 3. FICHIERS À CORRIGER

| Fichier | Correction | Priorité |
|---------|-----------|----------|
| requirements.txt | Rewrite complet | CRITIQUE |
| launch.sh | textual serve au lieu de textual-web | HAUTE |
| lib/ui/screens/presets.py | Select.BLANK→NULL compat | HAUTE |
| lib/ui/screens/detection.py | row_highlighted vs row_selected | MOYENNE |
| lib/ui/screens/mounts.py | row_highlighted vs row_selected | MOYENNE |
| lib/ui/screens/kernel.py | row_highlighted vs row_selected | MOYENNE |
| lib/ui/screens/snapshots.py | row_highlighted vs row_selected | MOYENNE |
| lib/ui/app.py | textual-web ref dans comments | BASSE |
| README.md | textual-web → textual serve dans docs | BASSE |

---

## 4. FICHIERS DÉJÀ COMPATIBLES (aucun changement)

Les APIs suivantes utilisées dans fsdeploy sont stables entre 0.43 et 8.2.1 :
- `App`, `Screen`, `ComposeResult`, `Binding`
- `Static`, `Label`, `Button`, `Input`, `Log`, `Rule`
- `DataTable` (API de base stable, seul le comportement Selected change)
- `Vertical`, `Horizontal`, `Container`, `ScrollableContainer`, `VerticalScroll`
- `Header`, `Footer`
- `reactive`, `Timer`
- `ProgressBar`
- CSS syntax (inchangée)
- `set_interval`, `set_timer`
- `push_screen`, `pop_screen`, `switch_screen`
- `notify()`
- `@on()` decorator
- `@work()` decorator

---

## 5. DOUBLONS À NETTOYER (rappel CLEANUP.md)

- `ARCHITECTURE.py` → supprimer
- `huffman.py` stub → supprimer  
- `core/intent.py` duplicate → supprimer
- `bus/init.py` duplicate → supprimer
- `ui/screens/graph.py` vs `lib/ui/screens/graph.py` → garder lib/ uniquement
- Fichiers textual-web stale : `LICENSE` MIT/Textualize, `pyproject.toml`, `poetry.lock`

---

## 6. VÉRIFICATION launch.sh

### Ce qui fonctionne bien :
- ✅ Détection Debian Live vs installé (heuristiques)
- ✅ Sources APT (contrib, non-free, backports)
- ✅ DKMS polling loop avec timeout 180s
- ✅ Groupe fsdeploy + sudoers validé visudo
- ✅ Permissions 2775 + setgid + ACL
- ✅ Git clone/pull
- ✅ Venv creation
- ✅ Mode --update avec migration config
- ✅ Mode --dev pour dépôt local
- ✅ Wrapper /usr/local/bin/fsdeploy
- ✅ .env export

### Ce qui doit changer :
- ⚠ requirements.txt tire textual-web qui tire une vieille version de textual
  → Correctif : le nouveau requirements.txt résout ce problème
- ⚠ Les commentaires README mentionnent `textual-web --app` 
  → Correctif : documenter `textual serve`
