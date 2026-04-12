# add.md — Action 7.0b : requirements.txt — retirer cryptography + séparer dev

**Date** : 2026-04-12

---

## Problème

`requirements.txt` contient :
1. `cryptography>=42.0.0` — nécessite compilateur Rust, absent sur Debian Live → pip hang 5+ min puis échec. **Aucun code runtime n'importe cryptography.**
2. `pytest`, `pytest-cov`, `pytest-asyncio`, `pytest-mock`, `black`, `isort`, `mypy` — deps dev inutiles sur Live, rallongent l'install de 2-3 min.
3. `pip install --quiet` dans launch.sh masque tout → l'utilisateur voit un freeze sans explication.

---

## Corrections

### 1. `requirements.txt` — garder uniquement runtime

Retirer :
- `cryptography>=42.0.0`
- `pytest>=7.0.0`, `pytest-cov>=4.0.0`, `pytest-asyncio>=0.23.0`, `pytest-mock>=3.12.0`
- `black>=23.0.0`, `isort>=5.12.0`, `mypy>=1.0.0`

### 2. `requirements-dev.txt` — nouveau fichier

```
# Dev/test dependencies — NOT installed on Live
-r requirements.txt
pytest>=7.0.0
pytest-cov>=4.0.0
pytest-asyncio>=0.23.0
pytest-mock>=3.12.0
black>=23.0.0
isort>=5.12.0
mypy>=1.0.0
cryptography>=42.0.0
```

### 3. `launch.sh` — pip avec timeout et progress

Remplacer :
```bash
as_user "$VENV_DIR/bin/pip" install --quiet -r "${INSTALL_DIR}/requirements.txt"
```
Par :
```bash
as_user "$VENV_DIR/bin/pip" install --timeout 120 --progress-bar on -r "${INSTALL_DIR}/requirements.txt"
```

---

## Fichiers Aider

```
fsdeploy/requirements.txt        (retirer cryptography + dev deps)
fsdeploy/requirements-dev.txt    (nouveau)
fsdeploy/launch.sh               (pip --timeout 120 --progress-bar on)
```

---

## Après

7.0b terminé. Prochaine : **7.1** (live/setup.py linux-headers dynamique).
