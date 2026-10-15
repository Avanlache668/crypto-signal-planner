#!/usr/bin/env python3
"""Deterministic *hypothetical spot-long* position sizing; NO network, NO trades."""
import argparse
import json
from decimal import Decimal, ROUND_DOWN


def D(x):
    return Decimal(str(x))


# 规则 v2.1 ⑨（2026-10-15）：ATR14 分档 → 单笔名义上限（占基准权益的比例）。
# $10,000 权益时对应 $250 / $375 / $500，与 MEMORY.md 的规则文字一致。
ATR_TIERS = ((D('8'), D('0.025')), (D('5'), D('0.0375')), (D('0'), D('0.05')))


def calculate(equity, entry, stop, target, risk_pct=D('0.005'), allocation_pct=D('0.05'),
              fee_pct=D('0.001'), slippage_pct=D('0.001'), qty_step=D('0.00000001'),
              atr=None, stop_min_atr=D('1.2'), side='long',
              atr_pct=None, atr_cap_mode='reject', atr_tier_equity=None):
    C, E, S, T = map(D, (equity, entry, stop, target))
    r, a, fee, slip, step = map(D, (risk_pct, allocation_pct, fee_pct, slippage_pct, qty_step))
    short = str(side).lower() == 'short'
    if C <= 0 or E <= 0 or S <= 0 or T <= 0:
        raise ValueError('Require C,E,S,T>0')
    if short:
        if not (T < E < S):
            raise ValueError('Require T < entry < stop (short).')
    else:
        if not (S < E < T):
            raise ValueError('Require stop < entry < target (spot long).')
    if not (0 < r <= D('0.1') and 0 < a <= D('1')):
        raise ValueError('Risk must be (0,10%], allocation (0,100%].')
    if not (0 <= fee < D('0.05') and 0 <= slip < D('0.05') and step > 0):
        raise ValueError('Invalid fee/slippage/quantity step.')
    # Conservative all-in adverse side for estimated stop loss.
    if short:
        eff_entry = E * (1 - fee - slip)   # sell fill is worse (lower)
        eff_stop = S * (1 + fee + slip)    # buy-back stop is worse (higher)
        eff_target = T * (1 + fee + slip)  # buy-back target is worse (higher)
        unit_risk = eff_stop - eff_entry
        unit_reward = eff_entry - eff_target
    else:
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
    out = dict(
        units=f(units), estimated_entry_cost=f(units * eff_entry),
        planned_max_loss_including_costs=f(units * unit_risk),
        max_trade_risk_amount=f(C*r), max_allocation_amount=f(C*a),
        unit_risk_including_costs=f(unit_risk),
        first_target_net_rr=f(unit_reward / unit_risk),
        first_target_meets_2r=unit_reward / unit_risk >= 2,
        caveat='Illustrative sizing only: stop fills, gap, spread, market impact and exchange restrictions can exceed estimates.'
    )
    if short:  # 仅在做空时附加，做多输出保持逐字节不变
        out['side'] = 'short'
    if atr is not None:  # 规则 v2：仅在传入 ATR 时附加校验，旧调用输出不变
        gate = check_stop_atr(E, S, atr, stop_min_atr, side=('short' if short else 'long'))
        out.update(stop_atr_ratio=gate['stop_atr_ratio'], stop_atr_ok=gate['ok'],
                   stop_atr_message=gate['message'])
    if atr_pct is not None:  # 规则 v2.1 ⑨：ATR 分档名义上限闸门，旧调用输出不变
        base = C if atr_tier_equity is None else D(atr_tier_equity)
        tier = check_atr_tier(base, units * eff_entry, atr_pct)
        if not tier['ok'] and str(atr_cap_mode).lower() == 'clamp':
            cap_units = (min(max_by_risk, D(tier['cap_amount']) / eff_entry) / step
                         ).to_integral_value(rounding=ROUND_DOWN) * step
            if cap_units > 0:
                units = cap_units
                out['units'] = f(units)
                out['estimated_entry_cost'] = f(units * eff_entry)
                out['planned_max_loss_including_costs'] = f(units * unit_risk)
                tier = check_atr_tier(base, units * eff_entry, atr_pct)
        out.update(atr_pct=f(D(atr_pct)), atr_tier_pct=tier['tier_pct'],
                   atr_tier_cap_amount=tier['cap_amount'], atr_tier_notional=tier['notional'],
                   atr_tier_ok=tier['ok'], atr_tier_message=tier['message'])
    return out


