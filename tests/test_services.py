"""Application boundary tests use existing synthetic provider clients only."""
from dataclasses import asdict, FrozenInstanceError
import json
import logging
from types import SimpleNamespace

import pytest
from sqlalchemy import update

from family_os import services
from family_os.cli import main
from family_os.errors import IngestionError
from family_os.ingestion import IngestionResult
from family_os.registry import register
from family_os.schema import source_account, source_record, raw_source_record, source_sync_state
from test_gmail import FakeGmail
from test_outlook import FakeGraph
from test_google_calendar import FakeCalendar, ACCOUNT as CALENDAR_ACCOUNT, rows
from test_google_drive import FakeDrive, FP

PROVIDERS = ("gmail", "outlook", "google_calendar", "google_drive")
PRIVATE = "synthetic-provider-secret-cursor-payload"
AUTH = {p: getattr(services, p + "_auth") for p in PROVIDERS}
CONNECTORS = {"gmail": "GmailConnector", "outlook": "OutlookConnector",
              "google_calendar": "GoogleCalendarConnector", "google_drive": "GoogleDriveConnector"}
IDENTITIES = {"gmail": "demo@gmail.com", "outlook": "alex@outlook.com",
              "google_calendar": CALENDAR_ACCOUNT.external_account, "google_drive": "demo@example.invalid"}


def setup(engine, monkeypatch, provider):
    register(engine, {"household": {"id": "home", "name": "Synthetic"}, "source_accounts": [
        {"id": "account", "provider": provider, "owner_type": "unknown", "external_account": IDENTITIES[provider]}]})
    client = {"gmail": FakeGmail, "outlook": FakeGraph,
              "google_calendar": FakeCalendar, "google_drive": FakeDrive}[provider]()
    closed = []
    client.session = SimpleNamespace(close=lambda: closed.append(True))
    monkeypatch.setattr(AUTH[provider], "load_client", lambda account: client)
    return client, closed


def call(engine, provider, **kwargs):
    return getattr(services, "ingest_" + provider)(engine, "home", "account", **kwargs)


@pytest.mark.parametrize("provider", PROVIDERS)
def test_direct_service_real_connector_atomic_ingestion_safe_immutable_outcome(engine, monkeypatch, provider, capsys):
    client, closed = setup(engine, monkeypatch, provider)
    outcome = call(engine, provider, page_size=7)
    assert outcome.ingestion.inserted == 1 and closed == [True]
    assert outcome.verified_identity == (None if provider == "google_drive" else IDENTITIES[provider])
    assert len(rows(engine, raw_source_record)) == len(rows(engine, source_record)) == 1
    assert set(asdict(outcome)) == {"ingestion", "verified_identity"}
    assert set(asdict(outcome.ingestion)) == {"inserted", "updated", "unchanged", "pages"}
    with pytest.raises(FrozenInstanceError):
        outcome.verified_identity = PRIVATE
    assert capsys.readouterr().out == ""
    assert PRIVATE not in json.dumps(asdict(outcome))
    assert client is not outcome and all(r["content_hash"] is None for r in rows(engine, source_record))


@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize("invalid", ["household", "account", "disabled", "provider", "identity", "duplicate"])
def test_invalid_registration_blocks_secure_loader_and_network(engine, monkeypatch, provider, invalid):
    client, closed = setup(engine, monkeypatch, provider)
    with engine.begin() as connection:
        if invalid in {"disabled", "provider", "identity"}:
            values = {"disabled": {"enabled": False}, "provider": {"provider": "fixture"}, "identity": {"external_account": None}}[invalid]
            connection.execute(update(source_account).where(source_account.c.id == "account").values(**values))
    if invalid == "duplicate":
        register(engine, {"household": {"id": "home", "name": "Synthetic"}, "source_accounts": [
            {"id": "other", "provider": provider, "owner_type": "unknown", "external_account": "other@example.invalid"}]})
        with engine.begin() as connection:
            connection.execute(update(source_account).where(source_account.c.id == "other").values(external_account=IDENTITIES[provider]))
    calls = []
    monkeypatch.setattr(AUTH[provider], "load_client", lambda account: calls.append(account))
    with pytest.raises((ValueError, IngestionError)):
        getattr(services, "ingest_" + provider)(engine,
            "wrong" if invalid == "household" else "home", "missing" if invalid == "account" else "account")
    assert calls == client.calls == closed == []


