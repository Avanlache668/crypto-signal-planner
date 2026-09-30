from datetime import datetime, timezone

from trading_os.contracts import EventEnvelope, OperatingMode

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def event(event_id: str, event_type: str, aggregate_version: int, payload=None, aggregate_id="a", mode=OperatingMode.PAPER, epoch=1):
    return EventEnvelope(
        event_id, event_type, "test", aggregate_id, aggregate_version, 0, "run", mode, epoch,
        NOW, NOW, NOW, aggregate_version, "tests", event_id, "policy-v1", payload or {},
    )
