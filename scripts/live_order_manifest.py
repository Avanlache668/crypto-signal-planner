#!/usr/bin/env python3
"""Build a deterministic Gate live-order proposal without submitting anything.

This helper is safe for unattended scheduling: it validates a plan, computes a
position size, builds the exact spot LIMIT order payload, and emits a SHA-256
fingerprint plus metadata for later human review. It never signs or sends a
private Gate write request.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN
from pathlib import Path

from gate_client import GateClient


def _load(path: Path) -> dict:
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
        raise SystemExit("Long spot proposal requires entry > stop")
    by_risk = equity * risk_pct / risk_per_unit
    by_allocation = equity * allocation_pct / entry
    return min(by_risk, by_allocation).quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)


def _fingerprint(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("plan", type=Path)
    ap.add_argument("--output", type=Path, help="optional JSON output path")
    args = ap.parse_args()

    _validate(args.plan)
    plan = _load(args.plan)
    if plan.get("model_signal") not in {"BUY_CANDIDATE", "WATCH_BUY"}:
        raise SystemExit("Plan model_signal is not eligible for a buy proposal")
    if plan.get("data_quality") != "VERIFIED":
        raise SystemExit("Order proposal requires VERIFIED data_quality")

    pair = str(plan["market_pair"]).replace("/", "_").upper()
    amount = _units(plan)
    order = GateClient.preview_limit_order(pair, "buy", amount, plan["entry"], "t-csp-proposal")
    manifest = {
        "schema": "crypto-signal-planner/gate-order-proposal/v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "execution_state": "PROPOSAL_ONLY",
        "live_submission_available": False,
        "source_plan": str(args.plan),
        "model_signal": plan.get("model_signal"),
        "data_quality": plan.get("data_quality"),
        "order_fingerprint_sha256": _fingerprint(order),
        "order": order,
    }
    text = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
