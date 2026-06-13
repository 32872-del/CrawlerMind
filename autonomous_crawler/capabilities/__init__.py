"""Transparent capability gating for CLM Community and Private Core.

Community features must keep running without a token. Private features should
use this package to check whether an explicitly signed local license enables a
named capability, then degrade cleanly when it is unavailable.
"""
from .license import (
    CapabilityGate,
    CapabilityStatus,
    LicenseCheckResult,
    LicensePayload,
    build_capability_gate,
)

__all__ = [
    "CapabilityGate",
    "CapabilityStatus",
    "LicenseCheckResult",
    "LicensePayload",
    "build_capability_gate",
]
