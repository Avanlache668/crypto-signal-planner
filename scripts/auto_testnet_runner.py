#!/usr/bin/env python3
"""Validate a plan and automatically submit a LIMIT order to Gate TestNet only.

This runner deliberately has no live-money execution path.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from decimal import Decimal, ROUND_DOWN

from gate_client import GateClient, GateConfig


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _validate(path: Path) -> None:
    script = Path(__file__).with_name("validate_plan.py")
    proc = subprocess.run([sys.executable, str(script), str(path)], capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit("Plan validation failed:\n" + proc.stdout + proc.stderr)


def _units(plan: dict) -> Decimal:
    equity = Decimal(str(plan["equity"]))
    entry = Decimal(str(plan["entry"]))
    stop = Decimal(str(plan["stop"]))
    risk_pct = Decimal(str(plan["risk_pct"]))
    allocation_pct = Decimal(str(plan["allocation_pct"]))
    risk_per_unit = entry - stop
    if risk_per_unit <= 0:
        raise SystemExit("Long spot testnet runner requires entry > stop")
    by_risk = equity * risk_pct / risk_per_unit
    by_allocation = equity * allocation_pct / entry
    return min(by_risk, by_allocation).quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("plan", type=Path)
    ap.add_argument("--execute", action="store_true", help="actually submit to Gate TestNet; otherwise preview only")
    args = ap.parse_args()

    _validate(args.plan)
    plan = _load(args.plan)
    if plan.get("model_signal") not in {"BUY_CANDIDATE", "WATCH_BUY"}:
        raise SystemExit("Plan model_signal is not eligible for a testnet buy")
    if plan.get("data_quality") != "VERIFIED":
        raise SystemExit("Testnet runner requires VERIFIED data_quality")

    pair = str(plan["market_pair"]).replace("/", "_").upper()
    amount = _units(plan)
    payload = GateClient.preview_limit_order(pair, "buy", amount, plan["entry"], "t-csp-testnet")
    if not args.execute:
        print(json.dumps({"mode": "preview", "order": payload}, ensure_ascii=False, indent=2))
        return 0

    cfg = GateConfig.from_env()
    if cfg.mode != "testnet":
        raise SystemExit("Set GATE_MODE=testnet. Live order execution is intentionally unavailable.")
    result = GateClient(cfg).submit_testnet_limit_order(pair, "buy", amount, plan["entry"], "t-csp-testnet")
    print(json.dumps({"mode": "testnet", "submitted": True, "result": result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