@pytest.mark.parametrize("provider", PROVIDERS)
def test_services_preserve_provider_options_and_pre_ingest_verification(engine, monkeypatch, provider):
    client, closed = setup(engine, monkeypatch, provider)
    seen = []
    real_connector = getattr(services, CONNECTORS[provider])
    def build(*args, **kwargs):
        connector = real_connector(*args, **kwargs); seen.append(connector); return connector
    monkeypatch.setattr(services, CONNECTORS[provider], build)
    def ingest(engine_arg, home, account, connector, *, max_pages):
        assert engine_arg is engine and (home, account, max_pages) == ("home", "account", 9)
        assert connector is seen[0] and connector.page_size == 7
        if provider == "gmail":
            assert connector.query == "label:synthetic" and client.calls[0][0] == "profile"
        elif provider == "outlook":
            assert connector.policy.fingerprint == services.FolderPolicy(["inbox"], ["sentitems"]).fingerprint
            assert client.calls[0][0] == "identity"
        elif provider == "google_calendar":
            assert connector.policy.fingerprint == services.CalendarPolicy(["extra"], ["excluded"]).fingerprint
            assert client.calls[0][0] == "list"
        else:
            assert connector.policy.fingerprint == services.DrivePolicy(["A"]).fingerprint
            assert client.calls == []  # Identity is checked by the Drive page, never for routine display.
        return IngestionResult(pages=2)
    monkeypatch.setattr(services, "ingest", ingest)
    options = {"gmail": {"query": "label:synthetic"}, "outlook": {"include_folder": ["inbox"], "exclude_folder": ["sentitems"]},
        "google_calendar": {"include_calendar": ["extra"], "exclude_calendar": ["excluded"]}, "google_drive": {"include_shared_drive": ["A"]}}[provider]
    assert call(engine, provider, page_size=7, max_pages=9, **options).ingestion.pages == 2
    assert closed == [True]


@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize("stage", ["verification", "construction", "ingestion", "internal"])
@pytest.mark.parametrize("cleanup_fails", [False, True])
def test_client_cleanup_every_failure_preserves_primary_error(engine, monkeypatch, provider, stage, cleanup_fails, caplog):
    client, closed = setup(engine, monkeypatch, provider)
    caplog.set_level(logging.DEBUG)
    if cleanup_fails:
        def close():
            closed.append(True); raise RuntimeError(PRIVATE)
        client.session.close = close
    failure = RuntimeError(PRIVATE) if stage == "internal" else IngestionError("Safe primary failure")
    def fail(*args, **kwargs):
        raise failure
    if stage == "construction":
        monkeypatch.setattr(services, CONNECTORS[provider], fail)
    elif stage == "verification":
        if provider == "google_drive":
            client.about = fail  # Verification lives inside the Drive ingestion page.
            from family_os.google_drive_errors import DriveIdentityError
            failure = DriveIdentityError()
        else:
            monkeypatch.setattr(getattr(services, CONNECTORS[provider]), "verify_account", fail)
    else:
        monkeypatch.setattr(services, "ingest", fail)
    with pytest.raises(type(failure)) as error:
        call(engine, provider)
    if provider != "google_drive" or stage != "verification":
        assert error.value is failure
    assert closed == [True] and PRIVATE not in caplog.text
    if stage in {"ingestion", "internal"} and provider != "google_drive":
        assert error.value.verified_identity == IDENTITIES[provider]
    assert ("session cleanup failed" in caplog.text) is cleanup_fails
    assert rows(engine, source_record) == []


