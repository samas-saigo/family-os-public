"""Synthetic Gmail responses only; behavioral suite runs on SQLite and PostgreSQL."""
from copy import deepcopy
from dataclasses import replace
import json
import logging
from gmail_clock import FakeClock

import pytest
from sqlalchemy import select, update

from family_os.domain import SourceAccount
from family_os.errors import GmailAPIError, MailboxIdentityError, ResyncRequiredError
from family_os.gmail import DEFAULT_QUERY, GmailConnector, GmailHTTPClient
from family_os.ingestion import ingest, IngestionError
from family_os.registry import get_account, list_accounts, register
from family_os.schema import raw_source_record, source_account, source_record, source_sync_state

PRIVATE = "synthetic-private-body-token-NEVER-PERSIST"


def message(message_id="m1", labels=None):
    return {"id": message_id, "threadId": "t1", "internalDate": "1791115200000",
        "historyId": "110", "labelIds": labels if labels is not None else ["INBOX", "UNREAD"],
        "sizeEstimate": 1234, "snippet": PRIVATE, "unexpected": {"access_token": PRIVATE},
        "payload": {"mimeType": "multipart/mixed", "headers": [
            {"name": "From", "value": "Sender <sender@example.invalid>"},
            {"name": "To", "value": "Demo <demo@gmail.com>, Second <second@example.invalid>"},
            {"name": "Cc", "value": "second@example.invalid, spouse@example.invalid"},
            {"name": "Subject", "value": "Synthetic subject"},
            {"name": "Message-ID", "value": "<synthetic@example.invalid>"},
            {"name": "Authorization", "value": PRIVATE},
            {"name": "X-Private", "value": PRIVATE}], "body": {"data": PRIVATE},
            "parts": [{"mimeType": "text/plain", "body": {"data": PRIVATE, "size": 25}},
                {"mimeType": "multipart/alternative", "parts": [
                    {"mimeType": "text/html", "body": {"data": PRIVATE}}]},
                {"mimeType": "application/pdf", "filename": "synthetic.pdf",
                 "body": {"data": PRIVATE, "size": 256, "attachmentId": "attachment-1"}}]}}


class FakeGmail:
    def __init__(self):
        self.email = "demo@gmail.com"
        self.tip = "100"
        self.messages = {"m1": message(), "m2": message("m2")}
        self.initial = {None: {"messages": [{"id": "m1"}]}}
        self.histories = {("100", None): {"historyId": "120"},
                          ("120", None): {"historyId": "120"}}
        self.calls = []

    @staticmethod
    def response(value):
        if isinstance(value, Exception):
            raise value
        return deepcopy(value)

    def profile(self):
        self.calls.append(("profile",))
        return {"emailAddress": self.email, "historyId": self.tip}

    def list_messages(self, query, page_token, page_size):
        self.calls.append(("list", query, page_token, page_size))
        return self.response(self.initial[page_token])

    def message(self, message_id):
        self.calls.append(("message", message_id))
        return self.response(self.messages[message_id])

    def history(self, history_id, page_token, page_size):
        self.calls.append(("history", history_id, page_token, page_size))
        return self.response(self.histories[(history_id, page_token)])


@pytest.fixture
def gmail_config():
    return {"household": {"id": "home", "name": "Synthetic"},
        "people": [{"id": "alex", "display_name": "Alex"}, {"id": "spouse", "display_name": "Spouse"}],
        "source_accounts": [
            {"id": "gmail1", "provider": "gmail", "owner_type": "person", "owner_id": "alex", "external_account": "demo@gmail.com"},
            {"id": "gmail2", "provider": "gmail", "owner_type": "person", "owner_id": "alex", "external_account": "secondary@gmail.com"},
            {"id": "spouse-mail", "provider": "gmail", "owner_type": "person", "owner_id": "spouse", "external_account": "spouse@gmail.com"},
            {"id": "shared", "provider": "gmail", "owner_type": "household", "owner_id": "home", "external_account": "shared@gmail.com"},
            {"id": "unknown", "provider": "gmail", "owner_type": "unknown", "external_account": "unknown@example.invalid"}]}


