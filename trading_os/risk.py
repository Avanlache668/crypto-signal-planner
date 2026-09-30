"""Independent, persistent risk control plane."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
import sqlite3

from .contracts import RiskAction, RiskBudget, RiskDecision
from .errors import ConcurrencyError, ValidationError


@dataclass(frozen=True)
class RiskSnapshot:
    gross_exposure: Decimal | None
    asset_exposure: Decimal | None
    daily_pnl: Decimal | None
    weekly_pnl: Decimal | None
    drawdown: Decimal | None
    volatility: Decimal | None
    liquidity_notional: Decimal | None
    correlation_exposure: Decimal | None
    data_valid: bool
    model_eligible: bool
    exchange_healthy: bool
    event_risk: bool = False


class RiskGovernor:
    def __init__(self, path: str = ":memory:", clock=None) -> None:
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.connection = sqlite3.connect(path, isolation_level=None, timeout=10)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript("""
        CREATE TABLE IF NOT EXISTS risk_budgets(
          budget_id TEXT PRIMARY KEY, currency TEXT NOT NULL, gross_limit TEXT NOT NULL,
          per_asset_limit TEXT NOT NULL, daily_loss_limit TEXT NOT NULL,
          weekly_loss_limit TEXT NOT NULL, drawdown_limit TEXT NOT NULL,
          policy_version TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS reservations(
          reservation_id TEXT PRIMARY KEY, budget_id TEXT NOT NULL, intent_id TEXT NOT NULL UNIQUE,
          asset TEXT NOT NULL, amount TEXT NOT NULL, committed TEXT NOT NULL DEFAULT '0',
          status TEXT NOT NULL, mode_epoch INTEGER NOT NULL, expires_at TEXT NOT NULL,
          FOREIGN KEY(budget_id) REFERENCES risk_budgets(budget_id));
        CREATE TABLE IF NOT EXISTS risk_control(
          singleton INTEGER PRIMARY KEY CHECK(singleton=1), killed INTEGER NOT NULL,
          reason TEXT, triggered_at TEXT, recovery_authorization TEXT);
        INSERT OR IGNORE INTO risk_control(singleton,killed) VALUES(1,0);
        """)

    def close(self) -> None: self.connection.close()

    def install_budget(self, budget: RiskBudget) -> None:
        with self.connection:
            self.connection.execute(
                "INSERT OR REPLACE INTO risk_budgets VALUES(?,?,?,?,?,?,?,?)",
                (budget.budget_id, budget.currency.canonical, str(budget.gross_limit), str(budget.per_asset_limit),
                 str(budget.daily_loss_limit), str(budget.weekly_loss_limit), str(budget.drawdown_limit), budget.policy_version),
            )

    @property
    def killed(self) -> bool:
        return bool(self.connection.execute("SELECT killed FROM risk_control WHERE singleton=1").fetchone()[0])

    def evaluate(self, decision_id: str, requested: Decimal, snapshot: RiskSnapshot, budget: RiskBudget) -> RiskDecision:
        requested = Decimal(str(requested))
        missing = [name for name in ("gross_exposure", "asset_exposure", "daily_pnl", "weekly_pnl", "drawdown", "volatility", "liquidity_notional", "correlation_exposure") if getattr(snapshot, name) is None]
        if self.killed:
            return RiskDecision(decision_id, RiskAction.KILL, ("persistent_kill",), Decimal("0"), budget.policy_version)
        if missing or not snapshot.data_valid:
            return RiskDecision(decision_id, RiskAction.BLOCK, ("missing_or_invalid:" + ",".join(missing),), Decimal("0"), budget.policy_version)
        if not snapshot.exchange_healthy or not snapshot.model_eligible:
            return RiskDecision(decision_id, RiskAction.BLOCK, ("exchange_or_model_risk",), Decimal("0"), budget.policy_version)
        if snapshot.daily_pnl < -budget.daily_loss_limit or snapshot.weekly_pnl < -budget.weekly_loss_limit or snapshot.drawdown > budget.drawdown_limit:
            return RiskDecision(decision_id, RiskAction.FREEZE, ("loss_or_drawdown_limit",), Decimal("0"), budget.policy_version)
        capacity = min(budget.gross_limit - snapshot.gross_exposure, budget.per_asset_limit - snapshot.asset_exposure, snapshot.liquidity_notional)
        if snapshot.event_risk or snapshot.volatility > Decimal("0.08") or snapshot.correlation_exposure > Decimal("0.70"):
            capacity = min(capacity, requested / Decimal("2"))
        approved = max(Decimal("0"), min(requested, capacity))
        action = RiskAction.ALLOW if approved == requested else RiskAction.REDUCE if approved > 0 else RiskAction.BLOCK
        return RiskDecision(decision_id, action, ("within_limits",) if action is RiskAction.ALLOW else ("risk_capacity",), approved, budget.policy_version)

    def reserve(self, reservation_id: str, budget_id: str, intent_id: str, asset: str, amount: Decimal, mode_epoch: int, expires_at: datetime) -> None:
        amount = Decimal(str(amount))
        if amount <= 0 or self.killed:
            raise ValidationError("positive reservation and active governor required")
        try:
            self.connection.execute("BEGIN IMMEDIATE")
            budget = self.connection.execute("SELECT gross_limit,per_asset_limit FROM risk_budgets WHERE budget_id=?", (budget_id,)).fetchone()
            if not budget:
                raise ValidationError("unknown budget")
            gross_used = sum((Decimal(row[0]) for row in self.connection.execute("SELECT amount FROM reservations WHERE budget_id=? AND status IN ('RESERVED','COMMITTED','UNKNOWN')", (budget_id,))), Decimal("0"))
            asset_used = sum((Decimal(row[0]) for row in self.connection.execute("SELECT amount FROM reservations WHERE budget_id=? AND asset=? AND status IN ('RESERVED','COMMITTED','UNKNOWN')", (budget_id, asset))), Decimal("0"))
            if gross_used + amount > Decimal(budget[0]) or asset_used + amount > Decimal(budget[1]):
                raise ConcurrencyError("risk budget exhausted")
            self.connection.execute("INSERT INTO reservations VALUES(?,?,?,?,?,'0','RESERVED',?,?)", (reservation_id,budget_id,intent_id,asset,str(amount),mode_epoch,expires_at.astimezone(timezone.utc).isoformat()))
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise

    def commit_fill(self, reservation_id: str, filled_notional: Decimal) -> None:
        row = self.connection.execute("SELECT amount,committed,status FROM reservations WHERE reservation_id=?", (reservation_id,)).fetchone()
        if not row or row["status"] not in {"RESERVED", "COMMITTED", "UNKNOWN"}:
            raise ValidationError("reservation cannot accept fill")
        committed = Decimal(row["committed"]) + Decimal(str(filled_notional))
        if committed > Decimal(row["amount"]):
            raise ValidationError("fill exceeds reserved worst-case amount")
        with self.connection:
            self.connection.execute("UPDATE reservations SET committed=?,status='COMMITTED' WHERE reservation_id=?", (str(committed),reservation_id))

    def mark_unknown(self, reservation_id: str) -> None:
        with self.connection:
            if self.connection.execute("UPDATE reservations SET status='UNKNOWN' WHERE reservation_id=? AND status IN ('RESERVED','COMMITTED')", (reservation_id,)).rowcount != 1:
                raise ValidationError("reservation cannot become unknown")

    def release(self, reservation_id: str, *, externally_confirmed: bool) -> None:
        row = self.connection.execute("SELECT status,committed FROM reservations WHERE reservation_id=?", (reservation_id,)).fetchone()
        if not row or not externally_confirmed:
            raise ValidationError("confirmed reconciliation is required to release")
        if row["status"] == "UNKNOWN":
            raise ValidationError("unknown order must be reconciled before release")
        with self.connection:
            self.connection.execute("UPDATE reservations SET amount=committed,status='RELEASED' WHERE reservation_id=?", (reservation_id,))

    def revalue(self, budget_id: str, multiplier: Decimal) -> bool:
        budget = self.connection.execute("SELECT gross_limit FROM risk_budgets WHERE budget_id=?", (budget_id,)).fetchone()
        used = sum((Decimal(r[0]) * Decimal(str(multiplier)) for r in self.connection.execute("SELECT amount FROM reservations WHERE budget_id=? AND status IN ('RESERVED','COMMITTED','UNKNOWN')", (budget_id,))), Decimal("0"))
        return bool(budget and used > Decimal(budget[0]))

    def trigger_kill(self, reason: str) -> None:
        if not reason: raise ValidationError("kill reason required")
        with self.connection:
            self.connection.execute("UPDATE risk_control SET killed=1,reason=?,triggered_at=?,recovery_authorization=NULL WHERE singleton=1", (reason,self.clock().isoformat()))

    def recover(self, authorization: str, *, reconciled: bool, cause_fixed: bool) -> None:
        if not authorization or not reconciled or not cause_fixed:
            raise ValidationError("authorized recovery requires reconciliation and remediation")
        with self.connection:
            self.connection.execute("UPDATE risk_control SET killed=0,recovery_authorization=? WHERE singleton=1", (authorization,))

    def status(self) -> dict:
        control = dict(self.connection.execute("SELECT * FROM risk_control WHERE singleton=1").fetchone())
        control["reservations"] = [dict(row) for row in self.connection.execute("SELECT * FROM reservations ORDER BY reservation_id")]
        return control