@pytest.mark.parametrize("provider", PROVIDERS)
def test_success_cleanup_failure_is_safe_and_keeps_result(engine, monkeypatch, provider, caplog):
    client, closed = setup(engine, monkeypatch, provider)
    def close():
        closed.append(True); raise RuntimeError(PRIVATE)
    client.session.close = close
    assert call(engine, provider).ingestion.inserted == 1
    assert closed == [True] and PRIVATE not in caplog.text
    assert "session cleanup failed" in caplog.text


@pytest.mark.parametrize("target", [None, CALENDAR_ACCOUNT.external_account])
def test_calendar_recovery_is_local_targeted_versioned_and_preserves_history(engine, monkeypatch, target):
    client, closed = setup(engine, monkeypatch, "google_calendar")
    call(engine, "google_calendar")
    before = rows(engine, source_sync_state)[0]; history = rows(engine, raw_source_record)
    calls = list(client.calls)
    monkeypatch.setattr(AUTH["google_calendar"], "load_client", lambda a: pytest.fail("Recovery loaded provider"))
    assert services.resync_google_calendar(engine, "home", "account", calendar_id=target) is None
    after = rows(engine, source_sync_state)[0]
    old, new = json.loads(before["cursor"]), json.loads(after["cursor"])
    assert after["version"] == before["version"] + 1
    if target is None:
        assert old["calendars"] == new["calendars"]
    else:
        assert old["list"] == new["list"]
    assert rows(engine, raw_source_record) == history and client.calls == calls and closed == [True]


@pytest.mark.parametrize("target", [None, "A"])
def test_drive_recovery_and_policy_migration_local_binding_and_history(engine, monkeypatch, target):
    client, closed = setup(engine, monkeypatch, "google_drive")
    call(engine, "google_drive", include_shared_drive=["A"])
    calls = list(client.calls); before = rows(engine, source_sync_state)[0]; history = rows(engine, raw_source_record)
    monkeypatch.setattr(AUTH["google_drive"], "load_client", lambda a: pytest.fail("Recovery loaded client"))
    bindings = []
    monkeypatch.setattr(AUTH["google_drive"], "load_binding", lambda a: bindings.append(a.id) or FP)
    assert services.resync_google_drive(engine, "home", "account", include_shared_drive=["A"], drive_id=target) is None
    after = rows(engine, source_sync_state)[0]
    old, new = json.loads(before["cursor"]), json.loads(after["cursor"])
    other = "drive:A" if target is None else "user"
    assert new["streams"][other] == old["streams"][other] and after["version"] == before["version"] + 1
    assert services.migrate_google_drive_policy(engine, "home", "account", previous_shared_drive=["A"], include_shared_drive=["A", "B"]) is None
    assert json.loads(rows(engine, source_sync_state)[0]["cursor"])["streams"]["drive:B"]["stage"] == "start"
    assert bindings == ["account", "account"] and rows(engine, raw_source_record) == history and client.calls == calls


@pytest.mark.parametrize("operation", ["resync_google_calendar", "resync_google_drive", "migrate_google_drive_policy"])
def test_recovery_invalid_account_before_keyring_or_network(engine, monkeypatch, operation):
    setup(engine, monkeypatch, "google_drive")
    monkeypatch.setattr(AUTH["google_drive"], "load_binding", lambda a: pytest.fail("Invalid recovery read credentials"))
    with pytest.raises((ValueError, IngestionError)):
        getattr(services, operation)(engine, "wrong-household", "account")