@pytest.fixture
def registered_gmail(engine, gmail_config):
    register(engine, gmail_config)
    return engine


def rows(engine, table):
    with engine.connect() as connection:
        return connection.execute(select(table)).mappings().all()


def state(engine):
    return next(row for row in rows(engine, source_sync_state) if row["source_account_id"] == "gmail1")


def account(engine):
    with engine.connect() as connection:
        return get_account(connection, "home", "gmail1")


def test_multiple_person_spouse_shared_and_unknown_gmail_accounts(registered_gmail):
    accounts = list_accounts(registered_gmail, "home")
    assert [a.owner_id for a in accounts if a.id in {"gmail1", "gmail2"}] == ["alex", "alex"]
    assert next(a for a in accounts if a.id == "spouse-mail").owner_id == "spouse"
    assert next(a for a in accounts if a.id == "shared").owner_type == "household"
    for target in accounts:
        client = FakeGmail()
        client.email = target.external_account
        assert ingest(registered_gmail, "home", target.id, GmailConnector(client)).inserted == 1
    assert len(rows(registered_gmail, source_record)) == 5


@pytest.mark.parametrize("address", [" DEMO@GMAIL.COM ", "d.e.m.o+alias@googlemail.com"])
def test_duplicate_mailbox_rejected_transactionally(engine, gmail_config, address):
    gmail_config["source_accounts"][1]["external_account"] = address
    with pytest.raises(ValueError, match="Duplicate active"):
        register(engine, gmail_config)
    assert not rows(engine, source_account)


def test_duplicate_guard_covers_previous_registrations_and_disable_retains_history(registered_gmail, gmail_config):
    ingest(registered_gmail, "home", "gmail1", GmailConnector(FakeGmail()))
    replacement = deepcopy(gmail_config)
    replacement["source_accounts"] = [dict(gmail_config["source_accounts"][0], id="replacement")]
    with pytest.raises(ValueError, match="Duplicate active"):
        register(registered_gmail, replacement)
    replacement["source_accounts"].append(dict(gmail_config["source_accounts"][0], enabled=False))
    register(registered_gmail, replacement)
    assert len(rows(registered_gmail, source_record)) == 1
    assert state(registered_gmail)["cursor"] is not None
    with pytest.raises(IngestionError):
        ingest(registered_gmail, "home", "gmail1", GmailConnector(FakeGmail()))


def test_gmail_registry_requires_explicit_identity(engine, gmail_config):
    del gmail_config["source_accounts"][0]["external_account"]
    with pytest.raises(ValueError, match="explicitly registered"):
        register(engine, gmail_config)


def test_duplicate_guard_blocks_sync_after_direct_database_write(registered_gmail):
    with registered_gmail.begin() as connection:
        connection.execute(update(source_account).where(source_account.c.id == "gmail2").values(external_account="demo@gmail.com"))
    client = FakeGmail()
    with pytest.raises(IngestionError):
        ingest(registered_gmail, "home", "gmail1", GmailConnector(client))
    assert client.calls == []


def test_profile_mismatch_and_empty_identity_never_fetch_messages(registered_gmail):
    client = FakeGmail()
    client.email = "other@gmail.com"
    connector = GmailConnector(client)
    before = state(registered_gmail)
    with pytest.raises(MailboxIdentityError):
        ingest(registered_gmail, "home", "gmail1", connector)
    assert state(registered_gmail) == before
    assert client.calls == [("profile",)]
    with pytest.raises(MailboxIdentityError):
        connector.fetch_changes(replace(account(registered_gmail), external_account=None), None)


def test_profile_identity_checked_on_each_resumed_page(registered_gmail):
    client = FakeGmail()
    ingest(registered_gmail, "home", "gmail1", GmailConnector(client))
    before = state(registered_gmail)
    client.email = "secondary@gmail.com"
    with pytest.raises(MailboxIdentityError):
        ingest(registered_gmail, "home", "gmail1", GmailConnector(client))
    assert state(registered_gmail) == before


