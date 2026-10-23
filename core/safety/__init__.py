"""T.A.R.O. safety package."""

from core.safety.audit import AuditLogger, default_audit_logger, get_audit_logger
from core.safety.confirmation import (
    ConfirmationGate,
    ConfirmationRequest,
    default_confirmation_gate,
)
from core.safety.kill_switch import KillSwitch, kill_switch
from core.safety.permissions import (
    PermissionAction,
    PermissionDenied,
    PermissionManager,
    SafetyBlock,
    get_permission_manager,
)
from core.safety.risk import RiskClassifier, RiskLevel, default_risk_classifier
from core.safety.sandbox import CodeSandbox, SandboxResult, default_sandbox
from core.safety.untrusted import (
    TaintContext,
    UntrustedSource,
    current_turn_taint,
    wrap_untrusted,
)

__all__ = [
    "AuditLogger",
    "CodeSandbox",
    "ConfirmationGate",
    "ConfirmationRequest",
    "KillSwitch",
    "PermissionAction",
    "PermissionDenied",
    "PermissionManager",
    "RiskClassifier",
    "RiskLevel",
    "SafetyBlock",
    "SandboxResult",
    "TaintContext",
    "UntrustedSource",
    "current_turn_taint",
    "default_audit_logger",
    "default_confirmation_gate",
    "default_risk_classifier",
    "default_sandbox",
    "get_audit_logger",
    "get_permission_manager",
    "kill_switch",
    "wrap_untrusted",
]
