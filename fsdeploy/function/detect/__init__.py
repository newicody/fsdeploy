"""fsdeploy.function.detect — Détection de l'environnement et des rôles."""
from function.detect.environment import EnvironmentDetectTask
from function.detect.role_patterns import (
    ROLE_PATTERNS,
    RolePattern,
    DetectionSignal,
    DetectionResult,
    detect_magic,
    scan_directory,
    compute_aggregate_confidence,
    get_role_pattern,
    get_role_color,
    get_role_emoji,
    get_role_description,
    format_role_badge,
)

__all__ = [
    "EnvironmentDetectTask",
    "ROLE_PATTERNS",
    "RolePattern",
    "DetectionSignal",
    "DetectionResult",
    "detect_magic",
    "scan_directory",
    "compute_aggregate_confidence",
    "get_role_pattern",
    "get_role_color",
    "get_role_emoji",
    "get_role_description",
    "format_role_badge",
]
