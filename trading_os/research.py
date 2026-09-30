"""Deterministic offline regime, alpha, arbitration and portfolio pipeline."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from math import exp, log
from typing import Callable, Iterable, Sequence

from .contracts import AlphaSignal, ArbitratedSignal, InstrumentId, RegimeAssessment, SignalState, TargetPortfolio, TradeIntent, OperatingMode
from .errors import ValidationError


@dataclass(frozen=True)
class Bar:
    available_at: datetime
    close: Decimal
    volume: Decimal


@dataclass(frozen=True)
class AlphaDefinition:
    name: str
    implemented: bool
    version: str


ALPHA_REGISTRY = {
    name: AlphaDefinition(name, name in {"trend", "momentum", "mean_reversion"}, "1.0")
    for name in ("trend", "momentum", "mean_reversion", "breakout", "relative_strength", "cross_sectional", "volume", "liquidity", "onchain", "catalyst", "macro", "supply_unlock", "sentiment")
}


def _known_bars(bars: Sequence[Bar], decision_at: datetime) -> list[Bar]:
    known = sorted((bar for bar in bars if bar.available_at <= decision_at), key=lambda b: b.available_at)
    if len(known) < 21:
        raise ValidationError("at least 21 available bars are required")
    return known


def generate_alphas(instrument: InstrumentId, state_id: str, bars: Sequence[Bar], decision_at: datetime, id_factory: Callable[[], str], *, calibration_ref: str | None = None) -> tuple[AlphaSignal, ...]:
    known = _known_bars(bars, decision_at)
    prices = [bar.close for bar in known]
    latest = prices[-1]
    sma5 = sum(prices[-5:]) / Decimal("5")
    sma20 = sum(prices[-20:]) / Decimal("20")
    momentum = latest / prices[-6] - Decimal("1")
    mean_deviation = latest / sma20 - Decimal("1")
    specs = (
        ("trend", Decimal("1") if sma5 > sma20 else Decimal("-1"), "LONG" if sma5 > sma20 else "SHORT", "price"),
        ("momentum", momentum, "LONG" if momentum > 0 else "SHORT", "price"),
        ("mean_reversion", -mean_deviation, "LONG" if mean_deviation < 0 else "SHORT", "price"),
    )
    results = []
    for name, score, direction, group in specs:
        # Scores remain rankings unless an externally validated calibrator is explicitly supplied.
        expected = score / Decimal("100") if calibration_ref else None
        results.append(AlphaSignal(id_factory(), name, "1.0", instrument, direction, score, "RAW_RANK" if not calibration_ref else "CALIBRATED_RETURN_PROXY", timedelta(days=1), decision_at + timedelta(days=1), tuple(f"bar:{b.available_at.isoformat()}" for b in known[-20:]), state_id, group, decision_at, expected))
    return tuple(results)


@dataclass(frozen=True)
class RegimeRule:
    enter_threshold: Decimal
    maintain_threshold: Decimal
    confirmations: int
    ttl: timedelta
    version: str = "1.0"


def assess_regime(scope_id: str, dimension: str, score: Decimal, evaluated_at: datetime, rule: RegimeRule, *, previous: RegimeAssessment | None = None, consecutive: int = 1) -> RegimeAssessment:
    threshold = rule.maintain_threshold if previous and previous.status == "ACTIVE" else rule.enter_threshold
    active = score >= threshold and consecutive >= rule.confirmations
    return RegimeAssessment(f"regime:{scope_id}:{dimension}:{evaluated_at.isoformat()}", scope_id, dimension,
                            "HIGH" if active else "UNCERTAIN", score, ("deterministic-score",),
                            previous.entered_at if active and previous else evaluated_at, evaluated_at,
                            evaluated_at + rule.ttl, "ACTIVE" if active else "UNCERTAIN", rule.version)


def arbitrate(signals: Sequence[AlphaSignal], now: datetime, *, half_life: timedelta = timedelta(hours=12), group_cap: Decimal = Decimal("1")) -> ArbitratedSignal:
    included: list[tuple[AlphaSignal, Decimal]] = []
    excluded: dict[str, str] = {}
    groups: dict[str, Decimal] = {}
    for signal in sorted(signals, key=lambda x: x.signal_id):
        if signal.expiry <= now:
            excluded[signal.signal_id] = "expired"; continue
        if signal.calibrated_expected_return is None:
            excluded[signal.signal_id] = "uncalibrated"; continue
        age = Decimal(str((now - signal.emitted_at).total_seconds()))
        decay = Decimal(str(exp(-log(2) * float(max(age, Decimal("0"))) / half_life.total_seconds())))
        available = max(Decimal("0"), group_cap - groups.get(signal.dependence_group, Decimal("0")))
        weight = min(decay, available)
        if weight == 0:
            excluded[signal.signal_id] = "dependence_group_cap"; continue
        groups[signal.dependence_group] = groups.get(signal.dependence_group, Decimal("0")) + weight
        included.append((signal, weight))
    expiry = min((s.expiry for s in signals), default=now)
    if not included:
        return ArbitratedSignal("arbitrated", SignalState.WATCH, timedelta(days=1), None, (), excluded, Decimal("1"), expiry)
    longs = sum((w for s,w in included if s.direction == "LONG"), Decimal("0"))
    shorts = sum((w for s,w in included if s.direction == "SHORT"), Decimal("0"))
    total = longs + shorts
    disagreement = min(longs, shorts) / total if total else Decimal("1")
    aggregate = sum((s.calibrated_expected_return * w for s,w in included), Decimal("0")) / total
    aggregate *= Decimal("1") - disagreement
    state = SignalState.BUY_CANDIDATE if aggregate > 0 and disagreement < Decimal("0.4") else SignalState.NO_ACTION
    return ArbitratedSignal("arbitrated", state, timedelta(days=1), aggregate, tuple(s.signal_id for s,_ in included), excluded, disagreement, expiry)


def construct_portfolio(signal: ArbitratedSignal, asset_key: str, *, max_weight: Decimal = Decimal("0.05")) -> TargetPortfolio:
    weight = Decimal("0")
    if signal.state is SignalState.BUY_CANDIDATE and signal.aggregate_score is not None:
        weight = min(max_weight, max(Decimal("0"), signal.aggregate_score))
    return TargetPortfolio("target", {asset_key: weight}, Decimal("1") - weight, signal.included_refs)


def compile_intent(target: TargetPortfolio, instrument: InstrumentId, equity: Decimal, price: Decimal, current_quantity: Decimal, now: datetime, mode: OperatingMode, epoch: int, policy_version: str) -> TradeIntent:
    weight = target.weights.get(instrument.base.canonical, Decimal("0"))
    target_quantity = equity * weight / price
    return TradeIntent("intent:" + target.target_id, instrument, target_quantity, current_quantity, price, now + timedelta(minutes=15), target.signal_refs, mode, epoch, policy_version)

