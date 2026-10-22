from dataclasses import replace
from datetime import datetime, timezone
import pytest
from sqlalchemy import select, func, update
from family_os.domain import RawRecord, NormalizedRecord, ChangeBatch
from family_os.ingestion import ingest, IngestionError, ConcurrentSyncError
from family_os.registry import register
from family_os.schema import raw_source_record, source_record, source_sync_state, source_account

class FakeConnector:
    provider = "fixture"

    def __init__(self, records=None):
        self.records = records if records is not None else [RawRecord("message-1", {"subject": "Demo"})]
        self.cursors = []

    def fetch_changes(self, account, cursor):
        self.cursors.append(cursor)
        return ChangeBatch(tuple(self.records), "done")

    def normalize(self, raw):
        return NormalizedRecord(raw.provider_object_id, "message", subject=raw.payload.get("subject"),
            occurred_at=datetime(2026, 10, 4, tzinfo=timezone.utc), provider_thread_id="thread-1",
            sender="demo@example.invalid", recipients=("alex@example.invalid",), content_text="Synthetic content")

@pytest.fixture
def registered(engine):
    register(engine, {"household": {"id": "home", "name": "Demo"},
        "people": [{"id": "alex", "display_name": "Alex"}],
        "source_accounts": [{"id": account_id, "provider": "fixture", "owner_type": "person", "owner_id": "alex"}
                            for account_id in ("personal", "secondary")]})
    return engine

def rows(engine, table):
    with engine.connect() as connection:
        return connection.execute(select(table).order_by(*table.primary_key.columns)).mappings().all()

def test_repeated_ingestion_is_idempotent_and_preserves_provenance(registered):
    connector = FakeConnector()
    first = ingest(registered, "home", "personal", connector)
    original = rows(registered, source_record)[0]
    second = ingest(registered, "home", "personal", connector)
    assert (first.inserted, second.inserted, second.unchanged) == (1, 0, 1)
    assert rows(registered, source_record)[0] == original
    assert len(rows(registered, raw_source_record)) == 1
    assert connector.cursors == [None, "done"]
    assert original["raw_record_id"] == rows(registered, raw_source_record)[0]["id"]
    assert original["provider_object_id"] == "message-1"
    assert original["provider_thread_id"] == "thread-1"
    assert original["content_hash"]
    assert "Synthetic content" not in str(rows(registered, raw_source_record))

def test_repeated_object_inside_page_and_distinct_accounts(registered):
    raw = RawRecord("message-1", {"subject": "Demo"})
    result = ingest(registered, "home", "personal", FakeConnector([raw, raw]))
    assert (result.inserted, result.unchanged) == (1, 1)
    ingest(registered, "home", "secondary", FakeConnector([raw]))
    assert len(rows(registered, source_record)) == 2
    assert len(rows(registered, raw_source_record)) == 2

def test_changed_object_retains_raw_history_and_stable_normalized_id(registered):
    ingest(registered, "home", "personal", FakeConnector())
    original = rows(registered, source_record)[0]
    result = ingest(registered, "home", "personal", FakeConnector([RawRecord("message-1", {"subject": "Changed"})]))
    current = rows(registered, source_record)[0]
    assert result.updated == 1
    assert current["id"] == original["id"]
    assert current["ingested_at"] == original["ingested_at"]
    assert current["raw_record_id"] != original["raw_record_id"]
    assert len(rows(registered, raw_source_record)) == 2

def test_normalization_failure_rolls_back_entire_page_and_cursor(registered):
    class Broken(FakeConnector):
        def normalize(self, raw):
            if raw.provider_object_id == "bad":
                raise RuntimeError("private body or token")
            return super().normalize(raw)
    with pytest.raises(IngestionError, match="check connector"):
        ingest(registered, "home", "personal", Broken([RawRecord("good", {}), RawRecord("bad", {})]))
    assert not rows(registered, source_record)
    assert not rows(registered, raw_source_record)
    assert rows(registered, source_sync_state)[0]["cursor"] is None
    assert ingest(registered, "home", "personal", FakeConnector()).inserted == 1