@pytest.mark.parametrize("provider", PROVIDERS)
def test_cli_delegates_safe_outputs_options_and_failure_identity(engine, monkeypatch, provider, capsys, caplog):
    calls = []
    identity = None if provider == "google_drive" else IDENTITIES[provider]
    def service(engine_arg, home, account, **kwargs):
        calls.append((home, account, kwargs))
        return services.IngestionOutcome(IngestionResult(inserted=2, pages=3), identity)
    monkeypatch.setattr(services, "ingest_" + provider, service)
    args = ["ingest-" + provider.replace("_", "-"), "--household", "home", "--account", "account", "--page-size", "7", "--max-pages", "9"]
    assert main(args) == 0
    output = capsys.readouterr().out.splitlines()
    assert json.loads(output[-1]) == {"inserted": 2, "updated": 0, "unchanged": 0, "pages": 3}
    assert len(output) == (1 if identity is None else 2)
    if identity:
        assert identity in output[0]
    assert calls[0][0:2] == ("home", "account") and calls[0][2]["page_size"] == 7 and calls[0][2]["max_pages"] == 9
    def failed(*args, **kwargs):
        error = IngestionError("Safe failed page"); error.verified_identity = identity; raise error
    monkeypatch.setattr(services, "ingest_" + provider, failed)
    assert main(args) == 1
    failed_output = capsys.readouterr().out
    assert (identity in failed_output) if identity else not failed_output
    assert "Safe failed page" in caplog.text and PRIVATE not in caplog.text


@pytest.mark.parametrize("command,operation,options", [
    ("google-calendar-resync", "resync_google_calendar", ["--calendar-list"]),
    ("google-drive-resync", "resync_google_drive", ["--personal"]),
    ("google-drive-policy", "migrate_google_drive_policy", ["--previous-shared-drive", "A", "--include-shared-drive", "B"])])
def test_cli_recovery_delegates_without_credential_or_connector_ownership(engine, monkeypatch, command, operation, options, capsys):
    calls = []
    monkeypatch.setattr(services, operation, lambda *args, **kwargs: calls.append((args[1:], kwargs)))
    assert main([command, "--household", "home", "--account", "account", *options]) == 0
    assert calls[0][0] == ("home", "account") and "historical records retained" in capsys.readouterr().out
    if command == "google-drive-policy":
        assert calls[0][1] == {"previous_shared_drive": ["A"], "include_shared_drive": ["B"]}


@pytest.mark.parametrize("provider", PROVIDERS)
def test_cli_real_service_failed_page_keeps_identity_and_safe_error(engine, monkeypatch, provider, capsys, caplog):
    client, closed = setup(engine, monkeypatch, provider)
    def failed(*args, **kwargs):
        raise RuntimeError(PRIVATE)
    monkeypatch.setattr(services, "ingest", failed)
    assert main(["ingest-" + provider.replace("_", "-"), "--household", "home", "--account", "account"]) == 1
    output = capsys.readouterr().out
    assert (IDENTITIES[provider] in output) if provider != "google_drive" else not output
    assert PRIVATE not in output + caplog.text and "Operation failed" in caplog.text
    assert closed == [True]


@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize("category", ["auth", "policy"])
def test_loaded_clients_close_on_typed_auth_and_policy_errors(engine, monkeypatch, provider, category):
    client, closed = setup(engine, monkeypatch, provider)
    from family_os.errors import GmailAuthError
    from family_os.outlook_errors import OutlookAuthError, OutlookPolicyError
    from family_os.google_calendar_errors import CalendarAuthError, CalendarPolicyError
    from family_os.google_drive_errors import DriveAuthError, DrivePolicyError
    types = {"gmail": (GmailAuthError, GmailAuthError), "outlook": (OutlookAuthError, OutlookPolicyError),
        "google_calendar": (CalendarAuthError, CalendarPolicyError), "google_drive": (DriveAuthError, DrivePolicyError)}
    failure = types[provider][category == "policy"]()
    def failed(*args, **kwargs):
        raise failure
    monkeypatch.setattr(services, "ingest", failed)
    with pytest.raises(type(failure)) as error:
        call(engine, provider)
    assert error.value is failure and closed == [True]


def test_identity_annotation_failure_never_masks_primary_failure(engine, monkeypatch):
    setup(engine, monkeypatch, "gmail")
    class Failure(RuntimeError):
        @property
        def verified_identity(self):
            return None
    failure = Failure("Safe primary failure")
    def failed(*args, **kwargs):
        raise failure
    monkeypatch.setattr(services, "ingest", failed)
    with pytest.raises(Failure) as error:
        services.ingest_gmail(engine, "home", "account")
    assert error.value is failure
