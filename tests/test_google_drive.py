"""Drive behavior uses only synthetic clients; identical suite on both databases."""
from copy import deepcopy
from dataclasses import replace
import json
import logging
from types import SimpleNamespace

import pytest
from sqlalchemy import select, update

from family_os.domain import SourceAccount
from family_os.google_drive import (GoogleDriveConnector, DriveHTTPClient, DrivePolicy,
    binding_fingerprint, minimize_file, transform_state, FILE_FIELDS, FILES_FIELDS, CHANGES_FIELDS, ABOUT_FIELDS)
from family_os.google_drive_identity import drive_identity
from family_os.google_drive_errors import (DriveIdentityError, DrivePolicyError, DriveAuthError,
    DriveAPIError, DriveResponseError, DriveResyncRequiredError, SharedDriveUnavailableError)
from family_os.ingestion import ingest, json_snapshot, DRIVE_FORBIDDEN_KEYS
from family_os.errors import IngestionError
from family_os.registry import register, get_account, list_accounts
from family_os.schema import household, person, source_account, source_sync_state, source_record, raw_source_record

ACCOUNT = SourceAccount("drive", "home", "google_drive", "person", "alex", "demo@example.invalid")
PERMISSION = "synthetic-stable-permission"
PRIVATE = "synthetic-token-name-owner-resource-key"
FP = binding_fingerprint(PERMISSION)


def file(fid="file1", **changes):
    return {"id": fid, "name": "Synthetic file", "mimeType": "text/plain",
        "createdTime": "2026-01-01T00:00:00Z", "modifiedTime": "2026-10-01T00:00:00Z",
        "parents": ["parent1"], "trashed": False, "version": "1", "size": "10", "md5Checksum": "synthetic-checksum",
        "owners": [{"permissionId": PERMISSION, "emailAddress": ACCOUNT.external_account, "displayName": "Synthetic", "me": True}], **changes}


class FakeDrive:
    bound_permission_id = PERMISSION
    def __init__(self):
        self.calls = []
        self.user = {"permissionId": PERMISSION, "emailAddress": ACCOUNT.external_account, "me": True}
        self.discovery = {None: {"drives": [{"id": "A"}, {"id": "B"}, {"id": "unselected"}]}}
        self.starts = {None: {"startPageToken": "start-user"}, "A": {"startPageToken": "start-A"}, "B": {"startPageToken": "start-B"}}
        self.baselines = {(None, None): {"files": [file()]}, ("A", None): {"files": [file("file-A", driveId="A")]},
                          ("B", None): {"files": [file("file-B", driveId="B")]}}
        self.deltas = {(None, "start-user"): {"changes": [], "newStartPageToken": "tip-user"},
                      (None, "tip-user"): {"changes": [], "newStartPageToken": "tip-user"},
                      ("A", "start-A"): {"changes": [], "newStartPageToken": "tip-A"},
                      ("A", "tip-A"): {"changes": [], "newStartPageToken": "tip-A"},
                      ("B", "start-B"): {"changes": [], "newStartPageToken": "tip-B"},
                      ("B", "tip-B"): {"changes": [], "newStartPageToken": "tip-B"}}
        self.session = SimpleNamespace(close=lambda: None)
    def result(self, value):
        if isinstance(value, Exception):
            raise value
        return deepcopy(value)
    def about(self):
        self.calls.append(("about",))
        return {"user": deepcopy(self.user)}
    def drives(self, page, size):
        self.calls.append(("drives", page, size))
        return self.result(self.discovery[page])
    def start_token(self, did):
        self.calls.append(("start", did))
        return self.result(self.starts[did])
    def files(self, did, page, size):
        self.calls.append(("files", did, page, size))
        return self.result(self.baselines[(did, page)])
    def changes(self, did, page, size):
        self.calls.append(("changes", did, page, size))
        return self.result(self.deltas[(did, page)])


def config():
    return {"household": {"id": "home", "name": "Synthetic"}, "people": [
        {"id": "alex", "display_name": "Alex"}, {"id": "spouse", "display_name": "Spouse"}],
        "source_accounts": [{"id": "drive", "provider": "google_drive", "owner_type": "person", "owner_id": "alex", "external_account": ACCOUNT.external_account}]}


def rows(engine, table):
    with engine.connect() as connection:
        return [dict(row) for row in connection.execute(select(table).order_by(*table.primary_key.columns)).mappings()]


def cursor(engine):
    return rows(engine, source_sync_state)[0]["cursor"]


def test_contract_baseline_capture_catchup_closes_race_and_incremental_resume(engine):
    register(engine, config()); fake = FakeDrive(); adapter = GoogleDriveConnector(fake)
    fake.deltas[(None, "start-user")] = {"changes": [{"fileId": "file1", "file": file(name="Renamed during baseline", parents=["moved-parent"])}], "newStartPageToken": "tip-user"}
    result = ingest(engine, "home", "drive", adapter)
    assert (result.inserted, result.updated, result.pages) == (1, 1, 3)
    assert [call[0] for call in fake.calls] == ["about", "start", "about", "files", "about", "changes"]
    state = json.loads(cursor(engine))
    assert state["phase"] == "idle" and state["streams"]["user"]["steady"] == "tip-user"
    record = rows(engine, source_record)[0]
    assert record["provider_object_id"] == "file1" and record["record_type"] == "document"
    assert record["subject"] == "Renamed during baseline" and record["raw_metadata"]["parents"] == ["moved-parent"]
    assert record["sender"] is None and record["recipients"] == [] and record["content_hash"] is None
    assert record["raw_metadata"]["md5Checksum"] == "synthetic-checksum"
    assert len(rows(engine, raw_source_record)) == 2
    assert ingest(engine, "home", "drive", adapter).pages == 1
    assert fake.calls[-1] == ("changes", None, "tip-user", 25)
    assert not any(call[0] == "drives" for call in fake.calls)
    assert PERMISSION not in cursor(engine)


