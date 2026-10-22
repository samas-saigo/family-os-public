"""Read-only connector contract and offline fixture adapter."""
import json
from datetime import datetime
from pathlib import Path
from typing import Protocol
from .domain import ChangeBatch, NormalizedRecord, RawRecord, SourceAccount

class Connector(Protocol):
    provider: str

    def fetch_changes(self, account: SourceAccount, cursor: str | None) -> ChangeBatch:
        """Fetch one bounded page. Raise on expired cursors; never silently skip data."""
        ...

    def normalize(self, record: RawRecord) -> NormalizedRecord:
        """Convert a source object without retaining full bodies in metadata."""
        ...

class FixtureConnector:
    """Synthetic JSON only. No network, OAuth, or provider write operations."""
    provider = "fixture"

    def __init__(self, path: str | Path, page_size: int = 100):
        if page_size < 1:
            raise ValueError("page_size must be positive")
        self.records = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(self.records, list):
            raise ValueError("Fixture must be a JSON array")
        self.page_size = page_size

    def fetch_changes(self, account, cursor):
        start = int(cursor or 0)
        if start < 0 or start > len(self.records):
            raise ValueError("Fixture cursor is outside the dataset")
        stop = min(start + self.page_size, len(self.records))
        return ChangeBatch(tuple(RawRecord(item["id"], item) for item in self.records[start:stop]),
                           str(stop), stop < len(self.records))

    def normalize(self, record):
        data = record.payload
        timestamp = data.get("occurred_at")
        return NormalizedRecord(
            provider_object_id=record.provider_object_id,
            record_type=data["record_type"], provider_thread_id=data.get("thread_id"),
            occurred_at=datetime.fromisoformat(timestamp.replace("Z", "+00:00")) if timestamp else None,
            subject=data.get("subject"), sender=data.get("sender"),
            recipients=tuple(data.get("recipients", [])), metadata=data.get("metadata", {}),
        )
