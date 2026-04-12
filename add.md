# add.md — Action 3.4 : Passer log_dir à setup_logging()

**Date** : 2026-04-12

---

## Problème

`log.py` accepte `log_dir` et `util/logging.py` a un `RotatingFileHandler` complet. Mais `__main__.py._setup_logging()` appelle :

```python
setup_logging(level=..., verbose=..., debug=..., quiet=...)
```

Sans `log_dir` → les logs ne vont jamais sur disque.

`_build_daemon_config()` construit bien `"log": {"dir": ...}` mais ce n'est pas exploité par `_setup_logging()`.

---

## Correction

Dans `fsdeploy/fsdeploy/__main__.py`, modifier `_setup_logging()` :

```python
def _setup_logging():
    log_dir = ""
    if state.config:
        log_dir = state.config.get("log.dir", "")
    try:
        from log import setup_logging
        setup_logging(
            level=state.log_level,
            verbose=state.verbose,
            debug=state.debug,
            quiet=state.quiet,
            log_dir=log_dir,
        )
    except ImportError:
        import logging
        level = getattr(logging, state.log_level.upper(), logging.INFO)
        logging.basicConfig(level=level, format="%(levelname)s: %(message)s")
```

---

## Fichier Aider

```
fsdeploy/fsdeploy/__main__.py
```

---

## Après

Phase 3 terminée. Prochaine : **Phase 4** (intégration init/).
