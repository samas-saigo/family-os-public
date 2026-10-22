"""Synthetic Graph metadata and injected clients only; both database backends."""
from copy import deepcopy
from dataclasses import replace
import json
import logging

import pytest
from sqlalchemy import select

from family_os.domain import ChangeBatch, NormalizedRecord, RawRecord
from family_os.ingestion import ingest, IngestionError
from family_os.outlook import (OutlookConnector, FolderPolicy, GraphHTTPClient, GRAPH_BASE,
    DEFAULT_EXCLUDED, MESSAGE_FIELDS, IMMUTABLE_PREFER, folder_url, validate_link)
from family_os.outlook_errors import (OutlookAPIError, OutlookAuthError, OutlookPolicyError,
                                      OutlookIdentityError, OutlookResyncRequiredError)
from family_os.registry import register, get_account, list_accounts
from family_os.schema import source_record, raw_source_record, source_sync_state

PRIVATE = "synthetic-private-Graph-body-token"


def link(fid="in", token="done", kind="delta"):
    return folder_url(fid) + "/messages/delta?$" + ("deltatoken" if kind == "delta" else "skiptoken") + "=" + token


def message(mid="m1", folder="in", subject="Synthetic subject"):
    address = lambda value: {"emailAddress": {"name": "Synthetic", "address": value, "private": PRIVATE}}
    return {"id": mid, "internetMessageId": "<synthetic@example.invalid>", "conversationId": "conversation",
        "parentFolderId": folder, "receivedDateTime": "2026-10-04T12:00:00Z",
        "sentDateTime": "2026-10-04T11:59:00Z", "createdDateTime": "2026-10-04T12:00:00Z",
        "lastModifiedDateTime": "2026-10-04T12:00:00Z", "subject": subject,
        "from": address("sender@example.invalid"), "sender": address("sender@example.invalid"),
        "toRecipients": [address("alex@outlook.com")], "ccRecipients": [address("spouse@example.invalid")],
        "bccRecipients": [address("alex@outlook.com")], "categories": ["Synthetic", "Synthetic"],
        "importance": "normal", "isRead": False, "hasAttachments": True,
        "body": {"content": PRIVATE}, "bodyPreview": PRIVATE, "uniqueBody": PRIVATE,
        "attachments": [{"contentBytes": PRIVATE}], "internetMessageHeaders": [{"value": PRIVATE}],
        "singleValueExtendedProperties": [{"value": PRIVATE}], "@odata.etag": PRIVATE}


class FakeGraph:
    def __init__(self):
        self.username = "alex@outlook.com"
        self.binding = "synthetic-binding-fingerprint"
        self.folders = [{"id": "in", "name": "Boîte de réception", "parent": None, "hidden": False}]
        self.known = {"inbox": "in"}
        self.pages = {("in", None): {"value": [{"id": "m1"}], "@odata.deltaLink": link()},
                      ("in", link()): {"value": [], "@odata.deltaLink": link()}}
        self.messages = {"m1": message()}
        self.calls = []

    def identity(self):
        self.calls.append(("identity",))
        return self.username, self.binding

    def discover_folders(self):
        self.calls.append(("folders",))
        return deepcopy(self.folders), deepcopy(self.known)

    def delta(self, fid, url, size):
        self.calls.append(("delta", fid, url, size))
        value = self.pages[(fid, url)]
        if isinstance(value, Exception):
            raise value
        return deepcopy(value)

    def message(self, mid):
        self.calls.append(("message", mid))
        value = self.messages[mid]
        if isinstance(value, Exception):
            raise value
        return deepcopy(value)


@pytest.fixture
def outlook_config():
    return {"household": {"id": "home", "name": "Synthetic"},
        "people": [{"id": "alex", "display_name": "Alex"}, {"id": "spouse", "display_name": "Spouse"}],
        "source_accounts": [
            {"id": "out1", "provider": "outlook", "owner_type": "person", "owner_id": "alex", "external_account": "alex@outlook.com"},
            {"id": "out2", "provider": "outlook", "owner_type": "person", "owner_id": "alex", "external_account": "alex@work.example.invalid"},
            {"id": "out-spouse", "provider": "outlook", "owner_type": "person", "owner_id": "spouse", "external_account": "spouse@hotmail.com"},
            {"id": "gmail", "provider": "gmail", "owner_type": "person", "owner_id": "alex", "external_account": "alex@gmail.com"}]}