def test_baseline_and_change_pagination_resumable_and_tip_final_only(engine):
    register(engine, config()); fake = FakeDrive(); adapter = GoogleDriveConnector(fake, page_size=1)
    fake.baselines[(None, None)]["nextPageToken"] = "opaque-baseline/+="
    fake.baselines[(None, "opaque-baseline/+=")] = {"files": [file("second", name="Synthetic file")]}
    fake.deltas[(None, "start-user")] = {"changes": [{"fileId": "file1", "file": file(name="Changed")}], "nextPageToken": "opaque-change/+="}
    fake.deltas[(None, "opaque-change/+=")] = {"changes": [], "newStartPageToken": "tip-user"}
    with pytest.raises(IngestionError, match="Page limit"):
        ingest(engine, "home", "drive", adapter, max_pages=2)
    stream = json.loads(cursor(engine))["streams"]["user"]
    assert stream["stage"] == "baseline" and stream["start"] == "start-user" and stream["baseline_page"] == "opaque-baseline/+="
    with pytest.raises(IngestionError, match="Page limit"):
        ingest(engine, "home", "drive", adapter, max_pages=2)
    stream = json.loads(cursor(engine))["streams"]["user"]
    assert stream["stage"] == "catchup" and stream["steady"] is None and stream["change_page"] == "opaque-change/+="
    ingest(engine, "home", "drive", adapter)
    assert json.loads(cursor(engine))["streams"]["user"]["steady"] == "tip-user"
    assert len(rows(engine, source_record)) == 2  # Equal names do not merge file IDs.
    fake.deltas[(None, "tip-user")] = {"changes": [], "nextPageToken": "steady-page"}
    fake.deltas[(None, "steady-page")] = {"changes": [], "newStartPageToken": "new-tip"}
    with pytest.raises(IngestionError, match="Page limit"):
        ingest(engine, "home", "drive", adapter, max_pages=1)
    stream = json.loads(cursor(engine))["streams"]["user"]
    assert stream["steady"] == "tip-user" and stream["change_page"] == "steady-page"
    ingest(engine, "home", "drive", adapter)
    assert json.loads(cursor(engine))["streams"]["user"]["steady"] == "new-tip"


def test_shared_opt_in_discovery_paging_independent_baseline_and_policy_migration(engine):
    register(engine, config()); fake = FakeDrive(); adapter = GoogleDriveConnector(fake, DrivePolicy(["A"]))
    fake.discovery[None] = {"drives": [{"id": "unselected"}], "nextPageToken": "discovery-page"}
    fake.discovery["discovery-page"] = {"drives": [{"id": "A"}, {"id": "B"}]}
    with pytest.raises(IngestionError, match="Page limit"):
        ingest(engine, "home", "drive", adapter, max_pages=1)
    assert json.loads(cursor(engine))["discovery"]["page"] == "discovery-page"
    ingest(engine, "home", "drive", adapter)
    before = json.loads(cursor(engine))
    for did in (None, "A"):
        assert fake.calls.index(("start", did)) < fake.calls.index(("files", did, None, 25))
    assert not any(call[0] in {"files", "start", "changes"} and call[1] in {"B", "unselected"} for call in fake.calls)
    with pytest.raises(DriveResyncRequiredError):
        GoogleDriveConnector(fake, DrivePolicy(["A", "B"])).fetch_changes(ACCOUNT, cursor(engine))
    transform_state(engine, "home", "drive", FP, DrivePolicy(["A"]), new_policy=DrivePolicy(["A", "B"]))
    state = json.loads(cursor(engine))
    assert state["streams"]["user"] == before["streams"]["user"]
    assert state["streams"]["drive:A"]["steady"] == "tip-A"
    assert state["streams"]["drive:B"]["stage"] == "start"
    assert ingest(engine, "home", "drive", GoogleDriveConnector(fake, DrivePolicy(["A", "B"]))).inserted == 1
    before = json.loads(cursor(engine)); history = rows(engine, raw_source_record)
    transform_state(engine, "home", "drive", FP, DrivePolicy(["A", "B"]), new_policy=DrivePolicy(["B"]))
    state = json.loads(cursor(engine))
    assert state["streams"]["drive:A"] == {**before["streams"]["drive:A"], "active": False}
    assert rows(engine, raw_source_record) == history
    ingest(engine, "home", "drive", GoogleDriveConnector(fake, DrivePolicy(["B"])))


def test_inaccessible_configured_drive_fails_without_provider_file_access(engine):
    register(engine, config()); fake = FakeDrive()
    with pytest.raises(SharedDriveUnavailableError):
        ingest(engine, "home", "drive", GoogleDriveConnector(fake, DrivePolicy(["not-visible"])))
    assert all(call[0] in {"about", "drives"} for call in fake.calls)
    assert cursor(engine) is None and rows(engine, source_record) == []


