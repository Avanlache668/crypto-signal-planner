from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest

from trading_os.contracts import AssetId, RiskAction, RiskBudget
from trading_os.errors import ConcurrencyError, ValidationError
from trading_os.risk import RiskGovernor, RiskSnapshot

NOW = datetime(2026,1,1,tzinfo=timezone.utc)


def budget():
    return RiskBudget("b", AssetId("native","USD"), Decimal("100"), Decimal("60"), Decimal("10"), Decimal("20"), Decimal("0.2"), "p1")


def snapshot(**updates):
    values = dict(gross_exposure=Decimal("10"),asset_exposure=Decimal("5"),daily_pnl=Decimal("0"),weekly_pnl=Decimal("0"),drawdown=Decimal("0.01"),volatility=Decimal("0.02"),liquidity_notional=Decimal("100"),correlation_exposure=Decimal("0.2"),data_valid=True,model_eligible=True,exchange_healthy=True)
    values.update(updates); return RiskSnapshot(**values)


class RiskTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.path=str(Path(self.temp.name)/"risk.db")
        self.risk=RiskGovernor(self.path); self.risk.install_budget(budget())
    def tearDown(self): self.risk.close(); self.temp.cleanup()

    def test_missing_data_fails_closed(self):
        result=self.risk.evaluate("d",Decimal("10"),snapshot(volatility=None),budget())
        self.assertEqual(result.action,RiskAction.BLOCK)

    def test_atomic_reservation_does_not_overallocate(self):
        self.risk.reserve("r1","b","i1","BTC",Decimal("60"),1,NOW)
        with self.assertRaises(ConcurrencyError): self.risk.reserve("r2","b","i2","ETH",Decimal("50"),1,NOW)

    def test_partial_fill_is_committed_immediately(self):
        self.risk.reserve("r1","b","i1","BTC",Decimal("50"),1,NOW)
        self.risk.commit_fill("r1",Decimal("20"))
        row=self.risk.status()["reservations"][0]
        self.assertEqual((row["committed"],row["status"]),("20","COMMITTED"))

    def test_unknown_never_releases(self):
        self.risk.reserve("r1","b","i1","BTC",Decimal("50"),1,NOW)
        self.risk.mark_unknown("r1")
        with self.assertRaises(ValidationError): self.risk.release("r1",externally_confirmed=True)

    def test_kill_persists_across_restart_and_requires_authorized_recovery(self):
        self.risk.trigger_kill("drawdown")
        self.risk.close(); self.risk=RiskGovernor(self.path)
        self.assertTrue(self.risk.killed)
        with self.assertRaises(ValidationError): self.risk.recover("",reconciled=True,cause_fixed=True)
        self.risk.recover("operator-ticket-1",reconciled=True,cause_fixed=True)
        self.assertFalse(self.risk.killed)


if __name__ == "__main__": unittest.main()