def test_initial_pagination_restart_and_baseline_transition(registered_gmail):
    client = FakeGmail()
    client.initial[None]["nextPageToken"] = "list-p2"
    client.initial["list-p2"] = {"messages": [{"id": "m2"}]}
    with pytest.raises(IngestionError, match="Page limit"):
        ingest(registered_gmail, "home", "gmail1", GmailConnector(client, page_size=1), max_pages=1)
    cursor = json.loads(state(registered_gmail)["cursor"])
    assert (cursor["phase"], cursor["page_token"], cursor["history_id"]) == ("initial", "list-p2", "100")
    client.tip = "999"  # Do not skip history during a restarted initial scan.
    result = ingest(registered_gmail, "home", "gmail1", GmailConnector(client, page_size=1))
    assert (result.pages, result.inserted) == (2, 1)
    cursor = json.loads(state(registered_gmail)["cursor"])
    assert (cursor["phase"], cursor["history_id"], cursor["page_token"]) == ("history", "120", None)
    assert ("history", "100", None, 1) in client.calls
    assert len(rows(registered_gmail, source_record)) == 2


def test_initial_replay_idempotent_and_content_is_never_persisted(registered_gmail, caplog):
    client = FakeGmail()
    connector = GmailConnector(client)
    assert ingest(registered_gmail, "home", "gmail1", connector).inserted == 1
    original = rows(registered_gmail, source_record)[0]
    assert ingest(registered_gmail, "home", "gmail1", connector).inserted == 0
    # Explicit synthetic controlled replay, retaining all historical records.
    with registered_gmail.begin() as connection:
        connection.execute(update(source_sync_state).where(source_sync_state.c.source_account_id == "gmail1")
                           .values(cursor=None, version=state(registered_gmail)["version"] + 1))
    assert ingest(registered_gmail, "home", "gmail1", connector).unchanged == 1
    assert rows(registered_gmail, source_record)[0] == original
    assert len(rows(registered_gmail, raw_source_record)) == 1
    persisted = json.dumps([dict(r) for r in rows(registered_gmail, raw_source_record) + rows(registered_gmail, source_record)], default=str)
    assert PRIVATE not in persisted + caplog.text
    assert "snippet" not in persisted and '"data"' not in persisted and '"body"' not in persisted
    assert original["content_hash"] is None  # Subject/snippet never substitute for a body.
    assert original["recipients"] == ["demo@gmail.com", "second@example.invalid", "spouse@example.invalid"]
    assert original["raw_metadata"]["attachments"] == [{"filename": "synthetic.pdf", "mime_type": "application/pdf",
        "size": 256, "attachment_id": "attachment-1"}]
    batch = connector.fetch_changes(account(registered_gmail), None)
    assert PRIVATE not in repr(batch) + repr(connector.normalize(batch.records[0]))


def test_incremental_new_and_repeated_history_and_label_changes(registered_gmail):
    client = FakeGmail()
    ingest(registered_gmail, "home", "gmail1", GmailConnector(client))
    original = rows(registered_gmail, source_record)[0]
    client.messages["m1"]["labelIds"] = ["INBOX"]
    client.messages["m1"]["historyId"] = "125"
    client.histories[("120", None)] = {"historyId": "130", "history": [
        {"messages": [{"id": "m2"}], "messagesAdded": [{"message": {"id": "m2"}}]},
        {"labelsRemoved": [{"message": {"id": "m1"}, "labelIds": ["UNREAD"]}]},
        {"labelsAdded": [{"message": {"id": "m1"}, "labelIds": ["INBOX"]}]}]}
    client.histories[("130", None)] = {"historyId": "130", "history": [
        {"messagesAdded": [{"message": {"id": "m2"}}, {"message": {"id": "m2"}}]}]}
    result = ingest(registered_gmail, "home", "gmail1", GmailConnector(client))
    assert (result.inserted, result.updated) == (1, 1)
    changed = next(row for row in rows(registered_gmail, source_record) if row["provider_object_id"] == "m1")
    assert changed["id"] == original["id"]
    assert changed["raw_record_id"] != original["raw_record_id"]
    assert changed["raw_metadata"]["label_ids"] == ["INBOX"]
    assert len(rows(registered_gmail, raw_source_record)) == 3
    assert ingest(registered_gmail, "home", "gmail1", GmailConnector(client)).unchanged == 1
    assert len(rows(registered_gmail, source_record)) == 2


