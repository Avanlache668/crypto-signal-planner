"""Deterministic, non-overlapping execution attribution and learning reports."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from math import sqrt
from typing import Sequence


@dataclass(frozen=True)
class Attribution:
    benchmark_component: Decimal
    timing_cost: Decimal
    slippage_cost: Decimal
    execution_pnl: Decimal
    fee_cost: Decimal
    net_marked_component: Decimal
    residual: Decimal


def attribute(quantity: Decimal, decision_mid: Decimal, release_mid: Decimal, fill_price: Decimal, horizon_price: Decimal, fee: Decimal, observed_net: Decimal | None = None) -> Attribution:
    benchmark = quantity * (horizon_price - decision_mid)
    timing = quantity * (release_mid - decision_mid)
    slippage = quantity * (fill_price - release_mid)
    execution = -timing - slippage
    net = benchmark + execution - fee
    residual = Decimal("0") if observed_net is None else observed_net - net
    return Attribution(benchmark, timing, slippage, execution, fee, net, residual)


def alpha_performance(alpha_id: str, returns: Sequence[Decimal], costs: Sequence[Decimal], *, minimum_effective_samples: int = 30) -> dict:
    if len(returns) != len(costs):
        raise ValueError("returns and costs must align")
    n = len(returns)
    if n < minimum_effective_samples:
        return {"alpha_id":alpha_id, "sample_count":n, "effective_sample_count":str(Decimal(n)), "status":"INSUFFICIENT_SAMPLE", "weight_update":"NOT_PROPOSED"}
    net = [r-c for r,c in zip(returns,costs)]
    mean = sum(net,Decimal("0"))/Decimal(n)
    variance = sum(((x-mean)**2 for x in net),Decimal("0"))/Decimal(n-1)
    error = Decimal(str(1.96 * sqrt(float(variance / Decimal(n)))))
    return {"alpha_id":alpha_id, "sample_count":n, "effective_sample_count":str(Decimal(n)), "status":"EVALUATED",
            "cost_adjusted_return":str(mean), "confidence_interval":[str(mean-error),str(mean+error)],
            "weight_update":"PROPOSAL_ONLY"}
