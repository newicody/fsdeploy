# add.md — Action 3.1 : Mode recovery (`--recovery`)

**Date** : 2026-04-12

---

## Objectif

Ajouter une sous-commande `python3 -m fsdeploy --recovery` qui lance un diagnostic complet et propose des réparations. Pas de TUI complète, juste un workflow linéaire : health-check → coherence → propositions de fix → exécution.

---

## Implémentation

### 1. `__main__.py` — ajouter sous-commande `recovery`

```python
@app.command()
def recovery(
    auto_fix: bool = typer.Option(False, "--fix", "-f", help="Appliquer les corrections."),
    pool: Optional[str] = typer.Option(None, "--pool", "-p"),
):
    """Diagnostic et réparation du système."""
```

La commande enchaîne :
1. `HealthCheckTask` → vérifie ZFS/sudo/espace
2. `CoherenceCheckTask(quick_mode=True)` → vérifie pools/datasets/montages
3. Affiche le rapport
4. Si `--fix` : applique les corrections proposées

### 2. `lib/function/recovery/diagnose.py` (nouveau)

`RecoveryDiagnoseTask` : orchestre health + coherence et produit un rapport structuré avec actions correctrices proposées.

---

## Fichiers Aider

```
fsdeploy/fsdeploy/__main__.py
fsdeploy/lib/function/recovery/__init__.py
fsdeploy/lib/function/recovery/diagnose.py
```

---

## Après

3.1 terminé. Prochaine : **3.2** (métriques de performance).
