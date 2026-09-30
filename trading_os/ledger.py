"""Pure inventory/cash/fee ledger reducer."""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Mapping

from .contracts import EventEnvelope
from .errors import ValidationError


@dataclass(frozen=True)
class LedgerState:
    balances: Mapping[str, Decimal] = field(default_factory=dict)
    fees: Mapping[str, Decimal] = field(default_factory=dict)
    external_flows: Mapping[str, Decimal] = field(default_factory=dict)
    processed_fills: frozenset[str] = frozenset()
    corrections: tuple[str, ...] = ()


def _add(values: Mapping[str, Decimal], key: str, amount: Decimal) -> dict[str, Decimal]:
    result = dict(values)
    result[key] = result.get(key, Decimal("0")) + amount
    return result


def ledger_reducer(state: LedgerState, event: EventEnvelope) -> LedgerState:
    payload = event.payload
    if event.event_type == "ORDER_FILLED":
        fill_id = str(payload["fill_id"])
        if fill_id in state.processed_fills:
            return state
        qty = Decimal(str(payload["quantity"]))
        price = Decimal(str(payload["price"]))
        fee = Decimal(str(payload["fee_amount"]))
        base, quote, fee_asset = str(payload["base"]), str(payload["quote"]), str(payload["fee_asset"])
        if qty <= 0 or price <= 0 or fee < 0:
            raise ValidationError("invalid fill economics")
        side = payload["side"]
        sign = Decimal("1") if side == "buy" else Decimal("-1") if side == "sell" else None
        if sign is None:
            raise ValidationError("invalid fill side")
        balances = _add(state.balances, base, sign * qty)
        balances = _add(balances, quote, -sign * qty * price)
        balances = _add(balances, fee_asset, -fee)
        return LedgerState(balances, _add(state.fees, fee_asset, fee), state.external_flows,
                           state.processed_fills | {fill_id}, state.corrections)
    if event.event_type == "EXTERNAL_FLOW_RECORDED":
        asset, amount = str(payload["asset"]), Decimal(str(payload["amount"]))
        return LedgerState(_add(state.balances, asset, amount), state.fees,
                           _add(state.external_flows, asset, amount), state.processed_fills, state.corrections)
    if event.event_type == "CORRECTION_RECORDED":
        asset, amount = str(payload["asset"]), Decimal(str(payload["amount"]))
        if not payload.get("reason") or not payload.get("corrects_event_id"):
            raise ValidationError("correction requires reason and event reference")
        return LedgerState(_add(state.balances, asset, amount), state.fees, state.external_flows,
                           state.processed_fills, state.corrections + (event.event_id,))
    return state