def test_rename_move_owner_drive_changes_same_id_then_trash_and_sparse_removal(engine):
    register(engine, config()); fake = FakeDrive(); adapter = GoogleDriveConnector(fake, DrivePolicy(["A"]))
    fake.baselines[(None, None)] = {"files": []}
    fake.baselines[("A", None)] = {"files": [file(driveId="A")]}
    ingest(engine, "home", "drive", adapter)
    changed = file(name="Renamed", parents=["new-parent"], driveId="A", owners=[{"permissionId": "other-owner", "me": False}])
    fake.deltas[("A", "tip-A")] = {"changes": [{"fileId": "file1", "file": changed}], "newStartPageToken": "tip-A"}
    assert ingest(engine, "home", "drive", adapter).updated == 1
    changed["trashed"] = True
    assert ingest(engine, "home", "drive", adapter).updated == 1
    record = rows(engine, source_record)[0]
    assert record["raw_metadata"]["trashed"] is True and record["raw_metadata"]["removed"] is False
    fake.deltas[("A", "tip-A")] = {"changes": [{"fileId": "file1", "removed": True, "driveId": "A"}], "newStartPageToken": "tip-A"}
    assert ingest(engine, "home", "drive", adapter).updated == 1
    record = rows(engine, source_record)[0]
    assert record["provider_object_id"] == "file1" and record["subject"] is None and record["occurred_at"] is None
    assert record["raw_metadata"] == {"file_id": "file1", "removed": True, "driveId": "A", "stream": {"kind": "shared_drive", "drive_id": "A"}}
    assert len(rows(engine, source_record)) == 1 and len(rows(engine, raw_source_record)) == 4
    assert ingest(engine, "home", "drive", adapter).unchanged == 1


def test_removed_change_with_current_resource_uses_only_returned_fields(engine):
    register(engine, config()); fake = FakeDrive(); adapter = GoogleDriveConnector(fake, DrivePolicy(["A"]))
    fake.baselines[(None, None)] = {"files": []}
    fake.baselines[("A", None)] = {"files": [file(driveId="A")]}
    ingest(engine, "home", "drive", adapter)
    fake.deltas[("A", "tip-A")] = {"changes": [{"fileId": "file1", "removed": True, "driveId": "A",
        "file": {"id": "file1", "mimeType": "text/plain", "description": PRIVATE}}], "newStartPageToken": "tip-A"}
    ingest(engine, "home", "drive", adapter)
    record = rows(engine, source_record)[0]
    assert record["raw_metadata"] == {"file_id": "file1", "removed": True, "stream": {"kind": "shared_drive", "drive_id": "A"},
        "driveId": "A", "change_drive_id": "A", "mimeType": "text/plain"}
    assert record["subject"] is None and "owners" not in record["raw_metadata"]
    assert len(rows(engine, raw_source_record)) == 2


def test_shortcut_folder_identity_and_no_target_fetch(engine):
    register(engine, config()); fake = FakeDrive()
    fake.baselines[(None, None)] = {"files": [file("shortcut", mimeType="application/vnd.google-apps.shortcut",
        shortcutDetails={"targetId": "target", "targetMimeType": "text/plain", "targetResourceKey": PRIVATE}),
        file("folder", name="Synthetic file", mimeType="application/vnd.google-apps.folder")]}
    ingest(engine, "home", "drive", GoogleDriveConnector(fake))
    records = {row["provider_object_id"]: row for row in rows(engine, source_record)}
    assert set(records) == {"shortcut", "folder"}
    assert records["shortcut"]["raw_metadata"]["shortcutDetails"] == {"targetId": "target", "targetMimeType": "text/plain"}
    assert records["folder"]["raw_metadata"]["mimeType"] == "application/vnd.google-apps.folder"
    assert all(row["content_hash"] is None for row in records.values())
    assert "target" not in [call[1] for call in fake.calls if len(call) > 1]
    assert all("path" not in row["raw_metadata"] for row in records.values())


PRIVATE_FIELDS = ["description", "properties", "appProperties", "permissions", "thumbnailLink", "exportLinks",
    "webContentLink", "webViewLink", "iconLink", "resourceKey", "contentHints", "imageMediaMetadata", "videoMediaMetadata",
    "labels", "labelInfo", "comments", "replies", "revisions", "content", "fileContents"]


def test_allowlist_privacy_and_optional_fields_only(engine):
    register(engine, config()); fake = FakeDrive()
    original = file(**{key: PRIVATE for key in PRIVATE_FIELDS})
    original.update(capabilities={"canDownload": True, "canEdit": PRIVATE}, sha1Checksum="synthetic-sha1",
                    sha256Checksum="synthetic-sha256", headRevisionId="revision-id", explicitlyTrashed=False, starred=True)
    original["owners"][0]["photoLink"] = PRIVATE
    fake.baselines[(None, None)] = {"files": [original]}
    ingest(engine, "home", "drive", GoogleDriveConnector(fake))
    persisted = rows(engine, raw_source_record)[0]["payload"]
    assert PRIVATE not in json.dumps(persisted)
    assert persisted["capabilities"] == {"canDownload": True}
    assert persisted["headRevisionId"] == "revision-id"
    assert rows(engine, source_record)[0]["content_hash"] is None
    assert minimize_file({"id": "minimal"}) == {"file_id": "minimal"}


@pytest.mark.parametrize("key", PRIVATE_FIELDS + ["targetResourceKey", "access_token"])
def test_drive_forbidden_keys_defense(key):
    with pytest.raises(ValueError):
        json_snapshot({"nested": [{key: PRIVATE}]}, DRIVE_FORBIDDEN_KEYS)


