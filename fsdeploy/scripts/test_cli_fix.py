#!/usr/bin/env python3
"""
Test CLI fix 22.2
Vérifie que sys.path est correct et que les imports fonctionnent.
"""
import sys
import subprocess
import os

def test_imports():
    # Test 1: import fsdeploy
    try:
        import fsdeploy
        print(f"✓ fsdeploy imported, version: {fsdeploy.__version__}")
    except ImportError as e:
        print(f"✗ import fsdeploy failed: {e}")
        return False
    # Test 2: bare import from scheduler
    try:
        from scheduler.model.task import Task
        print("✓ scheduler.model.task import OK")
    except ImportError as e:
        print(f"✗ scheduler import failed: {e}")
        # Afficher sys.path
        for p in sys.path:
            print(f"  {p}")
        return False
    # Test 3: run fsdeploy --help via module
    try:
        result = subprocess.run(
            [sys.executable, "-m", "fsdeploy", "--help"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            print("✓ fsdeploy --help works")
            return True
        else:
            print(f"✗ fsdeploy --help failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"✗ subprocess error: {e}")
        return False

if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)
