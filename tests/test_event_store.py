from decimal import Decimal
import unittest

from helpers import event
from trading_os.errors import ConcurrencyError, DuplicateEvent
from trading_os.event_store import SQLiteEventStore
from trading_os.ledger import LedgerState, ledger_reducer


class EventStoreTests(unittest.TestCase):
    def setUp(self): self.store = SQLiteEventStore()
    def tearDown(self): self.store.close()

    def test_append_concurrency_hash_chain_and_replay(self):
        one = self.store.append(event("e1", "EXTERNAL_FLOW_RECORDED", 1, {"asset":"USDT", "amount":"1000"}), 0)
        two = self.store.append(event("e2", "CORRECTION_RECORDED", 2, {"asset":"USDT", "amount":"-1", "reason":"bank fee", "corrects_event_id":"e1"}), 1)
        self.assertEqual(two.previous_hash, one.content_hash)
        state = self.store.replay(ledger_reducer, LedgerState())
        self.assertEqual(state.balances["USDT"], Decimal("999"))
        with self.assertRaises(ConcurrencyError): self.store.append(event("e3", "X", 2), 1)

    def test_duplicate_inbox_and_event_are_rejected(self):
        self.assertTrue(self.store.receive_once("venue", "m1"))
        self.assertFalse(self.store.receive_once("venue", "m1"))
        self.store.append(event("e1", "X", 1), 0)
        with self.assertRaises(DuplicateEvent): self.store.append(event("e1", "X", 1, aggregate_id="b"), 0)

    def test_transactional_outbox_and_unknown(self):
        self.store.append(event("e1", "ORDER_SEND_REQUESTED", 1), 0, ("o1", "fake", {"order":"x"}))
        self.assertEqual(len(self.store.pending_outbox()), 1)
        self.store.mark_outbox("o1", "UNKNOWN", "timeout")
        self.assertEqual(len(self.store.pending_outbox()), 0)

    def test_fill_is_idempotent_and_fee_not_double_counted(self):
        payload = {"fill_id":"f1", "quantity":"2", "price":"10", "fee_amount":"0.1", "base":"BTC", "quote":"USDT", "fee_asset":"USDT", "side":"buy"}
        fill = event("e1", "ORDER_FILLED", 1, payload)
        state = ledger_reducer(LedgerState(), fill)
        state = ledger_reducer(state, fill)
        self.assertEqual(state.balances, {"BTC":Decimal("2"), "USDT":Decimal("-20.1")})
        self.assertEqual(state.fees["USDT"], Decimal("0.1"))

    def test_snapshot_hash_is_verified(self):
        self.store.save_snapshot("x", "a", 1, 2, "r1", {"cash":"10"})
        self.assertEqual(self.store.load_snapshot("x", "a")["state"], {"cash":"10"})
        self.store.connection.execute("UPDATE snapshots SET state='{}'")
        with self.assertRaises(Exception): self.store.load_snapshot("x", "a")

    def test_replay_rejects_tampered_event_chain(self):
        self.store.append(event("e1", "EXTERNAL_FLOW_RECORDED", 1, {"asset":"USD","amount":"1"}), 0)
        self.store.connection.execute("UPDATE events SET payload='{}' WHERE event_id='e1'")
        with self.assertRaises(Exception): self.store.replay(ledger_reducer, LedgerState())


if __name__ == "__main__": unittest.main()