@pytest.mark.parametrize("target", [None, "A"])
def test_expired_token_and_explicit_recovery_only_target_stream(engine, target):
    register(engine, config()); fake = FakeDrive(); policy = DrivePolicy(["A"]); adapter = GoogleDriveConnector(fake, policy)
    ingest(engine, "home", "drive", adapter)
    key = "user" if target is None else "drive:A"
    token = "tip-user" if target is None else "tip-A"
    fake.deltas[(target, token)] = DriveResyncRequiredError(key)
    with pytest.raises(DriveResyncRequiredError) as failure:
        ingest(engine, "home", "drive", adapter)
    assert failure.value.stream == key
    state = json.loads(cursor(engine)); history = rows(engine, raw_source_record)
    assert state["streams"][key]["steady"] == token
    transform_state(engine, "home", "drive", FP, policy, target)
    after = json.loads(cursor(engine))
    assert after["streams"][key]["stage"] == "start"
    other = "drive:A" if target is None else "user"
    assert after["streams"][other] == state["streams"][other]
    assert rows(engine, raw_source_record) == history
    fake.starts[target] = {"startPageToken": "fresh-start"}
    fake.deltas[(target, "fresh-start")] = {"changes": [], "newStartPageToken": "fresh-tip"}
    fake.deltas[(target, token)] = {"changes": [], "newStartPageToken": token}
    assert ingest(engine, "home", "drive", adapter).inserted == 0
    assert rows(engine, raw_source_record) == history
    assert json.loads(cursor(engine))["streams"][key]["steady"] == "fresh-tip"


@pytest.mark.parametrize("stream", ["baseline", "changes"])
def test_failed_page_retains_cursor_and_history_without_private_logs(engine, caplog, stream):
    register(engine, config()); fake = FakeDrive(); adapter = GoogleDriveConnector(fake)
    with pytest.raises(IngestionError, match="Page limit"):
        ingest(engine, "home", "drive", adapter, max_pages=1 if stream == "baseline" else 2)
    before = rows(engine, source_sync_state); history = rows(engine, raw_source_record)
    if stream == "baseline":
        fake.baselines[(None, None)] = RuntimeError(PRIVATE)
    else:
        fake.deltas[(None, "start-user")] = RuntimeError(PRIVATE)
    caplog.set_level(logging.DEBUG)
    with pytest.raises(DriveResponseError) as error:
        ingest(engine, "home", "drive", adapter)
    assert rows(engine, source_sync_state) == before and rows(engine, raw_source_record) == history
    assert PRIVATE not in str(error.value) + caplog.text


@pytest.mark.parametrize("mutation", [lambda s: s.update(v=True), lambda s: s.update(account="other"),
    lambda s: s.update(household="other"), lambda s: s.update(identity="other"), lambda s: s.update(binding="other"),
    lambda s: s.update(policy="other"), lambda s: s.update(phase="other"), lambda s: s.update(extra=PRIVATE),
    lambda s: s.update(pending=[]), lambda s: s.update(pending=["user", "user"]), lambda s: s.update(pending=["unknown"]),
    lambda s: s["streams"]["user"].update(active=False), lambda s: s["streams"]["user"].update(stage="other"),
    lambda s: s["streams"]["user"].update(drive_id="A"), lambda s: s["streams"]["user"].update(start=None),
    lambda s: s["streams"]["user"].update(steady="premature-tip"), lambda s: s["streams"]["user"].update(baseline_page="no-trail"),
    lambda s: s["discovery"].update(extra=PRIVATE)])
def test_corrupt_state_fails_before_api(mutation):
    fake = FakeDrive(); adapter = GoogleDriveConnector(fake)
    state = json.loads(adapter.fetch_changes(ACCOUNT, None).next_cursor); mutation(state); fake.calls.clear()
    with pytest.raises(DriveResyncRequiredError):
        adapter.fetch_changes(ACCOUNT, json.dumps(state))
    assert fake.calls == []


@pytest.mark.parametrize("cursor_value", ["invalid", "[]", "null", '{"v":1,"v":1}'])
def test_invalid_or_duplicate_json_state(cursor_value):
    fake = FakeDrive()
    with pytest.raises(DriveResyncRequiredError):
        GoogleDriveConnector(fake).fetch_changes(ACCOUNT, cursor_value)
    assert fake.calls == []


@pytest.mark.parametrize("operation", ["baseline", "changes", "discovery"])
def test_page_cycles_fail_closed(operation):
    fake = FakeDrive(); policy = DrivePolicy(["A"]) if operation == "discovery" else DrivePolicy()
    adapter = GoogleDriveConnector(fake, policy)
    if operation == "discovery":
        fake.discovery[None] = {"drives": [], "nextPageToken": "a"}
        fake.discovery["a"] = {"drives": [], "nextPageToken": "b"}
        fake.discovery["b"] = {"drives": [], "nextPageToken": "a"}
    elif operation == "baseline":
        fake.baselines[(None, None)] = {"files": [], "nextPageToken": "a"}
        fake.baselines[(None, "a")] = {"files": [], "nextPageToken": "b"}
        fake.baselines[(None, "b")] = {"files": [], "nextPageToken": "a"}
    else:
        fake.deltas[(None, "start-user")] = {"changes": [], "nextPageToken": "a"}
        fake.deltas[(None, "a")] = {"changes": [], "nextPageToken": "b"}
        fake.deltas[(None, "b")] = {"changes": [], "nextPageToken": "a"}
    cursor_value = None
    with pytest.raises(DriveResyncRequiredError):
        for _ in range(8):
            cursor_value = adapter.fetch_changes(ACCOUNT, cursor_value).next_cursor