def test_history_pagination_resume_keeps_start_and_commits_tip_only_at_end(registered_gmail):
    client = FakeGmail()
    ingest(registered_gmail, "home", "gmail1", GmailConnector(client))
    client.histories[("120", None)] = {"historyId": "200", "nextPageToken": "history-p2",
        "history": [{"messagesAdded": [{"message": {"id": "m2"}}]}]}
    client.histories[("120", "history-p2")] = {"historyId": "210", "history": [
        {"messagesAdded": [{"message": {"id": "m2"}}]}]}
    with pytest.raises(IngestionError, match="Page limit"):
        ingest(registered_gmail, "home", "gmail1", GmailConnector(client), max_pages=1)
    cursor = json.loads(state(registered_gmail)["cursor"])
    assert cursor["history_id"] == "120" and cursor["page_token"] == "history-p2"
    assert ingest(registered_gmail, "home", "gmail1", GmailConnector(client)).unchanged == 1
    assert json.loads(state(registered_gmail)["cursor"])["history_id"] == "210"
    assert len(rows(registered_gmail, source_record)) == 2


@pytest.mark.parametrize("status, paginated", [(400, False), (400, True), (404, False)])
def test_invalid_history_requires_resync_without_mutation(registered_gmail, status, paginated):
    client = FakeGmail()
    ingest(registered_gmail, "home", "gmail1", GmailConnector(client))
    before = state(registered_gmail)
    if paginated:
        cursor = json.loads(before["cursor"])
        cursor["page_token"] = "expired-page"
        with registered_gmail.begin() as connection:
            connection.execute(update(source_sync_state).where(source_sync_state.c.source_account_id == "gmail1")
                               .values(cursor=json.dumps(cursor)))
        before = state(registered_gmail)
        client.histories[("120", "expired-page")] = GmailAPIError(status)
    else:
        client.histories[("120", None)] = GmailAPIError(status)
    with pytest.raises(ResyncRequiredError, match="resync required"):
        ingest(registered_gmail, "home", "gmail1", GmailConnector(client))
    assert state(registered_gmail) == before
    assert len(rows(registered_gmail, source_record)) == 1


@pytest.mark.parametrize("failure", [GmailAPIError(429), GmailAPIError(503), RuntimeError(PRIVATE)])
def test_failed_message_fetch_is_atomic_and_errors_are_safe(registered_gmail, caplog, failure):
    client = FakeGmail()
    client.initial[None] = {"messages": [{"id": "m1"}, {"id": "m2"}]}
    client.messages["m2"] = failure
    before = state(registered_gmail)
    with pytest.raises(IngestionError) as error:
        ingest(registered_gmail, "home", "gmail1", GmailConnector(client))
    assert PRIVATE not in caplog.text + str(error.value)
    assert state(registered_gmail) == before
    assert not rows(registered_gmail, source_record)
    assert not rows(registered_gmail, raw_source_record)


def test_failed_later_page_preserves_previous_page_and_restarts(registered_gmail):
    client = FakeGmail()
    client.initial[None]["nextPageToken"] = "p2"
    client.initial["p2"] = GmailAPIError(429)
    with pytest.raises(GmailAPIError):
        ingest(registered_gmail, "home", "gmail1", GmailConnector(client))
    assert len(rows(registered_gmail, source_record)) == 1
    assert json.loads(state(registered_gmail)["cursor"])["page_token"] == "p2"
    client.initial["p2"] = {"messages": [{"id": "m2"}]}
    assert ingest(registered_gmail, "home", "gmail1", GmailConnector(client)).inserted == 1


