# PLAN — fsdeploy (branche dev)

**Dernière mise à jour** : 2026-04-12

## Phase 1–6 — ✅ TERMINÉES (TUI, robustesse, features, init, tests, cleanup)

---

## Phase 7 : Audit, launch.sh, documentation (en cours)

### 7.0 — launch.sh : branche par défaut ← PROCHAINE
**Bug** : `REPO_BRANCH="${FSDEPLOY_BRANCH:-main}"` clone toujours `main`.
Le développement actif est sur `dev` → l'utilisateur qui lance
`curl ... | bash` n'obtient jamais le code à jour.
**Fix** : Changer le défaut en `dev` ou ajouter un mécanisme de sélection
interactif quand aucune branche n'est spécifiée.
**État** : ✅ **Corrigé** (branche dev, options --run/--no-run ajoutées).

### 7.1 — live/setup.py : linux-headers-amd64 hardcodé
**Bug** : `DEBIAN_PACKAGES` contient `"linux-headers-amd64"` (meta-package).
`launch.sh` utilise correctement `linux-headers-$(uname -r)`, mais
`LiveSetupTask` non — freeze DKMS possible si le meta-package tire
un kernel différent du kernel live courant.
**Fix** : Remplacer par détection dynamique `uname -r` dans `_install_packages()`.

### 7.2 — Synchroniser tests/ avec lib/ (copies stale)
Fichiers dans `tests/fsdeploy/lib/` qui ont des imports `SchedulerBridge.default()` directs
ou des anciennes versions :
- `tests/.../cross_compile_screen.py` — ancienne version avec bridge direct
- `tests/.../moduleregistry_screen.py` — ancienne version avec bridge direct
- `tests/.../module_registry.py` — OK (déjà version complète)
- `tests/.../navigation.py` — OK (déjà corrigé)

### 7.3 — next_actions.md obsolète
Le fichier dans le repo est gelé au 2026-04-12 avec des entrées "À faire"
pour des phases déjà terminées (dry-run, health-check, MountManager...).
**Fix** : Réécrire complètement.

### 7.4 — README.md : curl install pointe vers main
```bash
curl -fsSL https://raw.githubusercontent.com/newicody/fsdeploy/main/launch.sh
```
Doit pointer vers la branche active ou mentionner `--branch dev`.

### 7.5 — DIAGRAMS.md : linux-headers-amd64 hardcodé dans schéma
Schéma ASCII référence `linux-headers-amd64` au lieu de `linux-headers-$(uname -r)`.

### 7.6 — fsdeploy_main_status.md obsolète
Daté du 21 mars 2026, ne reflète plus l'état actuel (68 fichiers → bien plus,
phases 1-6 complétées, nouvelles features).

### 7.7 — lib/function/module/registry.py : stub vide
`ModuleRegistry` dans `lib/function/module/registry.py` est un stub (`pass`).
`lib/modules/registry.py` a la version complète. Le stub dans `function/module/`
crée de la confusion — soit le supprimer, soit le convertir en re-export.