@pytest.mark.parametrize("change", [{"permissionId": "switched"}, {"emailAddress": "other@example.invalid"},
    {"me": False}, {"permissionId": ""}, {"emailAddress": ""}])
def test_later_identity_change_preserves_state_before_source_access(engine, change):
    register(engine, config()); fake = FakeDrive(); adapter = GoogleDriveConnector(fake)
    ingest(engine, "home", "drive", adapter)
    before = rows(engine, source_sync_state); history = rows(engine, raw_source_record)
    fake.user.update(change); fake.calls.clear()
    with pytest.raises(DriveIdentityError):
        ingest(engine, "home", "drive", adapter)
    assert fake.calls == [("about",)]
    assert rows(engine, source_sync_state) == before and rows(engine, raw_source_record) == history


@pytest.mark.parametrize("size", [False, 0, -1, 1001, "25"])
def test_page_size_bounded(size):
    with pytest.raises(ValueError):
        GoogleDriveConnector(FakeDrive(), page_size=size)


@pytest.mark.parametrize("change", [{"provider": "gmail"}, {"enabled": False}, {"external_account": None}])
def test_invalid_registration_fails_before_api(change):
    fake = FakeDrive()
    with pytest.raises(DriveIdentityError):
        GoogleDriveConnector(fake).fetch_changes(replace(ACCOUNT, **change), None)
    assert fake.calls == []


def test_registry_multi_provider_person_and_household_members(engine):
    c = config(); original = c["source_accounts"][0]
    c["source_accounts"] += [dict(original, id="gmail", provider="gmail"), dict(original, id="calendar", provider="google_calendar"),
        dict(original, id="secondary", external_account="secondary@example.invalid"),
        dict(original, id="spouse_drive", owner_id="spouse", external_account="spouse@example.invalid")]
    register(engine, c)
    assert len(list_accounts(engine, "home")) == 5
    assert drive_identity(" Demo.Name+tag@gmail.com ") == "demo.name+tag@gmail.com"


@pytest.mark.parametrize("reverse", [False, True])
def test_duplicate_rejection_rolls_back_and_disabled_replacement_transactional(engine, reverse):
    c = config(); register(engine, c)
    before = {t.name: rows(engine, t) for t in (household, person, source_account, source_sync_state)}
    c["household"]["name"] = "Changed"
    c["source_accounts"].append(dict(c["source_accounts"][0], id="replacement", external_account=" DEMO@EXAMPLE.INVALID "))
    with pytest.raises(ValueError, match="Duplicate active"):
        register(engine, c)
    assert {t.name: rows(engine, t) for t in (household, person, source_account, source_sync_state)} == before
    c["source_accounts"][0]["enabled"] = False
    if reverse:
        c["source_accounts"].reverse()
    register(engine, c); register(engine, c)
    assert {a.id: a.enabled for a in list_accounts(engine, "home")} == {"drive": False, "replacement": True}


def test_direct_database_duplicate_fails_before_provider_access(engine):
    c = config(); c["source_accounts"].append(dict(c["source_accounts"][0], id="other", external_account="other@example.invalid"))
    register(engine, c)
    with engine.begin() as connection:
        connection.execute(update(source_account).where(source_account.c.id == "other").values(external_account=" DEMO@EXAMPLE.INVALID "))
    with engine.connect() as connection, pytest.raises(ValueError, match="Duplicate active"):
        get_account(connection, "home", "drive")
    fake = FakeDrive()
    with pytest.raises(IngestionError):
        ingest(engine, "home", "drive", GoogleDriveConnector(fake))
    assert fake.calls == []


def test_drive_ownership_immutability_and_separate_households(engine):
    c = config(); register(engine, c); ingest(engine, "home", "drive", GoogleDriveConnector(FakeDrive()))
    before = {t.name: rows(engine, t) for t in (source_account, source_record, raw_source_record, source_sync_state)}
    c["source_accounts"][0]["owner_id"] = "spouse"
    with pytest.raises(ValueError, match="Explicit account owner is immutable"):
        register(engine, c)
    assert {t.name: rows(engine, t) for t in (source_account, source_record, raw_source_record, source_sync_state)} == before
    register(engine, {"household": {"id": "other", "name": "Other"}, "source_accounts": [
        {"id": "otherdrive", "provider": "google_drive", "owner_type": "unknown", "external_account": ACCOUNT.external_account}]})
    assert len(list_accounts(engine, "other")) == 1


def test_http_only_metadata_routes_exact_queries_and_no_content_endpoints():
    calls = []
    class Session:
        def get(self, url, **kwargs):
            calls.append((url, kwargs))
            return SimpleNamespace(status_code=200, json=lambda: {})
    client = DriveHTTPClient(Session(), PERMISSION)
    client.about(); client.drives("discovery-token", 250); client.start_token(None); client.start_token("A")
    for did in (None, "A"):
        client.files(did, "baseline/+=" ,25); client.changes(did, "changes/+=" ,25)
    assert {url.rsplit("/", 1)[-1] for url, _ in calls} == {"about", "drives", "startPageToken", "files", "changes"}
    assert calls[0][1]["params"] == {"fields": ABOUT_FIELDS}
    assert calls[1][1]["params"]["useDomainAdminAccess"] is False and calls[1][1]["params"]["pageSize"] == 100
    assert calls[4][1]["params"]["corpora"] == "user" and calls[4][1]["params"]["includeItemsFromAllDrives"] is False
    assert calls[6][1]["params"]["driveId"] == "A" and calls[6][1]["params"]["corpora"] == "drive"
    assert all("alt" not in kw["params"] and "q" not in kw["params"] and kw["allow_redirects"] is False for _, kw in calls)
    assert calls[4][1]["params"]["fields"] == FILES_FIELDS
    assert calls[5][1]["params"]["fields"] == CHANGES_FIELDS and calls[5][1]["params"]["includeRemoved"] is True
    assert calls[5][1]["params"]["pageToken"] == "changes/+="
    assert all(key not in FILE_FIELDS for key in PRIVATE_FIELDS + ["targetResourceKey"])


