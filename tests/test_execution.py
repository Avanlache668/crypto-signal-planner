from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest

from trading_os.contracts import AssetId, Capability, InstrumentId, OperatingMode, TradeIntent
from trading_os.errors import CapabilityDenied, ValidationError
from trading_os.execution import BookLevel, GateProposalAdapter, OrderState, PaperFillModel, PaperSimulator, TestNetGateAdapter, build_limit_plan, order_reducer
from trading_os.governance import ModeController, TESTNET_HOST, validate_parameter_update

NOW=datetime(2026,1,1,tzinfo=timezone.utc)


def intent(mode=OperatingMode.PAPER,epoch=1,current=Decimal("0")):
    btc=AssetId("native","BTC"); usd=AssetId("native","USD")
    instrument=InstrumentId("gate","SPOT",btc,usd,usd)
    return TradeIntent("i",instrument,Decimal("2"),current,Decimal("100"),NOW+timedelta(minutes=5),("s",),mode,epoch,"p1")


class ExecutionTests(unittest.TestCase):
    def test_paper_fill_is_depth_limited_and_has_versioned_costs(self):
        plan=build_limit_plan(intent(),"risk","p",NOW)
        fill=PaperSimulator(PaperFillModel()).simulate(plan,(BookLevel(Decimal("99"),Decimal("5")),),intent().instrument.quote,NOW,"f")
        self.assertEqual(fill.quantity,Decimal("0.5"))
        self.assertTrue(fill.origin.startswith("SIMULATED:"))
        self.assertGreater(fill.fee.amount,0)

    def test_cancel_fill_race_and_duplicate_fill(self):
        state=order_reducer(OrderState(),"ORDER_CANCEL_REQUESTED",{})
        state=order_reducer(state,"ORDER_CANCELLED",{})
        state=order_reducer(state,"ORDER_FILLED",{"fill_id":"f","quantity":"1","remaining":"0"})
        again=order_reducer(state,"ORDER_FILLED",{"fill_id":"f","quantity":"1","remaining":"0"})
        self.assertEqual(again.filled,Decimal("1")); self.assertEqual(again.reconciliation,"DISPUTED")

    def test_all_modes_deny_live_writes(self):
        for mode in OperatingMode:
            controller=ModeController(mode)
            cap=Capability("SEND_LIVE_ORDER",mode,None,"live",1,NOW+timedelta(minutes=1),"p1")
            with self.assertRaises(CapabilityDenied): controller.authorize(cap,"SEND_LIVE_ORDER",NOW,host="https://api.gateio.ws")

    def test_testnet_host_substitution_and_old_epoch_are_rejected(self):
        controller=ModeController(OperatingMode.TESTNET)
        cap=Capability("SEND_TESTNET_LIMIT",OperatingMode.TESTNET,"test","testnet",1,NOW+timedelta(minutes=1),"p1")
        plan=build_limit_plan(intent(OperatingMode.TESTNET),"r","p",NOW)
        called=[]
        with self.assertRaises(CapabilityDenied): TestNetGateAdapter("https://api.gateio.ws",called.append).send(plan,cap,controller,NOW)
        controller.switch(OperatingMode.PAPER,reconciled=True,pending_commands=0)
        with self.assertRaises(CapabilityDenied): TestNetGateAdapter(TESTNET_HOST,called.append).send(plan,cap,controller,NOW)
        self.assertEqual(called,[])

    def test_live_proposal_is_unsigned_and_never_sends(self):
        plan=build_limit_plan(intent(OperatingMode.LIVE_PROPOSAL),"r","p",NOW)
        result=GateProposalAdapter({"p":"BTC_USDT"}).render(plan)
        self.assertFalse(result["live_submission_available"])
        self.assertEqual(result["execution_state"],"PROPOSAL_ONLY")

    def test_learning_cannot_change_safety_rules(self):
        with self.assertRaises(CapabilityDenied): validate_parameter_update("LEARNED",{"daily_loss_limit":"999"})


if __name__ == "__main__": unittest.main()
