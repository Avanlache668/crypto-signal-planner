#!/usr/bin/env python3
"""Check a candidate plan's internal evidence/risk gates. No fetches or trading."""
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import json
import sys
from pathlib import Path
from position_size import calculate, D

REQUIRED = {'hypothetical','symbol','chain','market_pair','source','as_of','source_2',
            'source_2_as_of','quote','quote_2','equity','entry','stop','first_target',
            'second_target','fee_pct_per_side','slippage_pct_per_side','risk_pct',
            'allocation_pct','active_branch','research_state','model_signal',
            'execution_state','data_quality'}


def parse_time(value):
    x = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if x.utcoffset() is None:
        raise ValueError('UTC-offset-aware ISO 8601 time required')
    return x.astimezone(timezone.utc)


def validate(p, allow_fixture=False, now=None):
    errors = []
    missing = REQUIRED - set(p)
    if missing: return ['missing fields: ' + ', '.join(sorted(missing))]
    try:
        one, two = parse_time(p['as_of']), parse_time(p['source_2_as_of'])
        now = now or datetime.now(timezone.utc)
        if one > now or two > now:
            errors.append('future evidence timestamp')
        if not p['hypothetical'] and (now-one).total_seconds()>900:
            errors.append('primary quote stale >15min')
        if not p['hypothetical'] and (now-two).total_seconds()>900:
            errors.append('secondary quote stale >15min')
    except (ValueError, TypeError) as ex:
        errors.append('invalid timestamps: ' + str(ex))
    for field in ('symbol','chain','market_pair','source','source_2'):
        if not isinstance(p[field], str) or not p[field].strip():
            errors.append(f'{field} missing')
    try:
        q, q2 = D(p['quote']), D(p['quote_2'])
        if q <= 0 or q2 <= 0 or abs(q-q2)/q > D('0.01'):
            errors.append('quote disagreement >1% or invalid quote')
        if abs(D(p['entry']) - q)/q > D('0.5'):
            errors.append('entry >50% away from current quote; needs manual review')
        r = calculate(p['equity'],p['entry'],p['stop'],p['first_target'],p['risk_pct'],
                      p['allocation_pct'],p['fee_pct_per_side'],p['slippage_pct_per_side'])
        if not r['first_target_meets_2r']:
            errors.append('first target net risk/reward below 2')
        if D(p['second_target']) <= D(p['first_target']):
            errors.append('second target must exceed first')
    except (ValueError, ArithmeticError, TypeError) as ex:
        errors.append('invalid price/risk inputs: ' + str(ex))
    if p['execution_state'] != 'NO_ORDER':
        errors.append('this skill only validates NO_ORDER candidate plans')
    if p['active_branch'] not in ('pullback','breakout','none'):
        errors.append('active_branch invalid')
    if p['hypothetical']:
        if not allow_fixture:
            errors.append('hypothetical fixture is not an actionable plan')
    elif p['data_quality'] != 'VERIFIED':
        errors.append('data_quality must be VERIFIED for nonfixture candidate')
    if not p['hypothetical'] and (not p.get('catalyst_sources') or
                                 any(not isinstance(x,str) or not x.startswith('https://') for x in p['catalyst_sources'])):
        errors.append('nonfixture plan requires https catalyst_sources')
    return errors


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('plan_json', type=Path)
    ap.add_argument('--allow-fixture', action='store_true', help='ONLY for bundled unit-test fixtures')
    args = ap.parse_args()
    data = json.loads(args.plan_json.read_text(encoding='utf-8'))
    errs = validate(data, args.allow_fixture)
    print(json.dumps({'valid':not errs, 'errors':errs, 'note':'Validation checks internal consistency, not the truth of externally supplied evidence.'},
                     ensure_ascii=False, indent=2))
    sys.exit(1 if errs else 0)


if __name__ == '__main__': main()
