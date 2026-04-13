#!/usr/bin/env python3
"""
Vérifie qu'aucun fichier Python n'importe depuis tests.fsdeploy.
"""
import os
import re
import sys

def find_py_files(root="."):
    for dirpath, dirnames, filenames in os.walk(root):
        # Ignorer certains dossiers
        if any(x in dirpath for x in (".git", "__pycache__", "tests/fsdeploy")):
            continue
        for fname in filenames:
            if fname.endswith(".py"):
                yield os.path.join(dirpath, fname)

def check_imports(filepath):
    pattern = r"^\s*(import|from)\s+tests\.fsdeploy"
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        for i, line in enumerate(f, 1):
            if re.match(pattern, line):
                return (i, line.strip())
    return None

def main():
    errors = []
    for pyfile in find_py_files():
        issue = check_imports(pyfile)
        if issue:
            errors.append((pyfile, issue[0], issue[1]))
    if errors:
        print("❌ Des imports vers tests.fsdeploy ont été trouvés :")
        for file, line_num, line_content in errors:
            print(f"   {file}:{line_num} -> {line_content}")
        sys.exit(1)
    else:
        print("✅ Aucun import problématique trouvé.")
        sys.exit(0)

if __name__ == "__main__":
    main()
