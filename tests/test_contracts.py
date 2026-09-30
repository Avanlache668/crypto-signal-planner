from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest

from trading_os.contracts import (
    AssetId, DataRequirement, DerivedState, InferredState, InstrumentId,
    KnowledgeType, MarketState, ObservedState,
)
from trading_os.errors import ValidationError

UTC = timezone.utc
NOW = datetime(2026, 1, 1, tzinfo=UTC)


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.btc = AssetId("native", "BTC")
        self.usdt = AssetId("token", "USDT", "ethereum", "0xdac17")
        self.instrument = InstrumentId("offline", "SPOT", self.btc, self.usdt, self.usdt)

    def test_identity_is_not_ticker_only_for_tokens(self):
        with self.assertRaises(ValidationError):
            AssetId("token", "LINK")

    def test_observed_inferred_are_not_interchangeable(self):
        inferred = InferredState("price", "100", "USDT", NOW, NOW + timedelta(minutes=5), ("model",))
        state = MarketState("s", NOW, NOW, self.instrument, (inferred,), "hash")
        requirement = DataRequirement(frozenset({"price"}), timedelta(minutes=5), timedelta(seconds=1), frozenset({KnowledgeType.OBSERVED}))
        self.assertEqual(requirement.validate(state, NOW), ("knowledge:price:INFERRED",))

    def test_no_future_data_leakage(self):
        price = ObservedState("price", "100", "USDT", NOW + timedelta(seconds=1), NOW + timedelta(minutes=5), ("feed:1",))
        state = MarketState("s", NOW, NOW, self.instrument, (price,), "hash")
        requirement = DataRequirement(frozenset({"price"}), timedelta(minutes=5), timedelta(seconds=1), frozenset({KnowledgeType.OBSERVED}))
        self.assertIn("future:price", requirement.validate(state, NOW))

    def test_derived_requires_inputs(self):
        with self.assertRaises(ValidationError):
            DerivedState("sma", Decimal("100"), "USDT", NOW, NOW, ("transform:v1",))

    def test_stale_quote_and_orderbook_gap_block_execution_requirements(self):
        price = ObservedState("price", "100", "USDT", NOW - timedelta(minutes=10), NOW - timedelta(minutes=5), ("feed:1",))
        state = MarketState("s", NOW - timedelta(minutes=10), NOW, self.instrument, (price,), "hash")
        requirement = DataRequirement(frozenset({"price", "orderbook_sequence_contiguous"}), timedelta(minutes=2), timedelta(seconds=2), frozenset({KnowledgeType.OBSERVED}))
        errors = requirement.validate(state, NOW)
        self.assertIn("stale:price", errors)
        self.assertIn("missing:orderbook_sequence_contiguous", errors)


if __name__ == "__main__":
    unittest.main()