@pytest.fixture
def registered_outlook(engine, outlook_config):
    register(engine, outlook_config)
    return engine


def rows(engine, table):
    with engine.connect() as connection:
        return connection.execute(select(table).order_by(*table.primary_key.columns)).mappings().all()


def state(engine):
    return next(row for row in rows(engine, source_sync_state) if row["source_account_id"] == "out1")


def account(engine):
    with engine.connect() as connection:
        return get_account(connection, "home", "out1")


def test_contract_multi_person_multi_provider_and_account_identities(registered_outlook):
    accounts = list_accounts(registered_outlook, "home")
    assert sum(item.owner_id == "alex" for item in accounts) == 3
    assert next(item for item in accounts if item.id == "out-spouse").owner_id == "spouse"
    for target in accounts:
        if target.provider == "outlook":
            client = FakeGraph()
            client.username = target.external_account
            batch = OutlookConnector(client).fetch_changes(target, None)
            assert isinstance(batch, ChangeBatch) and isinstance(batch.records[0], RawRecord)
            assert isinstance(OutlookConnector(client).normalize(batch.records[0]), NormalizedRecord)
            assert ingest(registered_outlook, "home", target.id, OutlookConnector(client)).inserted == 1
    assert len(rows(registered_outlook, source_record)) == 3


@pytest.mark.parametrize("identity", [None, "", "invalid"])
def test_registry_requires_outlook_identity(engine, outlook_config, identity):
    outlook_config["source_accounts"][0]["external_account"] = identity
    with pytest.raises(OutlookIdentityError):
        register(engine, outlook_config)


def test_identity_guard_never_fetches_wrong_mailbox(registered_outlook):
    client = FakeGraph()
    client.username = "other@outlook.com"
    with pytest.raises(OutlookIdentityError):
        ingest(registered_outlook, "home", "out1", OutlookConnector(client))
    assert client.calls == [("identity",)]
    assert state(registered_outlook)["cursor"] is None


def test_folder_policy_localized_names_custom_subtrees_and_explicit_overrides():
    client = FakeGraph()
    for name in DEFAULT_EXCLUDED:
        client.known[name] = "id-" + name
        client.folders.append({"id": "id-" + name, "name": "Localized " + name, "parent": None})
    client.folders += [{"id": "custom", "name": "Projets", "parent": "in"},
                       {"id": "child-junk", "name": "Custom", "parent": "id-junkemail"},
                       {"id": "hidden", "name": "System", "hidden": True}]
    assert set(FolderPolicy().select(client.folders, client.known)) == {"in", "custom"}
    assert set(FolderPolicy(include=["sentitems"]).select(client.folders, client.known)) == {"id-sentitems"}
    assert set(FolderPolicy(include=["inbox", "custom"], exclude=["custom"]).select(client.folders, client.known)) == {"in"}


def test_initial_delta_nextlink_restart_and_completed_deltalink(registered_outlook):
    client = FakeGraph()
    page2 = link(kind="next", token="opaque-unchanged")
    client.pages[("in", None)]["@odata.nextLink"] = page2
    del client.pages[("in", None)]["@odata.deltaLink"]
    client.pages[("in", page2)] = {"value": [{"id": "m2"}], "@odata.deltaLink": link()}
    client.messages["m2"] = message("m2")
    with pytest.raises(IngestionError, match="Page limit"):
        ingest(registered_outlook, "home", "out1", OutlookConnector(client), max_pages=1)
    saved = json.loads(state(registered_outlook)["cursor"])
    assert saved["folders"]["in"]["link"] == page2
    assert saved["folders"]["in"]["kind"] == "next"
    assert ingest(registered_outlook, "home", "out1", OutlookConnector(client)).inserted == 1
    assert ("delta", "in", page2, 25) in client.calls
    assert ingest(registered_outlook, "home", "out1", OutlookConnector(client)).inserted == 0
    assert ("delta", "in", link(), 25) in client.calls
    assert len(rows(registered_outlook, source_record)) == 2


