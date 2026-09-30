"""Unified offline-first Trading OS CLI. It never sends real-money requests."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
from pathlib import Path
from typing import Any

from .attribution import alpha_performance, attribute
from .contracts import AssetId, EventEnvelope, InstrumentId, OperatingMode, RiskBudget
from .event_store import SQLiteEventStore
from .execution import BookLevel, GateProposalAdapter, PaperFillModel, PaperSimulator, build_limit_plan
from .governance import CAPABILITY_MATRIX, IMMUTABLE_DENIES
from .ledger import LedgerState, ledger_reducer
from .research import Bar, arbitrate, compile_intent, construct_portfolio, generate_alphas
from .risk import RiskGovernor, RiskSnapshot
from .serialization import primitive

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE = ROOT / "fixtures" / "synthetic_btc_usd.csv"


class SequenceIds:
    def __init__(self): self.value=0
    def __call__(self): self.value+=1; return f"signal-{self.value:03d}"


def emit(value: Any) -> None:
    print(json.dumps(primitive(value), ensure_ascii=False, indent=2, sort_keys=True))


def load_bars(path: Path, cutoff: datetime | None = None) -> list[Bar]:
    bars=[]
    with path.open(newline="",encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            stamp=datetime.fromisoformat(row["available_at"].replace("Z","+00:00"))
            if cutoff is None or stamp <= cutoff:
                bars.append(Bar(stamp,Decimal(row["close"]),Decimal(row["volume"])))
    return bars


def instrument() -> InstrumentId:
    btc=AssetId("native","BTC"); usd=AssetId("native","USD")
    return InstrumentId("offline","SPOT",btc,usd,usd)


def research(path: Path) -> dict:
    bars=load_bars(path); now=bars[-1].available_at
    signals=generate_alphas(instrument(),"fixture-state-v1",bars,now,SequenceIds(),calibration_ref="synthetic-fixture-calibration-v1")
    result=arbitrate(signals,now)
    return {"fixture":"SYNTHETIC_NOT_LIVE", "as_of":now, "signals":signals, "arbitrated":result}


def paper(path: Path, db: Path) -> dict:
    output=research(path); signal=output["arbitrated"]; bars=load_bars(path); now=bars[-1].available_at
    ins=instrument(); price=bars[-1].close
    target=construct_portfolio(signal,ins.base.canonical,max_weight=Decimal("0.05"))
    intent=compile_intent(target,ins,Decimal("100000"),price,Decimal("0"),now,OperatingMode.PAPER,1,"offline-v1")
    if intent.delta <= 0:
        return {**output,"execution":"NO_ACTION","reason":"no positive calibrated candidate"}
    budget=RiskBudget("paper-budget",ins.quote,Decimal("10000"),Decimal("5000"),Decimal("1000"),Decimal("2000"),Decimal("0.2"),"offline-v1")
    governor=RiskGovernor(str(db)+".risk"); governor.install_budget(budget)
    snapshot=RiskSnapshot(Decimal("0"),Decimal("0"),Decimal("0"),Decimal("0"),Decimal("0"),Decimal("0.02"),Decimal("5000"),Decimal("0"),True,True,True)
    decision=governor.evaluate("risk-1",abs(intent.delta*price),snapshot,budget)
    governor.reserve("reservation-1",budget.budget_id,intent.intent_id,ins.base.canonical,decision.approved_amount,1,intent.expires_at)
    plan=build_limit_plan(intent,decision.decision_id,"paper-plan-1",now)
    fill=PaperSimulator(PaperFillModel()).simulate(plan,(BookLevel(price,Decimal("10")),),ins.quote,now,"paper-fill-1")
    if fill is None: raise RuntimeError("synthetic fixture unexpectedly produced no paper fill")
    governor.commit_fill("reservation-1",fill.quantity*fill.price)
    store=SQLiteEventStore(str(db))
    payload={"fill_id":fill.fill_id,"quantity":str(fill.quantity),"price":str(fill.price),"fee_amount":str(fill.fee.amount),"base":ins.base.canonical,"quote":ins.quote.canonical,"fee_asset":ins.quote.canonical,"side":"buy","fill_origin":fill.origin}
    event=EventEnvelope("paper-fill-event-1","ORDER_FILLED","order","paper-order-1",1,0,"offline-paper",OperatingMode.PAPER,1,now,now,now,1,"trading-os-cli","paper-fill-event-1","offline-v1",payload)
    stored=store.append(event,0)
    ledger=store.replay(ledger_reducer,LedgerState())
    store.close(); governor.close()
    return {**output,"target":target,"intent":intent,"risk":decision,"plan":plan,"fill":fill,"ledger":ledger,"event_hash":stored.content_hash}


def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(prog="trading-os",description=__doc__)
    parser.add_argument("--db",type=Path,default=Path("trading-os.db"))
    sub=parser.add_subparsers(dest="command",required=True)
    sub.add_parser("check")
    sub.add_parser("capabilities")
    for name in ("research","paper","proposal"):
        p=sub.add_parser(name); p.add_argument("--fixture",type=Path,default=DEFAULT_FIXTURE)
    sub.add_parser("replay")
    sub.add_parser("status")
    sub.add_parser("report")
    args=parser.parse_args(argv)
    if args.command=="check":
        emit({"valid":True,"config":"config/trading-os.example.json","real_money_autosubmit":False,"default_mode":"RESEARCH","fixture_exists":DEFAULT_FIXTURE.exists()}); return 0
    if args.command=="capabilities":
        emit({"schema":"capability-matrix/v2","default":"DENY","modes":CAPABILITY_MATRIX,"immutable_denies":IMMUTABLE_DENIES}); return 0
    if args.command=="research": emit(research(args.fixture)); return 0
    if args.command=="paper": emit(paper(args.fixture,args.db)); return 0
    if args.command=="proposal":
        r=research(args.fixture); bars=load_bars(args.fixture); now=bars[-1].available_at; ins=instrument()
        target=construct_portfolio(r["arbitrated"],ins.base.canonical)
        intent=compile_intent(target,ins,Decimal("100000"),bars[-1].close,Decimal("0"),now,OperatingMode.LIVE_PROPOSAL,1,"offline-v1")
        plan=build_limit_plan(intent,"proposal-risk-review","live-proposal-1",now)
        emit(GateProposalAdapter({plan.plan_id:"BTC_USDT"}).render(plan)); return 0
    if args.command=="replay":
        store=SQLiteEventStore(str(args.db)); state=store.replay(ledger_reducer,LedgerState()); count=len(store.load()); store.close()
        emit({"events":count,"ledger":state,"external_write_requests":0}); return 0
    if args.command=="status":
        store=SQLiteEventStore(str(args.db)); events=store.load(); store.close()
        risk_path=Path(str(args.db)+".risk"); risk=RiskGovernor(str(risk_path)); status=risk.status(); risk.close()
        emit({"event_count":len(events),"risk":status,"orders":[{"aggregate_id":e.aggregate_id,"type":e.event_type} for e in events if e.event_type.startswith("ORDER_")]}); return 0
    if args.command=="report":
        sample=attribute(Decimal("1"),Decimal("100"),Decimal("101"),Decimal("102"),Decimal("110"),Decimal("0.1"))
        emit({"attribution":sample,"alpha":alpha_performance("trend",[],[]),"counterfactuals":"SEPARATE_NOT_REAL_PNL"}); return 0
    return 2


if __name__=="__main__": raise SystemExit(main())
