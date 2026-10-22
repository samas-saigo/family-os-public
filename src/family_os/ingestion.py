"""Atomic read-only ingestion. Provider identity dedupe only, not entity merging."""
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import logging
import unicodedata
from uuid import uuid4
from sqlalchemy import select, update
from .connectors import Connector
from .domain import NormalizedRecord
from .errors import IngestionError, ConcurrentSyncError
from .registry import get_account, require_id
from .schema import raw_source_record, source_record, source_sync_state
from .storage import insert_for, upsert

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class IngestionResult:
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    pages: int = 0

# Default persistence policy: metadata only. Content may be hashed transiently.
FORBIDDEN_KEYS = frozenset({"access_token", "refresh_token", "id_token", "authorization",
    "password", "client_secret", "api_key", "cookie", "cookies", "body", "body_html",
    "body_text", "full_text", "attachment_content", "snippet", "bodypreview", "uniquebody", "$value",
    "internetmessageheaders", "contentbytes", "mime_content", "attachment_bytes", "singlevalueextendedproperties", "multivalueextendedproperties", "description", "extendedproperties",
    "privatecopy", "gadget", "conferencedata", "attachmenturl", "fileurl"})

# Gmail legitimately retains minimized attachment metadata. Calendar excludes it entirely.
CALENDAR_FORBIDDEN_KEYS = FORBIDDEN_KEYS | {"attachments", "source", "hangoutlink"}

DRIVE_FORBIDDEN_KEYS = FORBIDDEN_KEYS | {"properties", "appproperties", "contenthints",
    "imagemediametadata", "videomediametadata", "permissions", "exportlinks", "webcontentlink",
    "webviewlink", "iconlink", "resourcekey", "targetresourcekey", "thumbnail", "thumbnaillink",
    "thumbnailversion", "labels", "labelinfo", "comments", "replies", "revisions", "content", "filecontents", "token", "credentials", "authorization_code"}

def json_snapshot(value, forbidden_keys=FORBIDDEN_KEYS):
    def inspect(node):
        if isinstance(node, dict):
            for key, child in node.items():
                if not isinstance(key, str) or key.casefold() in forbidden_keys:
                    raise ValueError("Metadata contains prohibited fields")
                inspect(child)
        elif isinstance(node, (list, tuple)):
            for child in node:
                inspect(child)
    inspect(value)
    # Copy nested mutable values and reject NaN/non-JSON types before starting a transaction.
    return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))

def content_hash(text):
    if text is None or text == "":
        return None
    normalized = unicodedata.normalize("NFC", text.replace("\r\n", "\n").replace("\r", "\n"))
    return sha256(normalized.encode("utf-8")).hexdigest()

def normalized_values(record: NormalizedRecord, forbidden_keys=FORBIDDEN_KEYS):
    require_id(record.provider_object_id)
    require_id(record.record_type)
    occurred_at = record.occurred_at
    if occurred_at is not None:
        if occurred_at.tzinfo is None or occurred_at.utcoffset() is None:
            raise ValueError("Source timestamp must have a timezone")
        occurred_at = occurred_at.astimezone(timezone.utc)
    if not all(isinstance(address, str) for address in record.recipients):
        raise ValueError("Recipients must be strings")
    metadata = json_snapshot(record.metadata, forbidden_keys)
    if not isinstance(metadata, dict):
        raise ValueError("Metadata must be an object")
    return dict(provider_object_id=record.provider_object_id, record_type=record.record_type,
        provider_thread_id=record.provider_thread_id, occurred_at=occurred_at,
        subject=record.subject, sender=record.sender, recipients=list(record.recipients),
        content_hash=content_hash(record.content_text), raw_metadata=metadata)