def test_new_removed_and_reappearing_folder_keeps_other_cursors_and_history(registered_outlook):
    client = FakeGraph()
    ingest(registered_outlook, "home", "out1", OutlookConnector(client))
    client.folders.append({"id": "custom", "name": "Archive perso", "parent": None})
    client.pages[("custom", None)] = {"value": [{"id": "m2"}], "@odata.deltaLink": link("custom")}
    client.messages["m2"] = message("m2", "custom")
    assert ingest(registered_outlook, "home", "out1", OutlookConnector(client)).inserted == 1
    assert json.loads(state(registered_outlook)["cursor"])["folders"]["in"]["link"] == link()
    client.folders = [client.folders[0]]
    ingest(registered_outlook, "home", "out1", OutlookConnector(client))
    saved = json.loads(state(registered_outlook)["cursor"])
    assert saved["folders"]["custom"]["active"] is False
    assert len(rows(registered_outlook, source_record)) == 2
    client.folders.append({"id": "custom", "name": "Returned", "parent": None})
    client.pages[("custom", link("custom"))] = {"value": [], "@odata.deltaLink": link("custom")}
    ingest(registered_outlook, "home", "out1", OutlookConnector(client))
    assert ("delta", "custom", link("custom"), 25) in client.calls


def test_moves_replays_metadata_changes_and_privacy(registered_outlook, caplog):
    client = FakeGraph()
    connector = OutlookConnector(client)
    ingest(registered_outlook, "home", "out1", connector)
    original = rows(registered_outlook, source_record)[0]
    assert original["content_hash"] is None
    assert original["recipients"] == ["alex@outlook.com", "spouse@example.invalid"]
    client.folders.append({"id": "custom", "name": "Dossiers", "parent": None})
    client.messages["m1"] = message(folder="custom", subject="Updated synthetic")
    client.pages[("custom", None)] = {"value": [{"id": "m1"}, {"id": "m1"}], "@odata.deltaLink": link("custom")}
    assert ingest(registered_outlook, "home", "out1", connector).updated == 1
    current = rows(registered_outlook, source_record)[0]
    assert current["id"] == original["id"]
    assert current["raw_metadata"]["parent_folder_id"] == "custom"
    assert current["subject"] == "Updated synthetic"
    assert len(rows(registered_outlook, raw_source_record)) == 2
    # A stale folder-stream appearance re-fetches current metadata, not old folder data.
    client.pages[("in", link())] = {"value": [message(folder="in")], "@odata.deltaLink": link()}
    client.pages[("custom", link("custom"))] = {"value": [{"id": "m1"}], "@odata.deltaLink": link("custom")}
    assert ingest(registered_outlook, "home", "out1", connector).unchanged == 2
    assert len(rows(registered_outlook, source_record)) == 1
    persisted = json.dumps([dict(row) for row in rows(registered_outlook, raw_source_record) + rows(registered_outlook, source_record)], default=str)
    assert PRIVATE not in persisted + caplog.text
    assert not any(key in persisted for key in ("bodyPreview", "uniqueBody", "contentBytes", "internetMessageHeaders"))
    assert '"attachments"' not in persisted


@pytest.mark.parametrize("status", [400, 404, 410])
def test_expired_delta_retains_cursor_and_records(registered_outlook, status):
    client = FakeGraph()
    ingest(registered_outlook, "home", "out1", OutlookConnector(client))
    before = state(registered_outlook)
    client.pages[("in", link())] = OutlookAPIError(status)
    with pytest.raises(OutlookResyncRequiredError) as failure:
        ingest(registered_outlook, "home", "out1", OutlookConnector(client))
    assert failure.value.folder_id == "in"
    assert state(registered_outlook) == before
    assert len(rows(registered_outlook, source_record)) == 1


@pytest.mark.parametrize("failure", [OutlookAPIError(429), OutlookAPIError(503), RuntimeError(PRIVATE)])
def test_failed_message_page_is_atomic_and_safe(registered_outlook, failure, caplog):
    client = FakeGraph()
    client.pages[("in", None)]["value"].append({"id": "m2"})
    client.messages["m2"] = failure
    before = state(registered_outlook)
    with pytest.raises(IngestionError) as error:
        ingest(registered_outlook, "home", "out1", OutlookConnector(client))
    assert state(registered_outlook) == before
    assert not rows(registered_outlook, source_record)
    assert not rows(registered_outlook, raw_source_record)
    assert PRIVATE not in str(error.value) + caplog.text


