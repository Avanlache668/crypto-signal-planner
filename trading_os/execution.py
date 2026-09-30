"""LIMIT-only plans, bounded paper fills, proposal adapters and pure lifecycle."""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal, ROUND_DOWN
from typing import Mapping, Protocol

from .contracts import Capability, ExecutionPlan, Fill, Money, OperatingMode, Order, TradeIntent
from .errors import CapabilityDenied, ValidationError
from .governance import ModeController
from .serialization import content_hash


def build_limit_plan(intent: TradeIntent, risk_decision_id: str, plan_id: str, now: datetime) -> ExecutionPlan:
    if intent.expires_at <= now:
        raise ValidationError("intent expired")
    delta = intent.delta
    if delta == 0:
        raise ValidationError("target already satisfied")
    side = "buy" if delta > 0 else "sell"
    return ExecutionPlan(plan_id, intent.intent_id, "LIMIT", side, abs(delta), intent.limit_price,
                         intent.expires_at, intent.mode, intent.mode_epoch, risk_decision_id)


@dataclass(frozen=True)
class PaperFillModel:
    version: str = "paper-limit-v1"
    fee_rate: Decimal = Decimal("0.001")
    slippage_bps: Decimal = Decimal("2")
    max_depth_fraction: Decimal = Decimal("0.10")


@dataclass(frozen=True)
class BookLevel:
    price: Decimal
    quantity: Decimal


class PaperSimulator:
    def __init__(self, model: PaperFillModel): self.model = model

    def simulate(self, plan: ExecutionPlan, levels: tuple[BookLevel, ...], fee_asset, now: datetime, fill_id: str) -> Fill | None:
        eligible = [level for level in levels if (plan.side == "buy" and level.price <= plan.limit_price) or (plan.side == "sell" and level.price >= plan.limit_price)]
        if not eligible:
            return None
        available = sum((level.quantity for level in eligible), Decimal("0")) * self.model.max_depth_fraction
        quantity = min(plan.quantity, available)
        if quantity <= 0:
            return None
        best = eligible[0].price
        slip = self.model.slippage_bps / Decimal("10000")
        price = best * (Decimal("1") + slip if plan.side == "buy" else Decimal("1") - slip)
        if (plan.side == "buy" and price > plan.limit_price) or (plan.side == "sell" and price < plan.limit_price):
            price = plan.limit_price
        fee = Money(quantity * price * self.model.fee_rate, fee_asset)
        return Fill(fill_id, plan.plan_id, quantity, price, fee, "SIMULATED:" + self.model.version, now)


class ProposalAdapter(Protocol):
    def render(self, plan: ExecutionPlan) -> Mapping[str, object]: ...


class GateProposalAdapter:
    """No credentials and no network methods; renders the existing Gate payload shape."""
    def __init__(self, symbol_map: Mapping[str, str]): self.symbol_map = symbol_map

    def render(self, plan: ExecutionPlan) -> Mapping[str, object]:
        if plan.order_type != "LIMIT":
            raise ValidationError("UNSUPPORTED order type")
        pair = self.symbol_map.get(plan.plan_id)
        if not pair:
            raise ValidationError("instrument mapping unavailable")
        order = {"text":"t-trading-os-v2", "currency_pair":pair, "type":"limit", "account":"spot", "side":plan.side,
                 "amount":format(plan.quantity,"f"), "price":format(plan.limit_price,"f"), "time_in_force":"gtc", "auto_borrow":False}
        return {"schema":"crypto-trading-os/live-proposal/v2", "execution_state":"PROPOSAL_ONLY", "live_submission_available":False,
                "plan_id":plan.plan_id, "mode_epoch":plan.mode_epoch, "order":order, "content_hash":content_hash(order)}


class TestNetGateAdapter:
    """Calls an injected sender only after immutable capability and host checks."""
    def __init__(self, host: str, sender): self.host, self.sender = host, sender

    def send(self, plan: ExecutionPlan, capability: Capability, controller: ModeController, now: datetime):
        controller.authorize(capability, "SEND_TESTNET_LIMIT", now, host=self.host)
        if plan.mode is not OperatingMode.TESTNET or plan.mode_epoch != controller.epoch or plan.expires_at <= now:
            raise CapabilityDenied("plan mode, epoch, or expiry invalid")
        if plan.order_type != "LIMIT": raise ValidationError("UNSUPPORTED")
        return self.sender(plan)


@dataclass(frozen=True)
class OrderState:
    status: str = "PROPOSED"
    filled: Decimal = Decimal("0")
    seen_fills: frozenset[str] = frozenset()
    reconciliation: str = "PENDING"


def order_reducer(state: OrderState, event_type: str, payload: Mapping[str, object]) -> OrderState:
    if event_type == "ORDER_SEND_REQUESTED" and state.status in {"PROPOSED", "READY"}:
        return replace(state, status="SEND_PENDING")
    if event_type == "ORDER_STATUS_UNKNOWN":
        return replace(state, status="UNKNOWN", reconciliation="DISPUTED")
    if event_type == "ORDER_ACKNOWLEDGED" and state.status in {"SEND_PENDING", "UNKNOWN"}:
        return replace(state, status="ACKNOWLEDGED", reconciliation="CONFIRMED")
    if event_type == "ORDER_CANCEL_REQUESTED":
        return replace(state, status="CANCEL_PENDING")
    if event_type == "ORDER_CANCELLED":
        return replace(state, status="CANCELLED", reconciliation="CONFIRMED")
    if event_type == "ORDER_FILLED":
        fill_id, qty = str(payload["fill_id"]), Decimal(str(payload["quantity"]))
        if fill_id in state.seen_fills: return state
        # Fills remain economic facts even after cancel/terminal status.
        new_qty = state.filled + qty
        status = "PARTIALLY_FILLED" if payload.get("remaining", "1") != "0" else "FILLED"
        reconciliation = "DISPUTED" if state.status == "CANCELLED" else "CONFIRMED"
        return OrderState(status, new_qty, state.seen_fills | {fill_id}, reconciliation)
    return state