def ingest(engine, household_id: str, account_id: str, connector: Connector,
           max_pages: int = 1000) -> IngestionResult:
    if max_pages < 1:
        raise ValueError("max_pages must be positive")
    totals = [0, 0, 0]
    for page in range(1, max_pages + 1):
        try:
            with engine.connect() as connection:
                account = get_account(connection, household_id, account_id)
                state = connection.execute(select(source_sync_state).where(
                    source_sync_state.c.source_account_id == account_id)).mappings().one()
            if not account.enabled:
                raise ValueError("Account is disabled")
            if account.provider != connector.provider:
                raise ValueError("Connector provider does not match account")
            batch = connector.fetch_changes(account, state["cursor"])
            if batch.next_cursor is not None and not isinstance(batch.next_cursor, str):
                raise ValueError("Cursor must be a string or null")
            if batch.has_more and batch.next_cursor == state["cursor"]:
                raise ValueError("Connector pagination did not advance")
            forbidden = (CALENDAR_FORBIDDEN_KEYS if account.provider == "google_calendar" else
                         DRIVE_FORBIDDEN_KEYS if account.provider == "google_drive" else FORBIDDEN_KEYS)
            prepared = []
            for raw in batch.records:
                require_id(raw.provider_object_id)
                payload = json_snapshot(raw.payload, forbidden)
                if not isinstance(payload, dict):
                    raise ValueError("Raw payload must be an object")
                normalized = normalized_values(connector.normalize(raw), forbidden)
                if normalized["provider_object_id"] != raw.provider_object_id:
                    raise ValueError("Normalization changed provider identity")
                digest = sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                    separators=(",", ":")).encode("utf-8")).hexdigest()
                prepared.append((raw.provider_object_id, payload, digest, normalized))
            counts = [0, 0, 0]
            now = datetime.now(timezone.utc)
            with engine.begin() as connection:
                # A compare-and-swap locks this account's state for the page transaction.
                changed = connection.execute(update(source_sync_state).where(
                    source_sync_state.c.source_account_id == account_id,
                    source_sync_state.c.version == state["version"]).values(
                    version=state["version"] + 1, cursor=batch.next_cursor, updated_at=now))
                if changed.rowcount != 1:
                    raise ConcurrentSyncError("Account sync changed; retry from its saved cursor")
                if get_account(connection, household_id, account_id) != account:
                    raise IngestionError("Account configuration changed; retry sync")
                for object_id, payload, digest, normalized in prepared:
                    raw_id = str(uuid4())
                    statement = insert_for(connection, raw_source_record).values(id=raw_id,
                        household_id=household_id, source_account_id=account_id,
                        provider_object_id=object_id, payload_hash=digest, payload=payload, ingested_at=now)
                    connection.execute(statement.on_conflict_do_nothing(index_elements=[
                        "source_account_id", "provider_object_id", "payload_hash"]))
                    raw_id = connection.scalar(select(raw_source_record.c.id).where(
                        raw_source_record.c.source_account_id == account_id,
                        raw_source_record.c.provider_object_id == object_id,
                        raw_source_record.c.payload_hash == digest))
                    existing = connection.execute(select(source_record).where(
                        source_record.c.source_account_id == account_id,
                        source_record.c.provider_object_id == object_id)).mappings().first()
                    values = dict(normalized, raw_record_id=raw_id)
                    def comparable(value):
                        if isinstance(value, datetime):
                            # SQLite returns naive UTC values; API timestamps are always aware.
                            return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
                        return value
                    if existing and all(comparable(existing[key]) == comparable(value) for key, value in values.items()):
                        counts[2] += 1
                        continue
                    upsert(connection, source_record, dict(values, id=str(uuid4()),
                        household_id=household_id, source_account_id=account_id,
                        ingested_at=now, updated_at=now), ["source_account_id", "provider_object_id"],
                        [*values, "updated_at"])
                    counts[1 if existing else 0] += 1
            totals = [a + b for a, b in zip(totals, counts)]
            logger.info("Ingestion page committed: inserted=%d updated=%d unchanged=%d", *counts)
            if not batch.has_more:
                return IngestionResult(*totals, pages=page)
        except IngestionError:
            logger.warning("Ingestion page failed; its records and cursor were rolled back")
            raise
        except Exception:
            # Provider exceptions often include URLs/tokens. Do not log exception text/tracebacks.
            logger.warning("Ingestion page failed; its records and cursor were rolled back")
            raise IngestionError("Ingestion failed; check connector/configuration and retry") from None
    raise IngestionError("Page limit reached; resume from the committed cursor")
