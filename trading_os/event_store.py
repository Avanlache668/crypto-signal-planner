"""Transactional SQLite event store with optimistic concurrency and outbox."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import json
import sqlite3
from typing import Any, Callable, Iterable, TypeVar

from .contracts import EventEnvelope, OperatingMode
from .errors import ConcurrencyError, DuplicateEvent, ValidationError
from .serialization import canonical_json, content_hash

T = TypeVar("T")


class SQLiteEventStore:
    def __init__(self, path: str = ":memory:") -> None:
        self.connection = sqlite3.connect(path, isolation_level=None)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.connection.executescript("""
        CREATE TABLE IF NOT EXISTS events(
          stream_sequence INTEGER PRIMARY KEY AUTOINCREMENT,
          event_id TEXT NOT NULL UNIQUE, event_type TEXT NOT NULL,
          aggregate_type TEXT NOT NULL, aggregate_id TEXT NOT NULL,
          aggregate_version INTEGER NOT NULL, run_id TEXT NOT NULL,
          mode TEXT NOT NULL, mode_epoch INTEGER NOT NULL,
          occurred_at TEXT NOT NULL, recorded_at TEXT NOT NULL, available_at TEXT NOT NULL,
          logical_time INTEGER NOT NULL, producer TEXT NOT NULL,
          idempotency_key TEXT NOT NULL UNIQUE, policy_version TEXT NOT NULL,
          payload TEXT NOT NULL, previous_hash TEXT, content_hash TEXT NOT NULL,
          schema_version TEXT NOT NULL,
          UNIQUE(aggregate_type, aggregate_id, aggregate_version)
        );
        CREATE TABLE IF NOT EXISTS inbox(
          source TEXT NOT NULL, message_id TEXT NOT NULL, received_at TEXT NOT NULL,
          PRIMARY KEY(source, message_id));
        CREATE TABLE IF NOT EXISTS outbox(
          outbox_id TEXT PRIMARY KEY, event_id TEXT NOT NULL, destination TEXT NOT NULL,
          payload TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'PENDING',
          attempts INTEGER NOT NULL DEFAULT 0, last_error TEXT,
          FOREIGN KEY(event_id) REFERENCES events(event_id));
        CREATE TABLE IF NOT EXISTS snapshots(
          aggregate_type TEXT NOT NULL, aggregate_id TEXT NOT NULL,
          aggregate_version INTEGER NOT NULL, stream_sequence INTEGER NOT NULL,
          reducer_version TEXT NOT NULL, state TEXT NOT NULL, state_hash TEXT NOT NULL,
          PRIMARY KEY(aggregate_type, aggregate_id));
        """)

    def close(self) -> None:
        self.connection.close()

    def _version_and_hash(self, aggregate_type: str, aggregate_id: str) -> tuple[int, str | None]:
        row = self.connection.execute(
            "SELECT aggregate_version, content_hash FROM events WHERE aggregate_type=? AND aggregate_id=? ORDER BY aggregate_version DESC LIMIT 1",
            (aggregate_type, aggregate_id),
        ).fetchone()
        return (int(row[0]), str(row[1])) if row else (0, None)

    def append(self, event: EventEnvelope, expected_version: int, outbox: tuple[str, str, dict[str, Any]] | None = None) -> EventEnvelope:
        with self.connection:
            actual_version, previous_hash = self._version_and_hash(event.aggregate_type, event.aggregate_id)
            if actual_version != expected_version:
                raise ConcurrencyError(f"expected version {expected_version}, got {actual_version}")
            if event.aggregate_version != expected_version + 1:
                raise ValidationError("aggregate_version must increment by one")
            now = datetime.now(timezone.utc)
            unsigned = replace(event, stream_sequence=0, recorded_at=now, previous_hash=previous_hash, content_hash=None)
            digest = content_hash({"event": unsigned, "previous_hash": previous_hash})
            try:
                cursor = self.connection.execute(
                    """INSERT INTO events(event_id,event_type,aggregate_type,aggregate_id,aggregate_version,run_id,mode,mode_epoch,occurred_at,recorded_at,available_at,logical_time,producer,idempotency_key,policy_version,payload,previous_hash,content_hash,schema_version)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (event.event_id, event.event_type, event.aggregate_type, event.aggregate_id,
                     event.aggregate_version, event.run_id, event.mode.value, event.mode_epoch,
                     event.occurred_at.isoformat(), now.isoformat(), event.available_at.isoformat(),
                     event.logical_time, event.producer, event.idempotency_key, event.policy_version,
                     canonical_json(event.payload), previous_hash, digest, event.schema_version),
                )
            except sqlite3.IntegrityError as exc:
                raise DuplicateEvent(str(exc)) from exc
            stored = replace(unsigned, stream_sequence=int(cursor.lastrowid), content_hash=digest)
            if outbox:
                outbox_id, destination, payload = outbox
                self.connection.execute(
                    "INSERT INTO outbox(outbox_id,event_id,destination,payload) VALUES(?,?,?,?)",
                    (outbox_id, event.event_id, destination, canonical_json(payload)),
                )
            return stored

    def receive_once(self, source: str, message_id: str) -> bool:
        try:
            with self.connection:
                self.connection.execute(
                    "INSERT INTO inbox(source,message_id,received_at) VALUES(?,?,?)",
                    (source, message_id, datetime.now(timezone.utc).isoformat()),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def load(self, aggregate_type: str | None = None, aggregate_id: str | None = None) -> list[EventEnvelope]:
        sql = "SELECT * FROM events"
        params: list[str] = []
        clauses: list[str] = []
        if aggregate_type:
            clauses.append("aggregate_type=?"); params.append(aggregate_type)
        if aggregate_id:
            clauses.append("aggregate_id=?"); params.append(aggregate_id)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY stream_sequence"
        return [self._event(row) for row in self.connection.execute(sql, params)]

    @staticmethod
    def _event(row: sqlite3.Row) -> EventEnvelope:
        parse = datetime.fromisoformat
        return EventEnvelope(
            event_id=row["event_id"], event_type=row["event_type"], aggregate_type=row["aggregate_type"],
            aggregate_id=row["aggregate_id"], aggregate_version=row["aggregate_version"],
            stream_sequence=row["stream_sequence"], run_id=row["run_id"], mode=OperatingMode(row["mode"]),
            mode_epoch=row["mode_epoch"], occurred_at=parse(row["occurred_at"]), recorded_at=parse(row["recorded_at"]),
            available_at=parse(row["available_at"]), logical_time=row["logical_time"], producer=row["producer"],
            idempotency_key=row["idempotency_key"], policy_version=row["policy_version"],
            payload=json.loads(row["payload"]), previous_hash=row["previous_hash"], content_hash=row["content_hash"],
            schema_version=row["schema_version"],
        )

    def replay(self, reducer: Callable[[T, EventEnvelope], T], initial: T, *, aggregate_type: str | None = None, aggregate_id: str | None = None) -> T:
        state = initial
        for event in self.load(aggregate_type, aggregate_id):
            state = reducer(state, event)
        return state

    def save_snapshot(self, aggregate_type: str, aggregate_id: str, version: int, sequence: int, reducer_version: str, state: Any) -> None:
        encoded = canonical_json(state)
        digest = content_hash(state)
        with self.connection:
            self.connection.execute(
                """INSERT INTO snapshots VALUES(?,?,?,?,?,?,?)
                ON CONFLICT(aggregate_type,aggregate_id) DO UPDATE SET aggregate_version=excluded.aggregate_version,stream_sequence=excluded.stream_sequence,reducer_version=excluded.reducer_version,state=excluded.state,state_hash=excluded.state_hash""",
                (aggregate_type, aggregate_id, version, sequence, reducer_version, encoded, digest),
            )

    def load_snapshot(self, aggregate_type: str, aggregate_id: str) -> dict[str, Any] | None:
        row = self.connection.execute("SELECT * FROM snapshots WHERE aggregate_type=? AND aggregate_id=?", (aggregate_type, aggregate_id)).fetchone()
        if not row:
            return None
        state = json.loads(row["state"])
        if content_hash(state) != row["state_hash"]:
            raise ValidationError("snapshot hash mismatch")
        return {"version": row["aggregate_version"], "sequence": row["stream_sequence"], "reducer_version": row["reducer_version"], "state": state}

    def pending_outbox(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self.connection.execute("SELECT * FROM outbox WHERE status='PENDING' ORDER BY rowid")]

    def mark_outbox(self, outbox_id: str, status: str, error: str | None = None) -> None:
        if status not in {"SENT", "UNKNOWN", "FAILED"}:
            raise ValidationError("invalid outbox status")
        with self.connection:
            self.connection.execute("UPDATE outbox SET status=?,attempts=attempts+1,last_error=? WHERE outbox_id=?", (status, error, outbox_id))

