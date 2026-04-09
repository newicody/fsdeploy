"""
Package principal de fsdeploy.
"""

__version__ = "1.0.0"  # valeur par défaut
try:
    from .lib.version import __version__ as lib_version
    __version__ = lib_version
except (ImportError, AttributeError):
    pass