def test_removed_markers_and_message_404_retain_provenance(registered_outlook):
    client = FakeGraph()
    ingest(registered_outlook, "home", "out1", OutlookConnector(client))
    before = rows(registered_outlook, source_record)
    client.pages[("in", link())] = {"value": [{"id": "m1", "@removed": {"reason": "deleted"}}], "@odata.deltaLink": link(token="removed")}
    assert ingest(registered_outlook, "home", "out1", OutlookConnector(client)).updated == 0
    client.pages[("in", link(token="removed"))] = {"value": [{"id": "m1"}], "@odata.deltaLink": link(token="removed")}
    client.messages["m1"] = OutlookAPIError(404)
    assert ingest(registered_outlook, "home", "out1", OutlookConnector(client)).updated == 0
    assert rows(registered_outlook, source_record) == before


@pytest.mark.parametrize("mutation", [lambda s: s.update(v=True), lambda s: s.update(extra="unknown"),
    lambda s: s["folders"]["in"].update(extra="unknown"), lambda s: s.update(v=9), lambda s: s.update(account="out2"),
    lambda s: s.update(household="other"), lambda s: s.update(mailbox="other@outlook.com"),
    lambda s: s.update(binding="other"), lambda s: s.update(policy="other"),
    lambda s: s.update(pending=["missing"]), lambda s: s["folders"]["in"].update(kind="bad"),
    lambda s: s["folders"]["in"].update(link="https://evil.invalid/token")])
def test_cursor_binding_and_corruption_fail_closed(registered_outlook, mutation):
    client = FakeGraph()
    batch = OutlookConnector(client).fetch_changes(account(registered_outlook), None)
    saved = json.loads(batch.next_cursor)
    mutation(saved)
    with pytest.raises(OutlookResyncRequiredError):
        OutlookConnector(client).fetch_changes(account(registered_outlook), json.dumps(saved))


def test_policy_and_secure_binding_changes_require_controlled_resync(registered_outlook):
    client = FakeGraph()
    ingest(registered_outlook, "home", "out1", OutlookConnector(client))
    before = state(registered_outlook)
    with pytest.raises(OutlookResyncRequiredError):
        ingest(registered_outlook, "home", "out1", OutlookConnector(client, FolderPolicy(include=["inbox"])))
    client.binding = "different-account-binding"
    with pytest.raises(OutlookResyncRequiredError):
        ingest(registered_outlook, "home", "out1", OutlookConnector(client))
    assert state(registered_outlook) == before


@pytest.mark.parametrize("url", ["http://graph.microsoft.com/v1.0/me/mailFolders/in/messages/delta?$skiptoken=x",
    "https://evil.invalid/v1.0/me/mailFolders/in/messages/delta?$skiptoken=x",
    "https://graph.microsoft.com@evil.invalid/v1.0/me/mailFolders/in/messages/delta",
    "https://graph.microsoft.com:443/v1.0/me/mailFolders/in/messages/delta",
    "https://graph.microsoft.com/v1.0/users/other/messages/delta",
    "https://graph.microsoft.com/v1.0/me/mailFolders/other/messages/delta?$skiptoken=x",
    "https://graph.microsoft.com/beta/me/mailFolders/in/messages/delta",
    link() + "#fragment", link() + "&$select=bodyPreview", link() + "&$expand=attachments",
    link() + "&$deltatoken=duplicate", folder_url("in") + "/messages/delta", link() + "&$skip=10000"])
def test_untrusted_links_are_rejected_before_http(url):
    class Session:
        def get(self, *args, **kwargs):
            raise AssertionError("Must not reach HTTP")
    with pytest.raises(OutlookResyncRequiredError):
        GraphHTTPClient(Session()).delta("in", url, 25)


@pytest.mark.parametrize("response", [{"value": []}, {"value": [], "@odata.nextLink": link(kind="next"), "@odata.deltaLink": link()},
    {"value": [], "@odata.deltaLink": "https://evil.invalid/x"}])
def test_bad_delta_response_does_not_advance(registered_outlook, response):
    client = FakeGraph()
    client.pages[("in", None)] = response
    before = state(registered_outlook)
    with pytest.raises(OutlookResyncRequiredError):
        ingest(registered_outlook, "home", "out1", OutlookConnector(client))
    assert state(registered_outlook) == before


