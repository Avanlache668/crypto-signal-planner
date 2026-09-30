from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest

from trading_os.contracts import AssetId, InstrumentId, OperatingMode, SignalState
from trading_os.research import Bar, RegimeRule, arbitrate, assess_regime, compile_intent, construct_portfolio, generate_alphas

NOW=datetime(2026,1,22,tzinfo=timezone.utc)


class ResearchTests(unittest.TestCase):
    def setUp(self):
        btc=AssetId("native","BTC"); usd=AssetId("native","USD")
        self.instrument=InstrumentId("offline","SPOT",btc,usd,usd)
        self.bars=[Bar(NOW-timedelta(days=21-i),Decimal(100+i),Decimal(1000)) for i in range(21)]
        self.counter=iter(range(99))

    def ids(self): return "s"+str(next(self.counter))

    def test_future_bars_are_not_read(self):
        base=generate_alphas(self.instrument,"state",self.bars,NOW,self.ids)
        future=self.bars+[Bar(NOW+timedelta(seconds=1),Decimal("1"),Decimal("1"))]
        self.counter=iter(range(99)); other=generate_alphas(self.instrument,"state",future,NOW,self.ids)
        self.assertEqual([(x.direction,x.score) for x in base],[(x.direction,x.score) for x in other])

    def test_uncalibrated_scores_only_watch(self):
        signals=generate_alphas(self.instrument,"state",self.bars,NOW,self.ids)
        result=arbitrate(signals,NOW)
        self.assertEqual(result.state,SignalState.WATCH)
        self.assertTrue(all(v=="uncalibrated" for v in result.excluded.values()))

    def test_same_source_alphas_are_group_capped_and_disagreement_visible(self):
        signals=generate_alphas(self.instrument,"state",self.bars,NOW,self.ids,calibration_ref="fixture-calibration")
        result=arbitrate(signals,NOW,group_cap=Decimal("1"))
        self.assertLessEqual(len(result.included_refs),2)
        self.assertGreaterEqual(result.disagreement,Decimal("0"))

    def test_regime_hysteresis_and_ttl(self):
        rule=RegimeRule(Decimal("0.7"),Decimal("0.5"),2,timedelta(hours=1))
        one=assess_regime("BTC","trend",Decimal("0.8"),NOW,rule,consecutive=1)
        two=assess_regime("BTC","trend",Decimal("0.8"),NOW,rule,consecutive=2)
        self.assertEqual((one.status,two.status),("UNCERTAIN","ACTIVE"))
        self.assertEqual(two.valid_until,NOW+timedelta(hours=1))

    def test_intent_is_target_delta_not_repeat_buy(self):
        signals=generate_alphas(self.instrument,"state",self.bars,NOW,self.ids,calibration_ref="fixture")
        target=construct_portfolio(arbitrate(signals,NOW),self.instrument.base.canonical,max_weight=Decimal("0.05"))
        first=compile_intent(target,self.instrument,Decimal("1000"),Decimal("100"),Decimal("0"),NOW,OperatingMode.PAPER,1,"p1")
        retry=compile_intent(target,self.instrument,Decimal("1000"),Decimal("100"),first.target_quantity,NOW,OperatingMode.PAPER,1,"p1")
        self.assertEqual(retry.delta,Decimal("0"))


if __name__ == "__main__": unittest.main()
