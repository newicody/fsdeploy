#!/usr/bin/env python3
"""
Test runner for fsdeploy.

Runs all discoverable tests in the tests/ directory.
"""
import sys
import unittest

def main():
    """Run all tests."""
    loader = unittest.TestLoader()
    start_dir = 'tests'
    suite = loader.discover(start_dir, pattern='test_*.py')
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)

if __name__ == '__main__':
    main()
