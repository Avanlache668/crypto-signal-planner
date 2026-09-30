#!/usr/bin/env python3
"""Deterministic *hypothetical spot-long* position sizing; NO network, NO trades."""
import argparse
import json
from decimal import Decimal, ROUND_DOWN


def D(x):
    return Decimal(str(x))


def calculate(equity, entry, stop, target, risk_pct=D('0.005'), allocation_pct=D('0.05'),
              fee_pct=D('0.001'), slippage_pct=D('0.001'), qty_step=D('0.00000001')):
    C, E, S, T = map(D, (equity, entry, stop, target))
    r, a, fee, slip, step = map(D, (risk_pct, allocation_pct, fee_pct, slippage_pct, qty_step))
    if C <= 0 or E <= 0 or S <= 0 or T <= 0 or S >= E or T <= E:
        raise ValueError('Require C,E,S,T>0, stop < entry < target (spot long).')
    if not (0 < r <= D('0.1') and 0 < a <= D('1')):
        raise ValueError('Risk must be (0,10%], allocation (0,100%].')
    if not (0 <= fee < D('0.05') and 0 <= slip < D('0.05') and step > 0):
        raise ValueError('Invalid fee/slippage/quantity step.')
    # Conservative all-in adverse side for estimated stop loss.
    eff_entry = E * (1 + fee + slip)
    eff_stop = S * (1 - fee - slip)
    eff_target = T * (1 - fee - slip)
    unit_risk = eff_entry - eff_stop
    unit_reward = eff_target - eff_entry
    if unit_reward <= 0:
        raise ValueError('Expected target <= all-in effective entry.')
    max_by_risk = C * r / unit_risk
    max_by_allocation = C * a / eff_entry
    units = (min(max_by_risk, max_by_allocation) / step).to_integral_value(rounding=ROUND_DOWN) * step
    if units <= 0:
        raise ValueError('Allowed position rounds to zero; reduce qty_step or choose no trade.')
    def f(x): return float(x)
    return dict(
        units=f(units), estimated_entry_cost=f(units * eff_entry),
        planned_max_loss_including_costs=f(units * unit_risk),
        max_trade_risk_amount=f(C*r), max_allocation_amount=f(C*a),
        unit_risk_including_costs=f(unit_risk),
        first_target_net_rr=f(unit_reward / unit_risk),
        first_target_meets_2r=unit_reward / unit_risk >= 2,
        caveat='Illustrative sizing only: stop fills, gap, spread, market impact and exchange restrictions can exceed estimates.'
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('equity', 'entry', 'stop', 'target'):
        p.add_argument('--'+name, required=True, type=Decimal)
    for name, default in (('risk-pct','0.005'), ('allocation-pct','0.05'), ('fee-pct','0.001'),
                          ('slippage-pct','0.001'), ('qty-step','0.00000001')):
        p.add_argument('--'+name, default=Decimal(default), type=Decimal)
    a = p.parse_args()
    result = calculate(a.equity, a.entry, a.stop, a.target, a.risk_pct, a.allocation_pct,
                       a.fee_pct, a.slippage_pct, a.qty_step)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
