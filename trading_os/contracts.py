"""Versioned domain contracts. No network, clock, or exchange dependencies."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, Mapping, Sequence

from .errors import ValidationError

SCHEMA_VERSION = "2.0"


def utc(value: datetime, name: str = "timestamp") -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValidationError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def decimal(value: object, name: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValidationError(f"{name} must be Decimal-compatible") from exc
    if not result.is_finite():
        raise ValidationError(f"{name} must be finite")
    return result


class OperatingMode(str, Enum):
    RESEARCH = "RESEARCH"
    SHADOW = "SHADOW"
    PAPER = "PAPER"
    TESTNET = "TESTNET"
    LIVE_PROPOSAL = "LIVE_PROPOSAL"


class KnowledgeType(str, Enum):
    OBSERVED = "OBSERVED"
    DERIVED = "DERIVED"
    INFERRED = "INFERRED"


class RiskAction(str, Enum):
    ALLOW = "ALLOW"
    REDUCE = "REDUCE"
    BLOCK = "BLOCK"
    FREEZE = "FREEZE"
    KILL = "KILL"


class SignalState(str, Enum):
    NO_ACTION = "NO_ACTION"
    WATCH = "WATCH"
    WATCH_BUY = "WATCH_BUY"
    BUY_CANDIDATE = "BUY_CANDIDATE"
    REDUCE_CANDIDATE = "REDUCE_CANDIDATE"
    EXIT_CANDIDATE = "EXIT_CANDIDATE"


@dataclass(frozen=True)
class AssetId:
    namespace: str
    symbol: str
    chain: str | None = None
    contract: str | None = None

    def __post_init__(self) -> None:
        if not self.namespace.strip() or not self.symbol.strip():
            raise ValidationError("asset namespace and symbol are required")
        if self.namespace == "token" and not (self.chain and self.contract):
            raise ValidationError("token identity requires chain and contract")

    @property
    def canonical(self) -> str:
        parts = [self.namespace.lower(), self.symbol.upper()]
        if self.chain:
            parts.append(self.chain.lower())
        if self.contract:
            parts.append(self.contract.lower())
        return ":".join(parts)


@dataclass(frozen=True)
class InstrumentId:
    venue: str
    product: str
    base: AssetId
    quote: AssetId
    settlement: AssetId
    multiplier: Decimal = Decimal("1")

    def __post_init__(self) -> None:
        object.__setattr__(self, "multiplier", decimal(self.multiplier, "multiplier"))
        if self.product != "SPOT":
            raise ValidationError("V2 supports SPOT instruments only")
        if self.multiplier <= 0 or not self.venue:
            raise ValidationError("venue and positive multiplier are required")

    @property
    def canonical(self) -> str:
        return f"{self.venue.lower()}:{self.product}:{self.base.canonical}/{self.quote.canonical}"


@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: AssetId

    def __post_init__(self) -> None:
        object.__setattr__(self, "amount", decimal(self.amount, "money.amount"))


@dataclass(frozen=True)
class Quantity:
    amount: Decimal
    asset: AssetId

    def __post_init__(self) -> None:
        object.__setattr__(self, "amount", decimal(self.amount, "quantity.amount"))


@dataclass(frozen=True)
class Fact:
    field: str
    value: Decimal | str
    unit: str
    available_at: datetime
    valid_until: datetime
    provenance_refs: tuple[str, ...]
    epistemic_type: KnowledgeType
    input_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "available_at", utc(self.available_at, "available_at"))
        object.__setattr__(self, "valid_until", utc(self.valid_until, "valid_until"))
        if self.valid_until < self.available_at:
            raise ValidationError("valid_until precedes available_at")
        if not self.field or not self.unit or not self.provenance_refs:
            raise ValidationError("fact requires field, unit, and provenance")
        if self.epistemic_type is KnowledgeType.DERIVED and not self.input_refs:
            raise ValidationError("derived fact requires input_refs")


@dataclass(frozen=True)
class ObservedState(Fact):
    epistemic_type: KnowledgeType = field(default=KnowledgeType.OBSERVED, init=False)


@dataclass(frozen=True)
class DerivedState(Fact):
    epistemic_type: KnowledgeType = field(default=KnowledgeType.DERIVED, init=False)


@dataclass(frozen=True)
class InferredState(Fact):
    epistemic_type: KnowledgeType = field(default=KnowledgeType.INFERRED, init=False)
    calibration_ref: str | None = None


@dataclass(frozen=True)
class DataRequirement:
    required_fields: frozenset[str]
    max_age: timedelta
    max_skew: timedelta
    allowed_knowledge: frozenset[KnowledgeType]

    def validate(self, state: "MarketState", decision_at: datetime) -> tuple[str, ...]:
        decision_at = utc(decision_at, "decision_at")
        facts = {f.field: f for f in state.facts}
        errors: list[str] = []
        for name in sorted(self.required_fields):
            fact = facts.get(name)
            if fact is None:
                errors.append(f"missing:{name}")
                continue
            if fact.epistemic_type not in self.allowed_knowledge:
                errors.append(f"knowledge:{name}:{fact.epistemic_type.value}")
            if fact.available_at > state.knowledge_cutoff or fact.available_at > decision_at:
                errors.append(f"future:{name}")
            if decision_at > fact.valid_until or decision_at - fact.available_at > self.max_age:
                errors.append(f"stale:{name}")
        selected = [facts[n].available_at for n in self.required_fields if n in facts]
        if selected and max(selected) - min(selected) > self.max_skew:
            errors.append("source_skew")
        return tuple(errors)


@dataclass(frozen=True)
class MarketState:
    state_id: str
    as_of: datetime
    knowledge_cutoff: datetime
    instrument: InstrumentId
    facts: tuple[Fact, ...]
    content_hash: str
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "as_of", utc(self.as_of, "as_of"))
        object.__setattr__(self, "knowledge_cutoff", utc(self.knowledge_cutoff, "knowledge_cutoff"))
        if self.as_of > self.knowledge_cutoff:
            raise ValidationError("as_of exceeds knowledge_cutoff")
        if not self.state_id or not self.content_hash:
            raise ValidationError("state id and content hash are required")


@dataclass(frozen=True)
class RegimeAssessment:
    assessment_id: str
    scope_id: str
    dimension: str
    label: str
    score: Decimal
    evidence_refs: tuple[str, ...]
    entered_at: datetime
    evaluated_at: datetime
    valid_until: datetime
    status: str
    transition_rule_version: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "score", decimal(self.score, "regime.score"))
        for name in ("entered_at", "evaluated_at", "valid_until"):
            object.__setattr__(self, name, utc(getattr(self, name), name))
        if not Decimal("0") <= self.score <= Decimal("1"):
            raise ValidationError("regime score must be within [0,1]")


@dataclass(frozen=True)
class AlphaSignal:
    signal_id: str
    alpha_id: str
    alpha_version: str
    instrument: InstrumentId
    direction: str
    score: Decimal
    score_semantics: str
    horizon: timedelta
    expiry: datetime
    evidence_refs: tuple[str, ...]
    state_id: str
    dependence_group: str
    emitted_at: datetime
    calibrated_expected_return: Decimal | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "score", decimal(self.score, "alpha.score"))
        object.__setattr__(self, "expiry", utc(self.expiry, "expiry"))
        object.__setattr__(self, "emitted_at", utc(self.emitted_at, "emitted_at"))
        if self.direction not in {"LONG", "SHORT", "FLAT"}:
            raise ValidationError("invalid alpha direction")
        if self.calibrated_expected_return is not None:
            object.__setattr__(self, "calibrated_expected_return", decimal(self.calibrated_expected_return, "expected_return"))


@dataclass(frozen=True)
class ArbitratedSignal:
    signal_id: str
    state: SignalState
    horizon: timedelta
    aggregate_score: Decimal | None
    included_refs: tuple[str, ...]
    excluded: Mapping[str, str]
    disagreement: Decimal
    expiry: datetime


@dataclass(frozen=True)
class RiskBudget:
    budget_id: str
    currency: AssetId
    gross_limit: Decimal
    per_asset_limit: Decimal
    daily_loss_limit: Decimal
    weekly_loss_limit: Decimal
    drawdown_limit: Decimal
    policy_version: str

    def __post_init__(self) -> None:
        for name in ("gross_limit", "per_asset_limit", "daily_loss_limit", "weekly_loss_limit", "drawdown_limit"):
            object.__setattr__(self, name, decimal(getattr(self, name), name))
            if getattr(self, name) < 0:
                raise ValidationError(f"{name} cannot be negative")


@dataclass(frozen=True)
class Reservation:
    reservation_id: str
    budget_id: str
    intent_id: str
    asset: AssetId
    amount: Decimal
    committed: Decimal
    status: str
    mode_epoch: int
    expires_at: datetime


@dataclass(frozen=True)
class RiskDecision:
    decision_id: str
    action: RiskAction
    reasons: tuple[str, ...]
    approved_amount: Decimal
    policy_version: str


@dataclass(frozen=True)
class TargetPortfolio:
    target_id: str
    weights: Mapping[str, Decimal]
    cash_weight: Decimal
    signal_refs: tuple[str, ...]


@dataclass(frozen=True)
class TradeIntent:
    intent_id: str
    instrument: InstrumentId
    target_quantity: Decimal
    current_quantity: Decimal
    limit_price: Decimal
    expires_at: datetime
    signal_refs: tuple[str, ...]
    mode: OperatingMode
    mode_epoch: int
    policy_version: str

    @property
    def delta(self) -> Decimal:
        return self.target_quantity - self.current_quantity


@dataclass(frozen=True)
class ExecutionPlan:
    plan_id: str
    intent_id: str
    order_type: str
    side: str
    quantity: Decimal
    limit_price: Decimal
    expires_at: datetime
    mode: OperatingMode
    mode_epoch: int
    risk_decision_id: str


@dataclass(frozen=True)
class Order:
    order_id: str
    plan_id: str
    status: str
    quantity: Decimal
    filled_quantity: Decimal
    limit_price: Decimal
    mode: OperatingMode
    mode_epoch: int


@dataclass(frozen=True)
class Fill:
    fill_id: str
    order_id: str
    quantity: Decimal
    price: Decimal
    fee: Money
    origin: str
    occurred_at: datetime


@dataclass(frozen=True)
class Position:
    position_id: str
    instrument: InstrumentId
    quantity: Decimal
    cost_basis: Decimal
    economic_status: str
    workflow_status: str
    reconciliation_status: str


@dataclass(frozen=True)
class LedgerEntry:
    entry_id: str
    account: str
    asset: AssetId
    amount: Decimal
    entry_type: str
    reference_id: str


@dataclass(frozen=True)
class AlphaPerformance:
    alpha_id: str
    alpha_version: str
    sample_count: int
    effective_sample_count: Decimal
    cost_adjusted_return: Decimal | None
    confidence_interval: tuple[Decimal, Decimal] | None
    status: str


@dataclass(frozen=True)
class Policy:
    version: str
    content_hash: str
    limits: Mapping[str, Decimal]
    effective_at: datetime


@dataclass(frozen=True)
class Capability:
    name: str
    mode: OperatingMode
    account: str | None
    environment: str
    mode_epoch: int
    expires_at: datetime
    policy_version: str


@dataclass(frozen=True)
class EventEnvelope:
    event_id: str
    event_type: str
    aggregate_type: str
    aggregate_id: str
    aggregate_version: int
    stream_sequence: int
    run_id: str
    mode: OperatingMode
    mode_epoch: int
    occurred_at: datetime
    recorded_at: datetime
    available_at: datetime
    logical_time: int
    producer: str
    idempotency_key: str
    policy_version: str
    payload: Mapping[str, Any]
    previous_hash: str | None = None
    content_hash: str | None = None
    schema_version: str = SCHEMA_VERSION