def test_database_failure_rolls_back_records_and_cursor(registered):
    class Invalid(FakeConnector):
        def normalize(self, raw):
            return replace(super().normalize(raw), subject={"not": "a string"})
    with pytest.raises(IngestionError):
        ingest(registered, "home", "personal", Invalid())
    assert not rows(registered, raw_source_record)
    assert not rows(registered, source_record)
    assert rows(registered, source_sync_state)[0]["version"] == 0

@pytest.mark.parametrize("payload", [{"access_token": "secret"}, {"nested": {"body": "private"}}, {"number": float("nan")}])
def test_default_metadata_policy_rejects_secrets_and_full_bodies(registered, payload):
    with pytest.raises(IngestionError):
        ingest(registered, "home", "personal", FakeConnector([RawRecord("msg", payload)]))
    assert not rows(registered, raw_source_record)

def test_disabled_wrong_household_and_wrong_provider_accounts_are_not_fetched(registered):
    connector = FakeConnector()
    with pytest.raises(IngestionError):
        ingest(registered, "other", "personal", connector)
    connector.provider = "gmail"
    with pytest.raises(IngestionError):
        ingest(registered, "home", "personal", connector)
    connector.provider = "fixture"
    with registered.begin() as connection:
        connection.execute(update(source_account).where(source_account.c.id == "personal").values(enabled=False))
    with pytest.raises(IngestionError):
        ingest(registered, "home", "personal", connector)
    assert connector.cursors == []

def test_stale_sync_cannot_overwrite_new_cursor(registered):
    class Racing(FakeConnector):
        def fetch_changes(self, account, cursor):
            with registered.begin() as connection:
                connection.execute(update(source_sync_state).where(source_sync_state.c.source_account_id == account.id)
                    .values(version=1, cursor="newer"))
            return super().fetch_changes(account, cursor)
    with pytest.raises(ConcurrentSyncError):
        ingest(registered, "home", "personal", Racing())
    assert not rows(registered, source_record)
    assert rows(registered, source_sync_state)[0]["cursor"] == "newer"

def test_error_logs_do_not_include_provider_exception(registered, caplog):
    class Broken(FakeConnector):
        def fetch_changes(self, account, cursor):
            raise RuntimeError("secret-token-123")
    with pytest.raises(IngestionError) as failure:
        ingest(registered, "home", "personal", Broken())
    assert "secret-token-123" not in caplog.text
    assert "secret-token-123" not in str(failure.value)

def test_naive_timestamps_and_changed_identity_are_rejected(registered):
    class Naive(FakeConnector):
        def normalize(self, raw):
            return replace(super().normalize(raw), occurred_at=datetime(2026, 10, 4))
    class WrongIdentity(FakeConnector):
        def normalize(self, raw):
            return replace(super().normalize(raw), provider_object_id="wrong")
    for connector in (Naive(), WrongIdentity()):
        with pytest.raises(IngestionError):
            ingest(registered, "home", "personal", connector)
    assert not rows(registered, source_record)


@pytest.mark.parametrize("boundary", ["raw", "normalized"])
@pytest.mark.parametrize("nested", [False, True])
@pytest.mark.parametrize("key", ["snippet", "SnIpPeT"])
def test_snippet_rejected_without_changing_records_or_cursor(registered, caplog, boundary, nested, key):
    private = "synthetic-private-snippet-NEVER-PERSIST"
    metadata = {key: private}
    if nested:
        metadata = {"nested": [metadata]}

    class SnippetConnector(FakeConnector):
        def normalize(self, raw):
            normalized = super().normalize(raw)
            if boundary == "normalized" and raw.provider_object_id == "bad":
                return replace(normalized, metadata=metadata)
            return normalized

    ingest(registered, "home", "personal", FakeConnector())
    tables = (raw_source_record, source_record, source_sync_state)
    before = {table.name: rows(registered, table) for table in tables}
    records = [RawRecord("good", {"subject": "Synthetic"}),
               RawRecord("bad", metadata if boundary == "raw" else {})]
    with pytest.raises(IngestionError) as failure:
        ingest(registered, "home", "personal", SnippetConnector(records))
    assert {table.name: rows(registered, table) for table in tables} == before
    assert private not in str(failure.value) + caplog.text
