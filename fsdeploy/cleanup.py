#!/usr/bin/env python3
"""
fsdeploy cleanup — Nettoyage complet du repository.

Ce script :
  1. Supprime les scripts de patch manuels (fix-all.sh, patch.py)
  2. Supprime les doublons identifiés dans CLEANUP.md
  3. Supprime les fichiers de documentation obsolètes
  4. Corrige self.name dans tous les écrans (Textual 8.x breaking)
  5. Supprime poetry.lock (fichier ZFSBootMenu, pas fsdeploy)
  6. Vérifie la cohérence du repository

Usage :
    cd /opt/fsdeploy
    python3 cleanup.py              # dry-run (affiche sans modifier)
    python3 cleanup.py --apply      # applique les changements
"""

import os
import re
import sys
from pathlib import Path

DRY_RUN = "--apply" not in sys.argv

# ═══════════════════════════════════════════════════════════════════════════════
# 1. FICHIERS À SUPPRIMER
# ═══════════════════════════════════════════════════════════════════════════════

FILES_TO_DELETE = [
    # ── Scripts de patch manuels ──────────────────────────────────────────
    "fix-all.sh",                              # correctifs post-bootstrap
    "patch.py",                                # patch self.name

    # ── Doublons identifiés (CLEANUP.md) ──────────────────────────────────
    "fsdeploy/lib/ARCHITECTURE.py",            # remplacé par roadmap.md
    "lib/ARCHITECTURE.py",                     # idem (chemin alternatif)
    "fsdeploy/lib/scheduler/intentlog/huffman.py",  # stub vide
    "lib/scheduler/intentlog/huffman.py",            # idem
    "fsdeploy/lib/scheduler/core/intent.py",   # doublon → model/intent.py
    "lib/scheduler/core/intent.py",            # idem
    "fsdeploy/lib/bus/init.py",                # doublon → bus/__init__.py
    "lib/bus/init.py",                         # idem
    "fsdeploy/lib/function/pool/import.py",    # stub vide
    "lib/function/pool/import.py",             # idem

    # ── Fichiers obsolètes ────────────────────────────────────────────────
    "CLEANUP.md",                              # travail fait → supprimer
    "FINAL_STATUS.md",                         # doc de session, pas de repo
    "COMMIT_MESSAGE.md",                       # usage unique terminé
    "INTEGRATION.md",                          # intégration faite
    "FILES.md",                                # liste obsolète
    "MASTER_INDEX.md",                         # index obsolète
    "MIGRATION_TEXTUAL_8.md",                  # migration faite
    "SESSION_FINAL.md",                        # doc de session
    "roadmap.md",                              # historique, plus utile

    # ── poetry.lock (fichier ZFSBootMenu, pas fsdeploy) ───────────────────
    "poetry.lock",
]


# ═══════════════════════════════════════════════════════════════════════════════
# 2. SELF.NAME À SUPPRIMER DANS LES SCREENS
# ═══════════════════════════════════════════════════════════════════════════════

SCREEN_DIRS = [
    "fsdeploy/lib/ui/screens",
    "lib/ui/screens",
    "ui/screens",
]

SELF_NAME_PATTERN = re.compile(r"^\s*self\.name\s*=\s*[\"'][^\"'\n]*[\"']\s*;?\s*", re.MULTILINE)
# Cas inline : super().__init__(**kw); self.name="kernel"; ...
SELF_NAME_INLINE = re.compile(r";\s*self\.name\s*=\s*[\"'][^\"'\n]*[\"']")


def fix_screen_self_name(filepath: Path) -> bool:
    """Supprime self.name = '...' d'un fichier screen. Retourne True si modifié."""
    text = filepath.read_text(encoding="utf-8")
    original = text

    # Supprimer les assignations inline (ex: super().__init__(**kw); self.name="kernel"; ...)
    text = SELF_NAME_INLINE.sub("", text)
    # Supprimer les lignes complètes self.name = "..."
    text = SELF_NAME_PATTERN.sub("", text)
    # Nettoyer les lignes vides doublées
    text = re.sub(r"\n{3,}", "\n\n", text)

    if text != original:
        if not DRY_RUN:
            filepath.write_text(text, encoding="utf-8")
        return True
    return False


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    repo = Path(".")
    if not (repo / "launch.sh").exists() and not (repo / "fsdeploy").is_dir():
        print("ERREUR: Lancez ce script depuis la racine du repo fsdeploy")
        sys.exit(1)

    mode = "DRY-RUN" if DRY_RUN else "APPLY"
    print(f"\n{'='*60}")
    print(f"  fsdeploy cleanup — mode {mode}")
    print(f"{'='*60}\n")

    # ── 1. Suppression de fichiers ────────────────────────────────────────
    print("1. Fichiers à supprimer :")
    deleted = 0
    for rel in FILES_TO_DELETE:
        path = repo / rel
        if path.exists():
            print(f"   DEL  {rel}")
            if not DRY_RUN:
                path.unlink()
            deleted += 1
        # Pas de message si le fichier n'existe pas (chemin alternatif)

    print(f"   → {deleted} fichier(s) {'à supprimer' if DRY_RUN else 'supprimé(s)'}\n")

    # ── 2. Fix self.name dans les screens ─────────────────────────────────
    print("2. Correction self.name (Textual 8.x) :")
    fixed = 0
    for screen_dir in SCREEN_DIRS:
        sd = repo / screen_dir
        if not sd.is_dir():
            continue
        for py_file in sorted(sd.glob("*.py")):
            if fix_screen_self_name(py_file):
                print(f"   FIX  {py_file.relative_to(repo)}")
                fixed += 1

    print(f"   → {fixed} fichier(s) {'à corriger' if DRY_RUN else 'corrigé(s)'}\n")

    # ── 3. Vérification .gitignore ────────────────────────────────────────
    print("3. Vérification .gitignore :")
    gitignore = repo / ".gitignore"
    if gitignore.exists():
        lines = gitignore.read_text().splitlines()
        bad_lines = []
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            # lib/ ignore tout le code Python !
            if stripped == "lib/" or stripped == "lib":
                bad_lines.append((i, line))
            # var/ ignore var/lib/fsdeploy etc.
            elif stripped == "var/":
                bad_lines.append((i, line))

        if bad_lines:
            for lineno, line in bad_lines:
                print(f"   WARN  Ligne {lineno}: '{line}' — ignore du code fsdeploy !")
            print("   → Remplacer .gitignore par la version corrigée")
        else:
            print("   OK")
    print()

    # ── 4. Vérification pyproject.toml ────────────────────────────────────
    print("4. Vérification pyproject.toml :")
    pyproject = repo / "pyproject.toml"
    if pyproject.exists():
        content = pyproject.read_text()
        issues = []
        if "textual-web" in content:
            issues.append("textual-web (obsolète)")
        if 'textual>=0.43.0' in content:
            issues.append("textual>=0.43.0 (devrait être >=8.2.1)")
        if issues:
            print(f"   WARN  Dépendances obsolètes : {', '.join(issues)}")
            print("   → Remplacer pyproject.toml par la version corrigée")
        else:
            print("   OK")
    print()

    # ── Résumé ────────────────────────────────────────────────────────────
    print(f"{'='*60}")
    if DRY_RUN:
        print("  DRY-RUN terminé. Relancer avec --apply pour appliquer.")
    else:
        print("  Nettoyage terminé.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
