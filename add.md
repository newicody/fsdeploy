# add.md — P0-cleanup : 10.1 + 16.51 + 16.52

---

## Fix 1 — 10.1 : Unicode cassé dans `detection.py`

**Fichier** : `fsdeploy/lib/ui/screens/detection.py`

**Problème** : les constantes `CHECK`, `CROSS`, `WARN`, `ARROW` contiennent des codepoints Unicode sous forme de texte brut (`"2705"`, `"274c"`, `"26a0Fe0f"`, `"2192"`) au lieu d'échappements `\uXXXX`. La TUI affiche littéralement `2705` au lieu de ✅.

**Ce qu'il faut** : utiliser la syntaxe `\uXXXX` (convention du projet : ASCII dans le source, Unicode via escape). Tous les autres écrans le font correctement — voir `mounts.py` (`"\u2705"`), `zbm.py`/`presets.py`/`initramfs.py` (littéraux `"✅"`), `welcome.py` (littéraux). Aligner `detection.py` sur le même style.

---

## Fix 2 — 16.51 : `boot_intent.py` est une copie de `detection_intent.py`

**Fichiers** : `fsdeploy/lib/intents/boot_intent.py`, `fsdeploy/lib/intents/detection_intent.py`

**Problème** : `boot_intent.py` contient exactement le même code que `detection_intent.py` — même docstring (`fsdeploy.intents.detection_intent`), mêmes tasks (`PoolImportAllTask`, `DatasetProbeTask`, etc.), mêmes intents (`pool.import_all`, `pool.import`, `mount.request`, `detection.start`, etc.). Le dernier importé par `intents/__init__.py` écrase silencieusement le premier.

**Ce qu'il faut** : `boot_intent.py` devrait contenir uniquement les intents liés au boot/ZBM (qui ne sont PAS dans `detection_intent.py`). Les intents boot/ZBM pertinents sont dans `kernel_intent.py` (`boot.init.generate`, `zbm.validate`) et `system_intent.py` (`zbm.install`, `zbm.status`). 

Donc soit :
- Vider `boot_intent.py` et y mettre uniquement les intents boot spécifiques qui ne sont pas déjà ailleurs (s'il y en a)
- Soit supprimer `boot_intent.py` entièrement si tous ses intents légitimes sont déjà couverts par d'autres fichiers, et retirer l'import de `intents/__init__.py`

Le contenu dupliqué (pool/mount/detection) doit rester **uniquement** dans `detection_intent.py`.

---

## Fix 3 — 16.52 : Doublon `init.config.detect`

**Fichiers** : `fsdeploy/lib/intents/init_intent.py`, `fsdeploy/lib/intents/init_config_intent.py`

**Problème** : `init.config.detect` est enregistré via `@register_intent` dans les deux fichiers. Le second écrase le premier.

**Ce qu'il faut** : garder la définition dans `init_intent.py` (c'est là que tous les autres intents `init.*` sont définis). Supprimer le `@register_intent("init.config.detect")` de `init_config_intent.py`. Si le fichier est vide après, le supprimer et retirer son import de `intents/__init__.py`.

---

## Critères d'acceptation

1. DetectionScreen affiche ✅ / ❌ / ⚠️ / → (pas de texte brut `2705`)
2. `boot_intent.py` ne contient plus les mêmes classes que `detection_intent.py`
3. `grep -r "init.config.detect" fsdeploy/lib/intents/` → une seule occurrence dans `init_intent.py`
4. `cd fsdeploy/lib && python3 test_run.py` → 3/3 pass