def test_discovery_pages_children_and_http_projection_are_read_basic(caplog):
    calls = []
    pages = {GRAPH_BASE: {"value": [{"id": "in", "displayName": "Posteingang", "childFolderCount": 1}],
                                     "@odata.nextLink": GRAPH_BASE + "?$skiptoken=folders"},
             GRAPH_BASE + "?$skiptoken=folders": {"value": [{"id": "archive-id", "displayName": "Archiv"}]},
             folder_url("in") + "/childFolders": {"value": [{"id": "custom", "displayName": "Projekte"}]}}
    class Session:
        def get(self, url, **kwargs):
            logging.getLogger("requests.synthetic").warning(PRIVATE)
            calls.append((url, kwargs))
            if url in pages:
                data, status = pages[url], 200
            elif url == folder_url("inbox"):
                data, status = {"id": "in"}, 200
            elif url == folder_url("archive"):
                data, status = {"id": "archive-id"}, 200
            elif "/messages/delta" in url:
                data, status = {"value": [], "@odata.deltaLink": link()}, 200
            elif "/me/messages/" in url:
                data, status = message(), 200
            else:
                data, status = {"private": PRIVATE}, 404
            class Response:
                status_code = status
                def json(self):
                    return data
            return Response()
    client = GraphHTTPClient(Session())
    folders, known = client.discover_folders()
    assert {item["id"] for item in folders} == {"in", "archive-id", "custom"}
    assert next(item for item in folders if item["id"] == "custom")["parent"] == "in"
    assert known["inbox"] == "in"
    client.delta("in", None, 3)
    client.delta("in", link(), 3)
    client.message("m/1")
    for url, kwargs in calls:
        assert IMMUTABLE_PREFER in kwargs["headers"]["Prefer"]
        assert kwargs["allow_redirects"] is False and kwargs["timeout"] == 30
        selection = (kwargs["params"] or {}).get("$select", "")
        assert not any(key in selection for key in ("body", "bodyPreview", "uniqueBody", "attachments", "internetMessageHeaders"))
        assert "$value" not in url
    assert calls[-1][0].endswith("/messages/m%2F1")
    assert set(calls[-1][1]["params"]["$select"].split(",")) == set(MESSAGE_FIELDS)
    assert PRIVATE not in caplog.text


@pytest.mark.parametrize("status, error_type", [(401, OutlookAuthError), (403, OutlookPolicyError),
    (429, OutlookAPIError), (503, OutlookAPIError), (302, OutlookAPIError)])
def test_http_errors_never_expose_response_or_follow_redirect(status, error_type):
    class Session:
        def get(self, *args, **kwargs):
            class Response:
                status_code = status
                def json(self):
                    raise AssertionError(PRIVATE)
            return Response()
    with pytest.raises(error_type) as error:
        GraphHTTPClient(Session()).message("m1")
    assert PRIVATE not in str(error.value)


def test_default_excluded_streams_never_fetch_delta(registered_outlook):
    client = FakeGraph()
    for name in DEFAULT_EXCLUDED:
        client.known[name] = "id-" + name
        client.folders.append({"id": "id-" + name, "name": "Localized system folder", "parent": None})
    ingest(registered_outlook, "home", "out1", OutlookConnector(client))
    assert [call[1] for call in client.calls if call[0] == "delta"] == ["in"]


def test_failed_second_folder_retains_committed_first_and_retries(registered_outlook):
    client = FakeGraph()
    client.folders.append({"id": "zz-custom", "name": "Custom", "parent": None})
    client.pages[("zz-custom", None)] = OutlookAPIError(429)
    with pytest.raises(OutlookAPIError):
        ingest(registered_outlook, "home", "out1", OutlookConnector(client))
    saved = json.loads(state(registered_outlook)["cursor"])
    assert saved["folders"]["in"]["link"] == link()
    assert saved["folders"]["zz-custom"]["link"] is None
    assert saved["pending"] == ["zz-custom"]
    assert len(rows(registered_outlook, source_record)) == 1
    client.messages["m2"] = message("m2", "zz-custom")
    client.pages[("zz-custom", None)] = {"value": [{"id": "m2"}], "@odata.deltaLink": link("zz-custom")}
    assert ingest(registered_outlook, "home", "out1", OutlookConnector(client)).inserted == 1
    assert len(rows(registered_outlook, source_record)) == 2