def check_atr_tier(equity, notional, atr_pct, tiers=ATR_TIERS):
    """规则 v2.1 ⑨ 闸门：按 ATR14（百分数口径，如 8.49 = 8.49%）限制单笔名义上限。

    档位（基准权益为 $10,000 时）：ATR>8% → 2.5%($250) / 5~8% → 3.75%($375) / <=5% → 5%($500)。
    返回 dict（不抛异常）：atr_pct / tier_pct / cap_amount / notional / ok / message。
    注意与 check_stop_atr 的区别：本函数收 **百分数**，check_stop_atr 收 **价格口径**。
    """
    C, N, A = D(equity), D(notional), D(atr_pct)
    if C <= 0 or A <= 0:
        raise ValueError('Require equity>0 and atr_pct>0.')
    pct = D('0.05')
    for lo, cap in tiers:
        if A > lo:
            pct = cap
            break
    cap_amount = C * pct
    ok = N <= cap_amount
    def f(x): return float(x)
    return dict(atr_pct=f(A), tier_pct=f(pct * 100), cap_amount=f(cap_amount),
                notional=f(N), ok=bool(ok),
                message=('ok' if ok else
                         f'REJECT: 名义 ${float(N):,.2f} > ATR 分档上限 ${float(cap_amount):,.2f}'
                         f'（ATR14 {float(A):.2f}% → 基准权益 {float(pct * 100):.2f}%）；'
                         '按规则 v2.1 ⑨ 减仓或放弃该笔'))


def check_stop_atr(entry, stop, atr, min_ratio=D('1.2'), side='long'):
    """规则 v2 闸门：止损距离必须 >= min_ratio x ATR（避免被日内噪声扫损）。

    返回 dict（不抛异常）：ratio / ok / message。atr 为 ATR 的**同一价格口径**
    （如 ATR14 = 1821，或 ATR%=2.36 时请换算成价格后再传入；也可直接传 atr_pct 并把
    entry 的百分比距离当作比例使用，本函数只做比例比较）。
    """
    E, S, A, m = map(D, (entry, stop, atr, min_ratio))
    if E <= 0 or A <= 0:
        raise ValueError('Require entry>0 and atr>0.')
    dist = (S - E) if str(side).lower() == 'short' else (E - S)
    ratio = dist / A
    ok = ratio >= m
    def f(x): return float(x)
    return dict(stop_distance=f(dist), atr=f(A), stop_atr_ratio=f(ratio),
                min_ratio=f(m), ok=bool(ok),
                message=('ok' if ok else f'REJECT: 止损仅 {float(ratio):.2f}xATR (< {float(m):.2f}xATR)，'
                         '需放宽止损并据此减仓，或放弃该笔'))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('equity', 'entry', 'stop', 'target'):
        p.add_argument('--'+name, required=True, type=Decimal)
    p.add_argument('--side', default='long', choices=('long','short'),
                   help='long(默认,现货做多) | short(做空：需 target < entry < stop)')
    p.add_argument('--atr', default=None, type=Decimal,
                   help='规则v2：ATR 价格口径，传入则附加 stop_atr_ratio / stop_atr_ok 校验')
    p.add_argument('--atr-pct', default=None, type=Decimal,
                   help='规则v2.1 ⑨：ATR14 百分数（如 8.49），传入则附加 atr_tier_* 名义上限校验')
    p.add_argument('--atr-cap-mode', default='reject', choices=('reject', 'clamp'),
                   help='reject(默认)=超上限只标记 atr_tier_ok=false；clamp=自动缩到档位上限')
    p.add_argument('--atr-tier-equity', default=None, type=Decimal,
                   help='分档基准权益，默认=--equity')
    for name, default in (('risk-pct','0.005'), ('allocation-pct','0.05'), ('fee-pct','0.001'),
                          ('slippage-pct','0.001'), ('qty-step','0.00000001')):
        p.add_argument('--'+name, default=Decimal(default), type=Decimal)
    a = p.parse_args()
    result = calculate(a.equity, a.entry, a.stop, a.target, a.risk_pct, a.allocation_pct,
                       a.fee_pct, a.slippage_pct, a.qty_step, atr=a.atr, side=a.side,
                       atr_pct=a.atr_pct, atr_cap_mode=a.atr_cap_mode,
                       atr_tier_equity=a.atr_tier_equity)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
