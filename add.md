# add.md — 17.1 : SecurityResolver — niveaux + intégration executor

## Problème

Le `SecurityResolver` existe mais n'est **jamais appelé** par l'executor. Les tasks s'exécutent sans aucune vérification de sécurité. La section `[security]` de la config est vide.

## A. Modifier `fsdeploy/lib/scheduler/security/resolver.py`

Ajouter les 4 niveaux de sécurité nommés dans `_check_config_rules()` :

```python
# Dans _check_config_rules, remplacer le bloc existant par :

SECURITY_LEVELS = ("allow", "deny", "require_sudo", "dry_run_only")

def _check_config_rules(self, sec_path, task, context):
    if not self.config:
        return True, None
    try:
        security_section = self.config.get("security", {})
        # Chercher une regle pour ce path exact ou un parent
        # Ex: sec_path = "dataset.snapshot" cherche "dataset.snapshot" puis "dataset"
        rule = None
        parts = sec_path.split(".")
        for i in range(len(parts), 0, -1):
            key = ".".join(parts[:i])
            if key in security_section:
                rule = security_section[key]
                break
        if rule is None:
            return True, None  # pas de regle = allow

        # Normaliser
        if isinstance(rule, dict):
            level = rule.get("level", "allow")
        else:
            level = str(rule).strip().lower()

        if level == "deny":
            return False, f"Denied by config: {sec_path}"
        elif level == "require_sudo":
            if not self._check_privilege():
                return False, f"Requires sudo: {sec_path}"
        elif level == "dry_run_only":
            dry_run = context.get("dry_run", False)
            if not dry_run:
                return False, f"Allowed only in dry-run mode: {sec_path}"
        # "allow" ou inconnu = autorise
    except Exception:
        pass
    return True, None
```

## B. Modifier `fsdeploy/lib/scheduler/core/executor.py`

Ajouter un appel au resolver **avant** l'exécution dans la méthode `execute()`. Ajouter le resolver en paramètre du constructeur.

Dans `__init__` ajouter :
```python
self.resolver = None
try:
    from fsdeploy.lib.scheduler.security.resolver import SecurityResolver
    self.resolver = SecurityResolver(config=getattr(runtime, 'config', None))
except ImportError:
    pass
```

Dans `execute()`, avant le bloc d'exécution, ajouter :
```python
# Security check
if self.resolver is not None:
    ctx = {"dry_run": getattr(self.runtime, "dry_run", False)}
    allowed, reason = self.resolver.check(task, ctx)
    if not allowed:
        task.status = "denied"
        self._emit_task_event(task, "denied", error=reason)
        return
```

## C. Modifier `fsdeploy/etc/fsdeploy.conf`

Remplir la section `[security]` avec des exemples par défaut :

```ini
[security]
    # Niveaux : allow, deny, require_sudo, dry_run_only
    dataset.destroy = require_sudo
    dataset.create = allow
    dataset.snapshot = allow
    pool.import = allow
    pool.export = require_sudo
    kernel.compile = allow
    kernel.install = require_sudo
    service.install = require_sudo
    stream.start = allow
    zbm.install = require_sudo
```

## Critères

1. `grep "SECURITY_LEVELS\|dry_run_only\|require_sudo" fsdeploy/lib/scheduler/security/resolver.py` → les 4 niveaux présents
2. `grep "resolver.check\|SecurityResolver" fsdeploy/lib/scheduler/core/executor.py` → resolver appelé dans execute()
3. `grep "dataset.destroy\|require_sudo" fsdeploy/etc/fsdeploy.conf` → règles par défaut présentes
4. Le resolver ne bloque PAS quand `bypass=True` (mode existant)
