"""
Interface en ligne de commande pour fsdeploy.
"""
import json
import sys
import typer

# Import des classes Intent disponibles
from fsdeploy.lib.intents.zfsbootmenu_intent import ZFSBootMenuIntegrateIntent
from fsdeploy.lib.intents.kernel_module_intent import (
    KernelModuleDetectIntent,
    KernelModuleIntegrateIntent,
)
from fsdeploy.lib.intents.init_upstart_sysv_intent import (
    UpstartSysvInstallIntent,
    UpstartSysvTestIntent,
)
from fsdeploy.lib.intents.init_boot_config_intent import InitBootConfigIntent
from fsdeploy.lib.intents.integration_intent import IntegrationTestIntent
from fsdeploy.lib.intents.system_intent import InitDetectIntent, CoherenceCheckIntent
from fsdeploy.lib.intents.kernel_mainline_intent import KernelMainlineDetectIntent
# Ajoutez ici d'autres intents au besoin

app = typer.Typer()

# Mapping des noms d'intents vers les classes
_INTENT_MAP = {
    "zfsbootmenu.integrate": ZFSBootMenuIntegrateIntent,
    "kernel.module.detect": KernelModuleDetectIntent,
    "kernel.module.integrate": KernelModuleIntegrateIntent,
    "init.upstart_sysv.install": UpstartSysvInstallIntent,
    "init.upstart_sysv.test": UpstartSysvTestIntent,
    "init.boot.config": InitBootConfigIntent,
    "integration.test": IntegrationTestIntent,
    "init.detect": InitDetectIntent,
    "coherence.check": CoherenceCheckIntent,
    "kernel.mainline.detect": KernelMainlineDetectIntent,
}

@app.command()
def run_intent(
    intent: str = typer.Argument(..., help="Nom de l'intent (ex: 'zfsbootmenu.integrate')"),
    params: str = typer.Option("{}", help="Paramètres JSON pour l'intent."),
    dry_run: bool = typer.Option(False, help="Simuler l'exécution sans modifier le système."),
):
    """Exécute un intent avec les paramètres fournis."""
    try:
        params_dict = json.loads(params)
    except json.JSONDecodeError as e:
        typer.echo(f"Erreur de décodage JSON: {e}", err=True)
        sys.exit(1)

    # Ajouter dry_run aux paramètres
    params_dict["dry_run"] = dry_run

    if intent not in _INTENT_MAP:
        typer.echo(f"Intent non reconnu : {intent}", err=True)
        typer.echo(f"Intents disponibles : {', '.join(sorted(_INTENT_MAP.keys()))}")
        sys.exit(1)

    intent_class = _INTENT_MAP[intent]
    # Créer l'instance d'intent avec les paramètres
    intent_instance = intent_class(id=intent, params=params_dict, context={})
    # Construire les tâches
    tasks = intent_instance.build_tasks()
    # Exécuter chaque tâche
    for task in tasks:
        typer.echo(f"Exécution de la tâche : {task.id}")
        try:
            result = task.execute()
            typer.echo(f"Résultat : {json.dumps(result, indent=2, default=str)}")
        except Exception as e:
            typer.echo(f"Erreur lors de l'exécution : {e}", err=True)
            sys.exit(1)

    typer.echo("Intent exécuté avec succès.")

@app.command()
def list_intents():
    """Lister tous les intents disponibles."""
    typer.echo("Intents disponibles :")
    for name in sorted(_INTENT_MAP.keys()):
        typer.echo(f"  - {name}")

if __name__ == "__main__":
    app()