@pytest.mark.parametrize("status,error", [(401, DriveAuthError), (403, DrivePolicyError), (410, DriveResyncRequiredError),
    (429, DriveAPIError), (500, DriveAPIError), (302, DriveAPIError), (404, DriveAPIError)])
def test_http_errors_safe_and_typed(status, error, caplog):
    class Session:
        def get(self, *args, **kwargs):
            logging.getLogger("requests").debug(PRIVATE)
            return SimpleNamespace(status_code=status, json=lambda: {"error": PRIVATE})
    caplog.set_level(logging.DEBUG)
    with pytest.raises(error) as failure:
        DriveHTTPClient(Session()).changes(None, "private-continuation", 25)
    assert PRIVATE not in str(failure.value) + caplog.text and "private-continuation" not in str(failure.value) + caplog.text


@pytest.mark.parametrize("reason,location,error", [("invalid", "pageToken", DriveResyncRequiredError),
    ("invalidPageToken", None, DriveResyncRequiredError), ("invalid", "fields", DriveAPIError)])
def test_invalid_token_equivalent_is_specific_and_safe(reason, location, error):
    session = SimpleNamespace(get=lambda *a, **k: SimpleNamespace(status_code=400, json=lambda: {"error": {"errors": [
        {"reason": reason, "location": location, "message": PRIVATE}]}}))
    with pytest.raises(error) as failure:
        DriveHTTPClient(session).changes("A", "private-continuation", 25)
    assert PRIVATE not in str(failure.value)


@pytest.mark.parametrize("response", [{"files": [], "incompleteSearch": True}, {"files": "invalid"},
    {"files": [file(size=True)]}, {"files": [file(parents="invalid")]}, {"files": [file(owners=[PRIVATE])]},
    {"files": [file(capabilities={"canDownload": "yes"})]}, {"files": [file(modifiedTime="2026-10-01")]}])
def test_malformed_baseline_rollback(engine, response):
    register(engine, config()); fake = FakeDrive(); adapter = GoogleDriveConnector(fake)
    with pytest.raises(IngestionError, match="Page limit"):
        ingest(engine, "home", "drive", adapter, max_pages=1)
    before = rows(engine, source_sync_state)
    fake.baselines[(None, None)] = response
    with pytest.raises(DriveResponseError):
        ingest(engine, "home", "drive", adapter)
    assert rows(engine, source_sync_state) == before and rows(engine, raw_source_record) == []


@pytest.mark.parametrize("response,error", [
    ({"changes": [], "nextPageToken": "next", "newStartPageToken": "tip"}, DriveResyncRequiredError),
    ({"changes": []}, DriveResyncRequiredError),
    ({"changes": "bad", "newStartPageToken": "tip"}, DriveResponseError),
    ({"changes": [{"fileId": "file1"}], "newStartPageToken": "tip"}, DriveResponseError),
    ({"changes": [{"fileId": "file1", "file": file("other")}], "newStartPageToken": "tip"}, DriveResponseError),
    ({"changes": [{"fileId": "file1", "removed": "yes"}], "newStartPageToken": "tip"}, DriveResponseError),
    ({"changes": [], "newStartPageToken": ""}, DriveResponseError),
])
def test_malformed_changes_retains_prior_baseline_page(engine, response, error):
    register(engine, config()); fake = FakeDrive(); adapter = GoogleDriveConnector(fake)
    with pytest.raises(IngestionError, match="Page limit"):
        ingest(engine, "home", "drive", adapter, max_pages=2)
    before = rows(engine, source_sync_state); history = rows(engine, raw_source_record)
    fake.deltas[(None, "start-user")] = response
    with pytest.raises(error):
        ingest(engine, "home", "drive", adapter)
    assert rows(engine, source_sync_state) == before and rows(engine, raw_source_record) == history


def test_same_file_from_two_accounts_remains_separate_provenance(engine):
    c = config(); c["source_accounts"].append(dict(c["source_accounts"][0], id="second", external_account="other@example.invalid"))
    register(engine, c)
    ingest(engine, "home", "drive", GoogleDriveConnector(FakeDrive()))
    second = FakeDrive(); second.bound_permission_id = "other-permission"
    second.user.update(emailAddress="other@example.invalid", permissionId="other-permission")
    ingest(engine, "home", "second", GoogleDriveConnector(second))
    records = rows(engine, source_record)
    assert len(records) == 2 and {row["provider_object_id"] for row in records} == {"file1"}
    assert {row["source_account_id"] for row in records} == {"drive", "second"}


def test_disabled_replacement_keeps_original_records_and_cursor(engine):
    c = config(); register(engine, c)
    ingest(engine, "home", "drive", GoogleDriveConnector(FakeDrive()))
    history = {t.name: rows(engine, t) for t in (source_record, raw_source_record)}
    original_cursor = cursor(engine)
    old = c["source_accounts"][0]; old["enabled"] = False
    c["source_accounts"].insert(0, dict(old, id="replacement", enabled=True))
    register(engine, c)
    assert {t.name: rows(engine, t) for t in (source_record, raw_source_record)} == history
    assert next(r for r in rows(engine, source_sync_state) if r["source_account_id"] == "drive")["cursor"] == original_cursor


