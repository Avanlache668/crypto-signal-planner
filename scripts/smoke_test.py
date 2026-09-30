#!/usr/bin/env python3
"""Offline regressions for sizing and validation; never touches a network or broker."""
import copy
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from position_size import calculate
from validate_plan import validate

p = Path(__file__).resolve().parents[1] / 'examples' / 'hypothetical-plan.json'
fixture = json.loads(p.read_text(encoding='utf-8'))
sized = calculate(100000,10,9,12.3)
assert sized['units'] > 0
assert sized['first_target_meets_2r'] is True
assert sized['planned_max_loss_including_costs'] <= 500.01
assert sized['estimated_entry_cost'] <= 5000.01
assert not validate(fixture, allow_fixture=True), validate(fixture, allow_fixture=True)
assert validate(fixture, allow_fixture=False)
low_rr = copy.deepcopy(fixture)
low_rr['first_target'] = 10.5
assert any('below 2' in e for e in validate(low_rr, allow_fixture=True))
bad_quote = copy.deepcopy(fixture)
bad_quote['quote_2'] = 11.0
assert any('disagreement' in e for e in validate(bad_quote, allow_fixture=True))
print('PASS: offline sizing, cap, fixture rejection, low-RR rejection, quote-disagreement rejection.')
