"""Immutable capability matrix and mode-epoch governance."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping

from .contracts import Capability, OperatingMode
from .errors import CapabilityDenied, ValidationError

LIVE_HOST = "https://api.gateio.ws"
TESTNET_HOST = "https://api-testnet.gateapi.io"

CAPABILITY_MATRIX: Mapping[OperatingMode, frozenset[str]] = {
    OperatingMode.RESEARCH: frozenset({"PUBLIC_READ", "RESEARCH_PREVIEW"}),
    OperatingMode.SHADOW: frozenset({"PUBLIC_READ", "LIVE_PRIVATE_READ", "RESEARCH_PREVIEW"}),
    OperatingMode.PAPER: frozenset({"PUBLIC_READ", "SIMULATE_FILL"}),
    OperatingMode.TESTNET: frozenset({"PUBLIC_READ", "TESTNET_PRIVATE_READ", "BUILD_TESTNET_LIMIT", "SEND_TESTNET_LIMIT"}),
    OperatingMode.LIVE_PROPOSAL: frozenset({"PUBLIC_READ", "LIVE_PRIVATE_READ", "BUILD_UNSIGNED_LIVE_PROPOSAL"}),
}

IMMUTABLE_DENIES = frozenset({"SEND_LIVE_ORDER", "CANCEL_LIVE_ORDER", "AMEND_LIVE_ORDER", "WITHDRAW", "TRANSFER", "BORROW", "MARGIN_WRITE"})


@dataclass
class ModeController:
    mode: OperatingMode
    epoch: int = 1

    def switch(self, mode: OperatingMode, *, reconciled: bool, pending_commands: int) -> int:
        if not reconciled or pending_commands:
            raise ValidationError("mode switch requires reconciliation and no pending commands")
        self.mode = mode
        self.epoch += 1
        return self.epoch

    def authorize(self, capability: Capability, operation: str, now: datetime, *, host: str | None = None) -> None:
        if operation in IMMUTABLE_DENIES:
            raise CapabilityDenied("real-money and fund-movement writes are immutable-deny")
        if capability.mode != self.mode or capability.mode_epoch != self.epoch:
            raise CapabilityDenied("stale or cross-mode capability")
        if capability.expires_at <= now:
            raise CapabilityDenied("capability expired")
        if operation not in CAPABILITY_MATRIX[self.mode] or capability.name != operation:
            raise CapabilityDenied("operation not allowed in mode")
        if operation == "SEND_TESTNET_LIMIT" and host != TESTNET_HOST:
            raise CapabilityDenied("TestNet writes require exact official host")


def validate_parameter_update(layer: str, changes: Mapping[str, object]) -> None:
    protected = {"live_write_enabled", "daily_loss_limit", "weekly_loss_limit", "drawdown_limit", "capabilities", "mode"}
    if layer == "LEARNED" and protected.intersection(changes):
        raise CapabilityDenied("learned parameters cannot modify safety or operator policy")