def test_unknown_recovery_and_wrong_policy_migration_leave_state_unchanged(engine):
    register(engine, config()); ingest(engine, "home", "drive", GoogleDriveConnector(FakeDrive()))
    before = rows(engine, source_sync_state)
    with pytest.raises(DrivePolicyError):
        transform_state(engine, "home", "drive", FP, drive_id="unknown")
    with pytest.raises(DriveResyncRequiredError):
        transform_state(engine, "home", "drive", FP, DrivePolicy(["A"]), new_policy=DrivePolicy(["B"]))
    assert rows(engine, source_sync_state) == before


def test_unselected_drive_changes_do_not_enable_crawling():
    fake = FakeDrive(); adapter = GoogleDriveConnector(fake)
    state = adapter.fetch_changes(ACCOUNT, None).next_cursor
    state = adapter.fetch_changes(ACCOUNT, state).next_cursor
    fake.deltas[(None, "start-user")] = {"changes": [{"changeType": "drive", "driveId": "unselected", "removed": True}], "newStartPageToken": "tip-user"}
    result = adapter.fetch_changes(ACCOUNT, state)
    assert result.records == () and set(json.loads(result.next_cursor)["streams"]) == {"user"}


@pytest.mark.parametrize("status", [403, 404])
def test_shared_stream_read_access_failure_is_safe_policy_error(status):
    session = SimpleNamespace(get=lambda *a, **k: SimpleNamespace(status_code=status, json=lambda: {"error": PRIVATE}))
    for operation in (lambda: DriveHTTPClient(session).start_token("A"),
        lambda: DriveHTTPClient(session).files("A", None, 25), lambda: DriveHTTPClient(session).changes("A", "page", 25)):
        with pytest.raises(SharedDriveUnavailableError) as failure:
            operation()
        assert PRIVATE not in str(failure.value)


def test_baseline_page_expiry_has_stream_specific_recovery_target():
    session = SimpleNamespace(get=lambda *a, **k: SimpleNamespace(status_code=410, json=lambda: {"error": PRIVATE}))
    with pytest.raises(DriveResyncRequiredError) as failure:
        DriveHTTPClient(session).files("A", "expired-page", 25)
    assert failure.value.stream == "drive:A"


def test_reinclude_inactive_shared_stream_resumes_saved_token(engine):
    register(engine, config()); fake = FakeDrive()
    ingest(engine, "home", "drive", GoogleDriveConnector(fake, DrivePolicy(["A"])))
    transform_state(engine, "home", "drive", FP, DrivePolicy(["A"]), new_policy=DrivePolicy())
    transform_state(engine, "home", "drive", FP, new_policy=DrivePolicy(["A"]))
    fake.calls.clear()
    ingest(engine, "home", "drive", GoogleDriveConnector(fake, DrivePolicy(["A"])))
    assert ("changes", "A", "tip-A", 25) in fake.calls
    assert not any(call[0] in {"start", "files"} for call in fake.calls)


def test_shared_removal_preserves_stream_provenance_without_deleting_observations(engine):
    register(engine, config()); fake = FakeDrive()
    fake.baselines[(None, None)] = {"files": []}
    fake.baselines[("A", None)] = {"files": [file(driveId="A")]}
    adapter = GoogleDriveConnector(fake, DrivePolicy(["A"]))
    ingest(engine, "home", "drive", adapter)
    fake.deltas[("A", "tip-A")] = {"changes": [{"fileId": "file1", "removed": True, "driveId": "A"}], "newStartPageToken": "tip-A"}
    ingest(engine, "home", "drive", adapter)
    history = rows(engine, raw_source_record)
    assert len(history) == 2
    assert all(r["payload"]["stream"] == {"kind": "shared_drive", "drive_id": "A"} for r in history)
    assert {r["payload"]["removed"] for r in history} == {False, True}
    assert len(rows(engine, source_record)) == 1


@pytest.mark.parametrize("drive_id", ["unselected", "A"])
def test_personal_baseline_filters_shared_drive_files_without_fetching(engine, drive_id):
    register(engine, config()); fake = FakeDrive()
    fake.baselines[(None, None)] = {"files": [file("excluded", driveId=drive_id)], "nextPageToken": "next-baseline"}
    fake.baselines[(None, "next-baseline")] = {"files": [file("ordinary", shared=True)]}
    adapter = GoogleDriveConnector(fake)
    ingest(engine, "home", "drive", adapter)
    assert [r["provider_object_id"] for r in rows(engine, source_record)] == ["ordinary"]
    assert [r["provider_object_id"] for r in rows(engine, raw_source_record)] == ["ordinary"]
    assert json.loads(cursor(engine))["streams"]["user"]["steady"] == "tip-user"
    assert all(call[0] == "about" or call[1] is None for call in fake.calls)


