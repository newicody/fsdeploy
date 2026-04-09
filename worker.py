import os
import json
import subprocess
from pathlib import Path
from datetime import datetime

# =========================
# CONFIG
# =========================
BASE_DIR = Path("./project")

PLAN_FILE = BASE_DIR / "PLAN.md"
STATE_FILE = BASE_DIR / "STATE.json"

AIDER_CMD = "aider"
AIDER_MODEL = "deepseek/deepseek-reasoner"

AUTO_STAGE_ALL = True
DEFAULT_BRANCH = "dev"


# =========================
# LOGGER
# =========================
def log(msg, level="INFO"):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [{level}] {msg}")


# =========================
# STATE
# =========================
DEFAULT_STATE = {
    "current_task": None,
    "status": "IDLE",
    "iteration": 0
}


def load_state():
    if not STATE_FILE.exists():
        save_state(DEFAULT_STATE)
    try:
        return json.loads(STATE_FILE.read_text())
    except:
        return DEFAULT_STATE.copy()


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2))


# =========================
# SHELL
# =========================
def run(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        log(result.stderr.strip(), "ERROR")
    return result


# =========================
# GIT
# =========================
def git_check_auth():
    log("Test auth Git...")

    result = run("git ls-remote")

    if result.returncode != 0:
        log("❌ Auth Git échouée", "ERROR")
        log("➡️ Vérifie SSH ou token", "ERROR")
        exit()

    log("✅ Auth Git OK")

def git_checkout(branch):
    log(f"Checkout branche: {branch}")
    
    # vérifier si branche existe
    result = run(f"git rev-parse --verify {branch}")
    
    if result.returncode != 0:
        log(f"Création branche {branch}")
        run(f"git checkout -b {branch}")
    else:
        run(f"git checkout {branch}")


def git_pull():
    log("Git pull")
    run("git pull --rebase")


def git_has_changes():
    result = run("git status --porcelain")
    return bool(result.stdout.strip())


def git_diff():
    return run("git diff").stdout


def git_changed_files():
    result = run("git diff --name-only")
    files = result.stdout.strip().split("\n")
    return [f for f in files if f]


def git_push(branch):
    if not git_has_changes():
        log("Aucun changement à commit")
        return

    log("Git add")
    if AUTO_STAGE_ALL:
        run("git add .")

    log("Git commit")
    run(f'git commit -m "auto: {branch} update"')

    log("Git push")
    run(f"git push -u origin {branch}")


# =========================
# CLAUDE (manuel)
# =========================
def request_claude(task):
    log("➡️ ENVOIE À CLAUDE (mode projet)", "ACTION")

    print(f"""
================ CLAUDE INPUT ================

Nouvelle tâche:
{task}

Instructions:
- Met à jour PLAN.md
- Crée add.md si nécessaire
- Liste les fichiers à modifier

==============================================
""")

    input("⏸️ Appuie sur Entrée après réponse de Claude...")


# =========================
# DEEPSEEK (AIDER)
# =========================
def run_aider(files, task=None):
    if not files:
        log("Aucun fichier détecté → fallback manuel", "WARNING")
        files = input("Fichiers pour aider: ").strip().split()

    if not files:
        log("Toujours aucun fichier → abort aider", "ERROR")
        return

    log(f"DeepSeek ({AIDER_MODEL}) sur: {files}")

    prompt = task or "Implémente la tâche demandée proprement."

    cmd = (
        f'{AIDER_CMD} '
        f'--model {AIDER_MODEL} '
        f'--message "{prompt}" '
        f'{" ".join(files)}'
    )

    result = subprocess.run(cmd, shell=True)

    if result.returncode != 0:
        log("Erreur aider → fallback", "WARNING")
        subprocess.run(f"{AIDER_CMD} {' '.join(files)}", shell=True)

# =========================
# PLAN
# =========================
def mark_done(task):
    if not PLAN_FILE.exists():
        log("PLAN.md introuvable", "ERROR")
        return

    content = PLAN_FILE.read_text()

    if f"- [ ] {task}" not in content:
        log("Tâche non trouvée dans PLAN.md", "WARNING")
        return

    content = content.replace(f"- [ ] {task}", f"- [x] {task}")
    PLAN_FILE.write_text(content)

    log("Tâche marquée comme faite")


# =========================
# UTILS
# =========================
def ask_continue(msg):
    val = input(f"{msg} (y/n): ").lower()
    return val == "y"


def ensure_project():
    if not BASE_DIR.exists():
        log("Dossier project introuvable", "ERROR")
        exit()

    if not PLAN_FILE.exists():
        log("PLAN.md manquant → création")
        PLAN_FILE.write_text("# PLAN\n\n")


# =========================
# PIPELINE
# =========================
def run_pipeline(task, branch):

    ensure_project()

    state = load_state()
    state["current_task"] = task
    state["status"] = "RUNNING"
    state["iteration"] += 1
    save_state(state)

    try:
        # 0. Git auth + branche
        git_check_auth()
        git_checkout(branch)

        # 1. Sync
        git_pull()

        # 2. Claude
        request_claude(task)

        # 3. Validation humaine
        log("Vérifie PLAN.md et fichiers générés")

        if not ask_continue("Continuer ?"):
            log("Annulé", "WARNING")
            return

        # 4. Auto-détection fichiers
        files = git_changed_files()
        log(f"Fichiers détectés: {files}")

        # 5. DeepSeek
        run_aider(files, task)

        # 6. Diff
        log("Diff actuel:")
        print(git_diff())

        if not ask_continue("Valider les modifications ?"):
            log("Refusé", "WARNING")
            return

        # 7. Plan
        mark_done(task)

        # 8. Git push
        git_push(branch)

        # 9. Retour Claude
        log("➡️ Informe Claude que c'est terminé", "ACTION")
        input("Appuie sur Entrée après validation Claude...")

        state["status"] = "DONE"
        save_state(state)

        log("✅ Pipeline terminé")

    except Exception as e:
        log(f"Erreur: {e}", "ERROR")
        state["status"] = "ERROR"
        save_state(state)


# =========================
# MAIN
# =========================
if __name__ == "__main__":
    task = input("🧾 Nouvelle tâche: ").strip()
    branch = input(f"🌿 Branche (default: {DEFAULT_BRANCH}): ").strip() or DEFAULT_BRANCH

    if not task:
        print("Tâche vide.")
    else:
        run_pipeline(task, branch)
