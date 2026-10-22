"""Provider-independent value objects; no SDK or authentication dependencies."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

@dataclass(frozen=True)
class SourceAccount:
    id: str
    household_id: str
    provider: str
    owner_type: str
    owner_id: str | None
    external_account: str | None = None
    enabled: bool = True

@dataclass(frozen=True)
class RawRecord:
    provider_object_id: str
    payload: dict[str, Any] = field(repr=False)

@dataclass(frozen=True)
class NormalizedRecord:
    provider_object_id: str
    record_type: str
    provider_thread_id: str | None = None
    occurred_at: datetime | None = None
    subject: str | None = None
    sender: str | None = None
    recipients: tuple[str, ...] = ()
    content_text: str | None = field(default=None, repr=False)
    metadata: dict[str, Any] = field(default_factory=dict, repr=False)

@dataclass(frozen=True)
class ChangeBatch:
    records: tuple[RawRecord, ...]
    next_cursor: str | None
    has_more: bool = False