@pytest.mark.parametrize("stage", ["catchup", "incremental"])
@pytest.mark.parametrize("drive_id", ["unselected", "A"])
@pytest.mark.parametrize("location", ["change", "file"])
@pytest.mark.parametrize("kind", ["update", "trashed", "removed"])
def test_personal_changes_filter_shared_drive_observations(engine, stage, drive_id, location, kind):
    register(engine, config()); fake = FakeDrive()
    fake.baselines[(None, None)] = {"files": []}
    fake.baselines[("A", None)] = {"files": []}
    policy = DrivePolicy(["A"]) if drive_id == "A" else DrivePolicy()
    adapter = GoogleDriveConnector(fake, policy)
    if stage == "incremental":
        ingest(engine, "home", "drive", adapter)
        token = "tip-user"
    else:
        with pytest.raises(IngestionError, match="Page limit"):
            ingest(engine, "home", "drive", adapter, max_pages=3 if policy.include_shared else 2)
        token = "start-user"
    change = {"changeType": "file", "fileId": "excluded", "removed": kind == "removed"}
    if kind != "removed" or location == "file":
        change["file"] = file("excluded", trashed=kind == "trashed")
    if location == "change":
        change["driveId"] = drive_id
    else:
        change["file"]["driveId"] = drive_id
    fake.deltas[(None, token)] = {"changes": [change], "newStartPageToken": "filtered-tip"}
    fake.calls.clear()
    result = ingest(engine, "home", "drive", adapter)
    assert result.inserted == result.updated == result.unchanged == 0
    assert rows(engine, source_record) == rows(engine, raw_source_record) == []
    assert json.loads(cursor(engine))["streams"]["user"]["steady"] == "filtered-tip"
    assert not any(call[0] in {"start", "files", "changes"} and call[1] == "unselected" for call in fake.calls)
    assert {call[0] for call in fake.calls} <= {"about", "drives", "start", "files", "changes"}


@pytest.mark.parametrize("shared", [False, True])
def test_non_shared_drive_personal_and_directly_shared_items_still_ingest(engine, shared):
    register(engine, config()); fake = FakeDrive(); adapter = GoogleDriveConnector(fake)
    fake.baselines[(None, None)] = {"files": [file(shared=shared)]}
    ingest(engine, "home", "drive", adapter)
    fake.deltas[(None, "tip-user")] = {"changes": [{"fileId": "file1", "file": file(name="Updated ordinary file", shared=shared)}], "newStartPageToken": "tip-user"}
    assert ingest(engine, "home", "drive", adapter).updated == 1
    record = rows(engine, source_record)[0]
    assert record["subject"] == "Updated ordinary file" and record["raw_metadata"]["shared"] is shared
    assert record["raw_metadata"]["stream"] == {"kind": "personal"}
    assert len(rows(engine, raw_source_record)) == 2


@pytest.mark.parametrize("kind", ["update", "trashed", "removed", "removed_current"])
def test_selected_shared_drive_has_only_dedicated_observations_and_no_personal_overwrite(engine, kind):
    register(engine, config()); fake = FakeDrive()
    fake.baselines[(None, None)] = {"files": [file("file-A", driveId="A", name="Personal duplicate")]}
    fake.deltas[(None, "start-user")] = {"changes": [{"fileId": "file-A", "file": file("file-A", driveId="A", name="Personal catchup duplicate")}], "newStartPageToken": "tip-user"}
    adapter = GoogleDriveConnector(fake, DrivePolicy(["A"]))
    ingest(engine, "home", "drive", adapter)
    # Legitimate dedicated-stream updates and replay preserve history/idempotence.
    fake.deltas[("A", "tip-A")] = {"changes": [{"fileId": "file-A", "driveId": "A", "file": file("file-A", driveId="A", name="Dedicated update", parents=["moved-parent"])}], "newStartPageToken": "tip-A"}
    assert ingest(engine, "home", "drive", adapter).updated == 1
    before = rows(engine, source_record); history = rows(engine, raw_source_record)
    assert len(before) == 1 and len(history) == 2
    change = {"fileId": "file-A", "driveId": "A", "removed": kind.startswith("removed")}
    if kind != "removed":
        change["file"] = file("file-A", driveId="A", name="Personal overwrite", trashed=kind == "trashed")
    fake.deltas[(None, "tip-user")] = {"changes": [change], "newStartPageToken": "tip-user"}
    fake.calls.clear()
    result = ingest(engine, "home", "drive", adapter)
    assert result.inserted == result.updated == 0
    assert rows(engine, source_record) == before and rows(engine, raw_source_record) == history
    assert all(r["payload"]["stream"] == {"kind": "shared_drive", "drive_id": "A"} for r in history)
    assert not any(call[0] == "files" for call in fake.calls)


def test_move_between_selected_shared_drives_retains_file_identity_and_history(engine):
    register(engine, config()); fake = FakeDrive()
    fake.baselines[(None, None)] = {"files": []}
    fake.baselines[("A", None)] = {"files": [file(driveId="A")]}
    fake.baselines[("B", None)] = {"files": []}
    adapter = GoogleDriveConnector(fake, DrivePolicy(["A", "B"]))
    ingest(engine, "home", "drive", adapter)
    fake.deltas[("B", "tip-B")] = {"changes": [{"fileId": "file1", "driveId": "B",
        "file": file(driveId="B", name="Moved file", parents=["new-parent"])}], "newStartPageToken": "tip-B"}
    assert ingest(engine, "home", "drive", adapter).updated == 1
    record = rows(engine, source_record)[0]
    assert record["provider_object_id"] == "file1" and record["raw_metadata"]["driveId"] == "B"
    history = rows(engine, raw_source_record)
    assert len(history) == 2 and {r["payload"]["driveId"] for r in history} == {"A", "B"}
    assert all(r["payload"]["stream"]["kind"] == "shared_drive" for r in history)