@pytest.mark.parametrize("key", ["bodyPreview", "uniqueBody", "$value", "internetMessageHeaders",
                                  "singleValueExtendedProperties", "multiValueExtendedProperties", "contentBytes", "mime_content"])
@pytest.mark.parametrize("boundary", ["raw", "normalized"])
def test_common_privacy_guard_rejects_graph_private_fields(registered_outlook, key, boundary, caplog):
    from test_ingestion import FakeConnector
    # Exercise the provider-independent guard, beyond Graph's own allowlist.
    metadata = {"nested": [{key: PRIVATE}]}
    class PrivateConnector(FakeConnector):
        provider = "outlook"
        def normalize(self, record):
            return replace(super().normalize(record), metadata=metadata if boundary == "normalized" else {})
    before = state(registered_outlook)
    with pytest.raises(IngestionError) as failure:
        ingest(registered_outlook, "home", "out1", PrivateConnector([RawRecord("private", metadata if boundary == "raw" else {})]))
    assert state(registered_outlook) == before
    assert not rows(registered_outlook, source_record)
    assert PRIVATE not in str(failure.value) + caplog.text


def test_incomplete_stream_queue_corruption_fails_closed(registered_outlook):
    client = FakeGraph()
    client.pages[("in", None)] = {"value": [], "@odata.nextLink": link(kind="next")}
    batch = OutlookConnector(client).fetch_changes(account(registered_outlook), None)
    saved = json.loads(batch.next_cursor)
    saved["pending"] = []
    with pytest.raises(OutlookResyncRequiredError):
        OutlookConnector(client).fetch_changes(account(registered_outlook), json.dumps(saved))


def test_repeated_nextlink_is_controlled_failure(registered_outlook):
    client = FakeGraph()
    next_link = link(kind="next")
    client.pages[("in", None)] = {"value": [], "@odata.nextLink": next_link}
    client.pages[("in", next_link)] = {"value": [], "@odata.nextLink": next_link}
    with pytest.raises(OutlookResyncRequiredError):
        ingest(registered_outlook, "home", "out1", OutlookConnector(client))
    assert json.loads(state(registered_outlook)["cursor"])["folders"]["in"]["link"] == next_link


@pytest.mark.parametrize("url", [
    "https://graph.microsoft.com/v1.0/me/mailFolders/opaque==/messages/delta?$deltatoken=unchanged%2Bopaque",
    "https://graph.microsoft.com/v1.0/me/mailFolders('opaque==')/messages/delta?$deltatoken=unchanged%2Bopaque",
    "https://graph.microsoft.com/v1.0/me/mailFolders('opaque%3D%3D')/messages/delta?$deltatoken=unchanged%2Bopaque",
])
def test_equivalent_graph_folder_routes_keep_continuation_url_opaque(url):
    assert validate_link(url, "opaque==", kind="delta") == url
    with pytest.raises(OutlookResyncRequiredError):
        validate_link(url, "other==", kind="delta")


@pytest.mark.parametrize("address", ["alex@outlook.com", "  ALEX@OUTLOOK.COM  "])
def test_duplicate_outlook_registration_rolls_back_entire_registry(engine, outlook_config, address):
    from family_os.schema import household, person, source_account
    outlook_config["source_accounts"][1]["external_account"] = address
    with pytest.raises(ValueError, match="Duplicate active Outlook"):
        register(engine, outlook_config)
    for table in (household, person, source_account, source_sync_state, raw_source_record, source_record):
        assert not rows(engine, table)


def test_outlook_guard_checks_existing_registrations_and_rolls_back_changes(registered_outlook, outlook_config):
    from family_os.schema import household, person, source_account
    ingest(registered_outlook, "home", "out1", OutlookConnector(FakeGraph()))
    tables = (household, person, source_account, source_sync_state, raw_source_record, source_record)
    before = {table.name: rows(registered_outlook, table) for table in tables}
    changed = deepcopy(outlook_config)
    changed["household"]["name"] = "Changed synthetic name"
    changed["people"][0]["display_name"] = "Changed Alex"
    changed["source_accounts"] = [dict(changed["source_accounts"][0], id="replacement")]
    with pytest.raises(ValueError, match="Duplicate active Outlook"):
        register(registered_outlook, changed)
    assert {table.name: rows(registered_outlook, table) for table in tables} == before