def test_deleted_message_preserves_existing_provenance_and_trash_retains_labels(registered_gmail):
    client = FakeGmail()
    ingest(registered_gmail, "home", "gmail1", GmailConnector(client))
    client.messages["m1"]["labelIds"] = ["TRASH"]
    client.histories[("120", None)] = {"historyId": "130", "history": [
        {"labelsAdded": [{"message": {"id": "m1"}, "labelIds": ["TRASH"]}]}]}
    assert ingest(registered_gmail, "home", "gmail1", GmailConnector(client)).updated == 1
    previous = rows(registered_gmail, source_record)
    client.messages["m1"] = GmailAPIError(404)
    client.histories[("130", None)] = {"historyId": "140", "history": [
        {"messages": [{"id": "m1"}], "messagesDeleted": [{"message": {"id": "m1"}}]}]}
    assert ingest(registered_gmail, "home", "gmail1", GmailConnector(client)).updated == 0
    assert rows(registered_gmail, source_record) == previous
    assert len(rows(registered_gmail, raw_source_record)) == 2


@pytest.mark.parametrize("mutation", [lambda c: c.update(v=99), lambda c: c.update(account="gmail2"),
    lambda c: c.update(mailbox="other@gmail.com"), lambda c: c.update(household="other"),
    lambda c: c.update(history_id="bad"), lambda c: c.update(phase="unknown")])
def test_cursor_cannot_be_reused_across_mailbox_account_household_or_version(registered_gmail, mutation):
    connector = GmailConnector(FakeGmail())
    batch = connector.fetch_changes(account(registered_gmail), None)
    cursor = json.loads(batch.next_cursor)
    mutation(cursor)
    with pytest.raises(ResyncRequiredError):
        connector.fetch_changes(account(registered_gmail), json.dumps(cursor))


def test_query_change_requires_explicit_resync(registered_gmail):
    client = FakeGmail()
    ingest(registered_gmail, "home", "gmail1", GmailConnector(client))
    before = state(registered_gmail)
    with pytest.raises(ResyncRequiredError):
        ingest(registered_gmail, "home", "gmail1", GmailConnector(client, query="newer_than:1d"))
    assert state(registered_gmail) == before


@pytest.mark.parametrize("response", [{"historyId": "bad"}, {"historyId": "99"},
    {"historyId": "120", "nextPageToken": ""}])
def test_malformed_history_does_not_advance_cursor(registered_gmail, response):
    client = FakeGmail()
    ingest(registered_gmail, "home", "gmail1", GmailConnector(client))
    before = state(registered_gmail)
    client.histories[("120", None)] = response
    with pytest.raises(IngestionError):
        ingest(registered_gmail, "home", "gmail1", GmailConnector(client))
    assert state(registered_gmail) == before


def test_http_boundary_uses_only_read_endpoints_and_suppresses_wire_logs(caplog):
    calls = []
    class Session:
        def get(self, url, **kwargs):
            logging.getLogger("oauthlib.fake").warning(PRIVATE)
            calls.append((url, kwargs))
            class Response:
                status_code = 200
                def json(self):
                    return {}
            return Response()
    caplog.set_level(logging.DEBUG)
    clock = FakeClock()
    client = GmailHTTPClient(Session(), clock=clock.clock, sleep=clock.sleep)
    client.profile()
    client.list_messages(DEFAULT_QUERY, "p2", 3)
    client.message("m/1")
    client.history("100", "p3", 5)
    assert [url.rsplit("/", 1)[-1] for url, _ in calls] == ["profile", "messages", "m%2F1", "history"]
    assert calls[1][1]["params"]["q"] == DEFAULT_QUERY
    assert calls[3][1]["params"]["startHistoryId"] == "100"
    assert calls[3][1]["params"]["fields"] == (
        "history(messages(id),messagesAdded(message(id)),"
        "labelsAdded(message(id)),labelsRemoved(message(id))),historyId,nextPageToken")
    fields = calls[2][1]["params"]["fields"]
    assert "data" not in fields and "snippet" not in fields
    assert fields.count("body(size,attachmentId)") == 17
    assert all(kwargs["timeout"] == 30 for _, kwargs in calls)
    assert PRIVATE not in caplog.text
    logging.warning("Diagnostics restored")
    assert "Diagnostics restored" in caplog.text


