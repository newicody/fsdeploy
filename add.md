# add.md — Action 7.0 : launch.sh — branche par défaut + freeze

**Date** : 2026-04-12

---

## Problèmes identifiés dans launch.sh

### 1. Branche par défaut = main (ligne ~20)

```bash
REPO_BRANCH="${FSDEPLOY_BRANCH:-main}"
```

Le développement actif est sur `dev`. Un utilisateur qui fait :
```bash
curl -fsSL https://raw.githubusercontent.com/newicody/fsdeploy/dev/launch.sh | bash
```
...obtient le `launch.sh` de dev, mais celui-ci clone la branche `main` car
le défaut est hardcodé. Le code Python obtenu est celui de main (ancien).

### 2. Pas de lancement automatique post-install

Après l'étape 9/9, le script affiche un message mais ne propose pas de
lancer fsdeploy. L'utilisateur doit taper manuellement le chemin du venv.

---

## Corrections

### Dans `fsdeploy/launch.sh` :

**a)** Changer le défaut de branche :
```bash
REPO_BRANCH="${FSDEPLOY_BRANCH:-dev}"
```

**b)** Ajouter une option `--run` et proposer le lancement à la fin :
```bash
# Après étape 9/9
step "Installation terminée"
ok "fsdeploy est prêt dans ${INSTALL_DIR}"
info "Lancer : ${VENV_DIR}/bin/python3 -m fsdeploy"
if [[ "${RUN_AFTER:-0}" -eq 1 ]]; then
    exec as_user "${VENV_DIR}/bin/python3" -m fsdeploy
fi
```

---

## Fichier Aider

```
fsdeploy/launch.sh
```

---

## Après

7.0 terminé. Prochaine : **7.1** (live/setup.py linux-headers dynamique).