@pytest.mark.parametrize("old_first", [True, False])
def test_disabled_old_outlook_and_enabled_replacement_are_transactional(registered_outlook, outlook_config, old_first):
    ingest(registered_outlook, "home", "out1", OutlookConnector(FakeGraph()))
    tables = (raw_source_record, source_record, source_sync_state)
    original_history = {table.name: rows(registered_outlook, table) for table in tables}
    old = dict(outlook_config["source_accounts"][0], enabled=False)
    replacement = dict(old, id="replacement", enabled=True, external_account=" ALEX@OUTLOOK.COM ")
    changed = deepcopy(outlook_config)
    changed["source_accounts"] = [old, replacement] if old_first else [replacement, old]
    register(registered_outlook, changed)
    register(registered_outlook, changed)  # Reloading this final state stays valid.
    with registered_outlook.connect() as connection:
        assert not get_account(connection, "home", "out1").enabled
        assert get_account(connection, "home", "replacement").enabled
    assert rows(registered_outlook, raw_source_record) == original_history[raw_source_record.name]
    assert rows(registered_outlook, source_record) == original_history[source_record.name]
    assert [row for row in rows(registered_outlook, source_sync_state) if row["source_account_id"] != "replacement"] == original_history[source_sync_state.name]


@pytest.mark.parametrize("second_owner", ["alex", "spouse"])
def test_distinct_outlook_identities_remain_allowed_for_person_or_spouse(engine, outlook_config, second_owner):
    outlook_config["source_accounts"][1]["owner_id"] = second_owner
    register(engine, outlook_config)
    register(engine, outlook_config)
    with engine.connect() as connection:
        first = get_account(connection, "home", "out1")
        second = get_account(connection, "home", "out2")
    assert first.external_account != second.external_account
    assert first.owner_id == "alex" and second.owner_id == second_owner


def test_same_identity_across_gmail_and_outlook_is_allowed(engine, outlook_config):
    gmail = outlook_config["source_accounts"][3]
    gmail["external_account"] = outlook_config["source_accounts"][0]["external_account"]
    register(engine, outlook_config)
    accounts = list_accounts(engine, "home")
    assert len(accounts) == 4
    assert next(item for item in accounts if item.id == "gmail").external_account == next(item for item in accounts if item.id == "out1").external_account


def test_same_outlook_identity_in_different_households_is_allowed(registered_outlook):
    register(registered_outlook, {"household": {"id": "other-home", "name": "Other synthetic"},
        "source_accounts": [{"id": "other-outlook", "provider": "outlook", "owner_type": "unknown",
                             "external_account": " ALEX@OUTLOOK.COM "}]})
    with registered_outlook.connect() as connection:
        assert get_account(connection, "home", "out1").enabled
        assert get_account(connection, "other-home", "other-outlook").enabled


def test_outlook_duplicate_guard_does_not_infer_dots_plus_or_alias_equivalence(engine, outlook_config):
    outlook_config["source_accounts"][1]["external_account"] = "a.lex@outlook.com"
    outlook_config["source_accounts"][2]["external_account"] = "alex+alias@outlook.com"
    register(engine, outlook_config)
    assert len(list_accounts(engine, "home")) == 4


def test_direct_database_duplicate_outlook_identity_blocks_reads_and_sync(registered_outlook):
    from sqlalchemy import update
    from family_os.schema import source_account
    with registered_outlook.begin() as connection:
        connection.execute(update(source_account).where(source_account.c.id == "out2")
                           .values(external_account=" ALEX@OUTLOOK.COM "))
    before = state(registered_outlook)
    with registered_outlook.connect() as connection, pytest.raises(ValueError, match="Duplicate active Outlook"):
        get_account(connection, "home", "out1")
    with pytest.raises(ValueError, match="Duplicate active Outlook"):
        list_accounts(registered_outlook, "home")
    client = FakeGraph()
    with pytest.raises(IngestionError):
        ingest(registered_outlook, "home", "out1", OutlookConnector(client))
    assert client.calls == []
    assert state(registered_outlook) == before
    assert not rows(registered_outlook, raw_source_record)
    assert not rows(registered_outlook, source_record)
