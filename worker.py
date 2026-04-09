import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime

# =========================
# CONFIG
# =========================
AIDER_CMD = "aider"
AIDER_MODEL = "deepseek/deepseek-reasoner"

AUTO_STAGE_ALL = True
DEFAULT_BRANCH = "dev"

INTERACTIVE = True


# =========================
# ROOT DETECTION (CRITIQUE)
# =========================
def get_git_root():
    result = subprocess.run(
        "git rev-parse --show-toplevel",
        shell=True,
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError("Pas dans un repo Git")

    return Path(result.stdout.strip())


BASE_DIR = get_git_root()
PLAN_FILE = BASE_DIR / "PLAN.md"
STATE_FILE = BASE_DIR / "STATE.json"


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
# SHELL (STRICT)
# =========================
def run(cmd, check=True):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

    if result.returncode != 0:
        log(result.stderr.strip(), "ERROR")
        if check:
            raise RuntimeError(f"Commande échouée: {cmd}")

    return result


# =========================
# GIT HELPERS
# =========================
def git_has_changes():
    return bool(run("git status --porcelain").stdout.strip())


def git_has_stash():
    return bool(run("git stash list").stdout.strip())


def git_restore_stash():
    log("♻️ Restauration stash")
    result = run("git stash pop", check=False)

    if result.returncode != 0:
        log("⚠️ Conflits après stash pop", "ERROR")
        input("Résous les conflits puis appuie sur Entrée...")


def git_changed_files():
    result = run("git status --porcelain")

    files = []
    for line in result.stdout.split("\n"):
        if line.strip():
            files.append(line[3:])

    return files


def git_diff():
    return run("git diff").stdout


# =========================
# GIT CORE
# =========================
def git_check_auth():
    log("Test auth Git...")

    result = run("git ls-remote", check=False)

    if result.returncode != 0:
        log("❌ Auth Git échouée", "ERROR")
        raise RuntimeError("Git auth failed")

    log("✅ Auth Git OK")


def git_set_upstream(branch):
    result = run(f"git branch --set-upstream-to=origin/{branch} {branch}", check=False)

    if result.returncode != 0:
        log("Création upstream")
        run(f"git push -u origin {branch}")


def git_checkout(branch):
    log(f"Checkout branche: {branch}")

    # Vérifier si la branche existe localement
    result = run(f"git rev-parse --verify {branch}", check=False)
    if result.returncode == 0:
        run(f"git checkout {branch}")
    else:
        # Vérifier si la branche existe sur l'origine
        result_remote = run(f"git ls-remote --heads origin {branch}", check=False)
        if result_remote.returncode == 0 and result_remote.stdout.strip():
            # branche distante existe
            run(f"git checkout -b {branch} origin/{branch}")
        else:
            # créer nouvelle branche locale sans tracking
            run(f"git checkout -b {branch}")

    git_set_upstream(branch)


def git_pull(branch):
    log("Git pull (SAFE)")

    stash_created = False

    try:
        if git_has_changes():
            log("⚠️ stash auto", "WARNING")
            run("git stash push -u -m 'auto-stash'")
            stash_created = True

        result = run(f"git pull --no-rebase origin {branch}", check=False)

        if result.returncode != 0:
            log("❌ conflit Git → abort", "ERROR")

            run("git merge --abort", check=False)
            run("git rebase --abort", check=False)

            raise RuntimeError("Git pull failed")
    finally:
        if stash_created:
            git_restore_stash()


def git_commit(branch):
    result = run("git diff --cached --quiet", check=False)

    if result.returncode == 0:
        log("Rien à commit")
        return False

    run(f'git commit -m "auto: {branch} update"')
    return True


def git_push(branch):
    if not git_has_changes():
        log("Aucun changement à commit")
        return

    if AUTO_STAGE_ALL:
        run("git add .")

    git_commit(branch)

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
# AIDER
# =========================
def run_aider(files, task=None):
    if not files:
        log("Aucun fichier → fallback manuel", "WARNING")
        files = input("Fichiers pour aider: ").split()

    if not files:
        log("Abort aider", "ERROR")
        return

    log(f"Aider ({AIDER_MODEL}) → {files}")

    prompt = task or "Implémente la tâche proprement."

    cmd = (
        f'{AIDER_CMD} '
        f'--model {AIDER_MODEL} '
        f'--message "{prompt}" '
        f'{" ".join(files)}'
    )

    result = subprocess.run(cmd, shell=True)

    if result.returncode != 0:
        log("Fallback aider")
        subprocess.run(f"{AIDER_CMD} {' '.join(files)}", shell=True)


# =========================
# PLAN
# =========================
def mark_done(task):
    if not PLAN_FILE.exists():
        return

    content = PLAN_FILE.read_text()

    lines = content.splitlines()

    new_lines = []
    for line in lines:
        if task.lower() in line.lower() and "- [ ]" in line:
            line = line.replace("- [ ]", "- [x]")
        new_lines.append(line)

    PLAN_FILE.write_text("\n".join(new_lines))


def check_aider_installed():
    """Vérifie que aider est disponible dans PATH."""
    result = run(f"which {AIDER_CMD}", check=False)
    if result.returncode != 0:
        log(f"⚠️ {AIDER_CMD} non trouvé dans PATH", "WARNING")
        # Optionnel: proposer d'installer avec pipx
        return False
    log(f"✅ {AIDER_CMD} est installé")
    return True

# =========================
# UTILS
# =========================
def ask_continue(msg):
    if not INTERACTIVE:
        log(f"{msg} (auto: yes)")
        return True
    return input(f"{msg} (y/n): ").lower() == "y"


def ensure_project():
    if not PLAN_FILE.exists():
        log("Création PLAN.md")
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
        git_check_auth()
        git_checkout(branch)
        git_pull(branch)

        # Vérifier que aider est disponible
        if not check_aider_installed():
            log("Continuer sans aider ?", "WARNING")
            if not ask_continue("Aider non trouvé, continuer ?"):
                raise RuntimeError("Aider requis")

        request_claude(task)

        log("Vérifie PLAN.md")

        if not ask_continue("Continuer ?"):
            return

        files = git_changed_files()
        log(f"Fichiers: {files}")

        run_aider(files, task)

        log("Diff:")
        print(git_diff())

        if not ask_continue("Valider ?"):
            return

        mark_done(task)
        git_push(branch)

        log("➡️ Informe Claude")
        input("Entrée pour continuer...")

        state["status"] = "DONE"
        save_state(state)

        log("✅ Terminé")

    except Exception as e:
        log(f"Erreur: {e}", "ERROR")
        state["status"] = "ERROR"
        save_state(state)


# =========================
# MAIN
# =========================
if __name__ == "__main__":
    if "--auto" in sys.argv:
        sys.argv.remove("--auto")
        INTERACTIVE = False

    task = input("🧾 Nouvelle tâche: ").strip()
    branch = input(f"🌿 Branche ({DEFAULT_BRANCH}): ").strip() or DEFAULT_BRANCH

    if task:
        run_pipeline(task, branch)