@pytest.mark.parametrize("status", [401, 403, 429, 500])
def test_http_failure_never_exposes_response(status):
    class Session:
        def get(self, *args, **kwargs):
            class Response:
                status_code = status
                def json(self):
                    raise AssertionError(PRIVATE)
            return Response()
    with pytest.raises(GmailAPIError) as error:
        clock = FakeClock()
        GmailHTTPClient(Session(), sleep=clock.sleep, clock=clock.clock, jitter=lambda: 0).profile()
    assert error.value.status == status
    assert PRIVATE not in str(error.value)


def test_metadata_change_updates_record_and_keeps_prior_raw_snapshot(registered_gmail):
    client = FakeGmail()
    ingest(registered_gmail, "home", "gmail1", GmailConnector(client))
    original = rows(registered_gmail, source_record)[0]
    client.messages["m1"]["payload"]["headers"][3]["value"] = "Updated synthetic subject"
    client.messages["m1"]["payload"]["parts"][2]["filename"] = "updated.pdf"
    client.histories[("120", None)] = {"historyId": "130", "history": [
        {"messages": [{"id": "m1"}]}]}
    assert ingest(registered_gmail, "home", "gmail1", GmailConnector(client)).updated == 1
    changed = rows(registered_gmail, source_record)[0]
    assert changed["id"] == original["id"]
    assert changed["subject"] == "Updated synthetic subject"
    assert changed["raw_metadata"]["attachments"][0]["filename"] == "updated.pdf"
    assert len(rows(registered_gmail, raw_source_record)) == 2


def test_mime_projection_retains_nested_metadata_without_fetching_content(registered_gmail):
    # Model Gmail partial-response semantics with synthetic data, including the
    # depth sentinel. Parsing also catches unbalanced/nested projection mistakes.
    from family_os.gmail import _message_fields, MIME_METADATA_DEPTH

    def parse(fields):
        position = 0
        def group():
            nonlocal position
            result = {}
            while position < len(fields) and fields[position] != ")":
                start = position
                while position < len(fields) and fields[position] not in ",()":
                    position += 1
                name = fields[start:position]
                assert name
                children = None
                if position < len(fields) and fields[position] == "(":
                    position += 1
                    children = group()
                    assert fields[position] == ")"
                    position += 1
                result[name] = children
                if position < len(fields) and fields[position] == ",":
                    position += 1
                else:
                    break
            return result
        result = group()
        assert position == len(fields)
        return result

    def project(value, selection):
        if isinstance(value, list):
            return [project(item, selection) for item in value]
        return {key: project(value[key], children) if children is not None else value[key]
                for key, children in selection.items() if key in value}

    selection = parse(_message_fields())
    synthetic = message()
    attachment = synthetic["payload"]["parts"][2]
    nested = attachment
    for _ in range(MIME_METADATA_DEPTH):
        nested = {"mimeType": "multipart/mixed", "parts": [nested], "body": {"data": PRIVATE}}
    synthetic["payload"] = nested
    projected = project(synthetic, selection)
    assert PRIVATE not in json.dumps(projected)
    client = FakeGmail()
    client.messages["m1"] = projected
    assert ingest(registered_gmail, "home", "gmail1", GmailConnector(client)).inserted == 1
    assert rows(registered_gmail, source_record)[0]["raw_metadata"]["attachments"][0]["attachment_id"] == "attachment-1"

    # Beyond the projection's supported depth, the sentinel reveals truncation.
    # Fail atomically rather than silently dropping attachment provenance.
    synthetic["payload"] = {"mimeType": "multipart/mixed", "parts": [nested]}
    client.messages["m1"] = project(synthetic, selection)
    client.histories[("120", None)] = {"historyId": "130", "history": [{"messages": [{"id": "m1"}]}]}
    before = state(registered_gmail)
    with pytest.raises(IngestionError):
        ingest(registered_gmail, "home", "gmail1", GmailConnector(client))
    assert state(registered_gmail) == before
    assert len(rows(registered_gmail, raw_source_record)) == 1
