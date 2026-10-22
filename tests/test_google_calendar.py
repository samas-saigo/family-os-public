"""Synthetic Calendar streams only; runs on SQLite and PostgreSQL unchanged."""
from copy import deepcopy
from dataclasses import replace
import json
import logging
from types import SimpleNamespace

import pytest
from sqlalchemy import select, update

from family_os.domain import SourceAccount
from family_os.google_calendar import (GoogleCalendarConnector, CalendarHTTPClient, CalendarPolicy,
    object_identity, minimize_event, recover_stream, EVENT_PROJECTION, LIST_FIELDS)
from family_os.google_calendar_errors import (CalendarIdentityError, CalendarAPIError,
    CalendarPolicyError, CalendarResyncRequiredError, CalendarAuthError)
from family_os.google_calendar_identity import calendar_identity
from family_os.ingestion import ingest, json_snapshot, CALENDAR_FORBIDDEN_KEYS
from family_os.errors import IngestionError
from family_os.registry import register, get_account, list_accounts
from family_os.schema import household, person, source_account, source_record, raw_source_record, source_sync_state

ACCOUNT = SourceAccount("cal", "home", "google_calendar", "person", "alex", "demo@example.invalid")
PRIVATE = "synthetic-description-token-attendee-location"


def calendar(cid=ACCOUNT.external_account, **changes):
    return {"id": cid, "primary": cid == ACCOUNT.external_account, "selected": True,
            "hidden": False, "accessRole": "owner", **changes}


def event(eid="event1", **changes):
    return {"id": eid, "status": "confirmed", "iCalUID": "meeting@example.invalid", "eventType": "fromGmail",
        "created": "2026-01-01T12:00:00Z", "updated": "2026-01-02T12:00:00Z", "summary": "Synthetic meeting",
        "start": {"dateTime": "2026-10-05T10:00:00+01:00", "timeZone": "Europe/London"},
        "end": {"dateTime": "2026-10-05T11:00:00+01:00"},
        "organizer": {"email": "organizer@example.invalid", "displayName": "Synthetic", "self": False},
        "attendees": [{"email": "guest@example.invalid", "displayName": "Guest", "self": False,
                       "responseStatus": "accepted", "optional": True, "resource": False}], **changes}


class FakeCalendar:
    def __init__(self):
        self.calls = []
        self.discovery = {(None, None): {"items": [calendar()], "nextSyncToken": "list-sync"},
                          (None, "list-sync"): {"items": [], "nextSyncToken": "list-sync"}}
        self.event_pages = {(ACCOUNT.external_account, None, None): {"items": [event()], "nextSyncToken": "event-sync"},
                            (ACCOUNT.external_account, None, "event-sync"): {"items": [event()], "nextSyncToken": "event-sync"}}
        self.session = SimpleNamespace(close=lambda: None)

    def calendar_list(self, page_token, sync_token, page_size):
        self.calls.append(("list", page_token, sync_token, page_size))
        value = self.discovery[(page_token, sync_token)]
        if isinstance(value, Exception):
            raise value
        return deepcopy(value)

    def events(self, cid, page_token, sync_token, page_size):
        self.calls.append(("event", cid, page_token, sync_token, page_size))
        value = self.event_pages[(cid, page_token, sync_token)]
        if isinstance(value, Exception):
            raise value
        return deepcopy(value)


def config():
    return {"household": {"id": "home", "name": "Synthetic"}, "people": [
        {"id": "alex", "display_name": "Alex"}, {"id": "spouse", "display_name": "Spouse"}],
        "source_accounts": [dict(id=ACCOUNT.id, provider=ACCOUNT.provider, owner_type="person", owner_id="alex",
                                 external_account=ACCOUNT.external_account)]}


def rows(engine, table):
    with engine.connect() as connection:
        return [dict(row) for row in connection.execute(select(table).order_by(*table.primary_key.columns)).mappings()]


def saved(engine):
    return rows(engine, source_sync_state)[0]["cursor"]


def test_contract_replay_metadata_change_and_cancellation_history(engine):
    register(engine, config())
    fake = FakeCalendar()
    adapter = GoogleCalendarConnector(fake)
    result = ingest(engine, "home", "cal", adapter)
    assert (result.inserted, result.pages) == (1, 2)
    record = rows(engine, source_record)[0]
    assert record["record_type"] == "calendar_event" and record["content_hash"] is None
    assert record["provider_object_id"] == object_identity(ACCOUNT.external_account, "event1")
    assert record["raw_metadata"]["iCalUID"] == "meeting@example.invalid"
    assert ingest(engine, "home", "cal", adapter).unchanged == 1
    fake.event_pages[(ACCOUNT.external_account, None, "event-sync")] = {"items": [event(summary="Changed")], "nextSyncToken": "event-sync"}
    assert ingest(engine, "home", "cal", adapter).updated == 1
    fake.event_pages[(ACCOUNT.external_account, None, "event-sync")] = {"items": [{"id": "event1", "status": "cancelled"}], "nextSyncToken": "event-sync"}
    assert ingest(engine, "home", "cal", adapter).updated == 1
    assert len(rows(engine, raw_source_record)) == 3
    assert rows(engine, source_record)[0]["raw_metadata"] == {"calendar_id": ACCOUNT.external_account, "event_id": "event1", "status": "cancelled"}
    assert any(row["payload"].get("summary") == "Synthetic meeting" for row in rows(engine, raw_source_record))


def test_paginated_calendar_list_and_events_resume_opaque_tokens(engine):
    register(engine, config())
    fake = FakeCalendar()
    fake.discovery[(None, None)] = {"items": [calendar()], "nextPageToken": "opaque-list/+/="}
    fake.discovery[("opaque-list/+/=", None)] = {"items": [calendar("shared")], "nextSyncToken": "list-sync"}
    fake.event_pages[(ACCOUNT.external_account, None, None)] = {"items": [event()], "nextPageToken": "opaque-event/+/="}
    fake.event_pages[(ACCOUNT.external_account, "opaque-event/+/=", None)] = {"items": [event("second")], "nextSyncToken": "event-sync"}
    fake.event_pages[("shared", None, None)] = {"items": [event()], "nextSyncToken": "shared-sync"}
    adapter = GoogleCalendarConnector(fake, page_size=1)
    with pytest.raises(IngestionError, match="Page limit reached"):
        ingest(engine, "home", "cal", adapter, max_pages=1)
    state = json.loads(saved(engine))
    assert state["list"]["page"] == "opaque-list/+/=" and state["list"]["sync"] is None
    with pytest.raises(IngestionError, match="Page limit reached"):
        ingest(engine, "home", "cal", adapter, max_pages=2)
    state = json.loads(saved(engine))
    assert state["calendars"][ACCOUNT.external_account]["events"]["page"] == "opaque-event/+/="
    assert state["calendars"][ACCOUNT.external_account]["events"]["sync"] is None
    assert ingest(engine, "home", "cal", adapter).inserted == 2
    records = rows(engine, source_record)
    assert len(records) == 3
    assert len({row["provider_object_id"] for row in records}) == 3
    assert object_identity("ab", "c") != object_identity("a", "bc")
    assert object_identity('a","b', "c") != object_identity("a", 'b","c')


def test_incremental_event_pagination_keeps_original_sync_until_final():
    fake = FakeCalendar(); adapter = GoogleCalendarConnector(fake)
    a = adapter.fetch_changes(ACCOUNT, None); b = adapter.fetch_changes(ACCOUNT, a.next_cursor)
    c = adapter.fetch_changes(ACCOUNT, b.next_cursor)
    fake.event_pages[(ACCOUNT.external_account, None, "event-sync")] = {"items": [], "nextPageToken": "incremental-page"}
    d = adapter.fetch_changes(ACCOUNT, c.next_cursor)
    state = json.loads(d.next_cursor)["calendars"][ACCOUNT.external_account]["events"]
    assert state["sync"] == "event-sync" and state["page"] == "incremental-page"
    fake.event_pages[(ACCOUNT.external_account, "incremental-page", "event-sync")] = {"items": [], "nextSyncToken": "new-event-sync"}
    e = adapter.fetch_changes(ACCOUNT, d.next_cursor)
    assert json.loads(e.next_cursor)["calendars"][ACCOUNT.external_account]["events"]["sync"] == "new-event-sync"
    assert fake.calls[-1][1:4] == (ACCOUNT.external_account, "incremental-page", "event-sync")


def test_incremental_discovery_new_and_removed_streams_preserve_other_tokens_and_history(engine):
    register(engine, config()); fake = FakeCalendar(); adapter = GoogleCalendarConnector(fake)
    ingest(engine, "home", "cal", adapter)
    fake.discovery[(None, "list-sync")] = {"items": [calendar("shared")], "nextPageToken": "list-incremental"}
    fake.discovery[("list-incremental", "list-sync")] = {"items": [], "nextSyncToken": "new-list-sync"}
    fake.event_pages[("shared", None, None)] = {"items": [event()], "nextSyncToken": "shared-sync"}
    ingest(engine, "home", "cal", adapter)
    assert ("event", ACCOUNT.external_account, None, "event-sync", 25) in fake.calls
    assert ("list", "list-incremental", "list-sync", 25) in fake.calls
    fake.discovery[(None, "new-list-sync")] = {"items": [{"id": "shared", "deleted": True}], "nextSyncToken": "new-list-sync"}
    ingest(engine, "home", "cal", adapter)
    state = json.loads(saved(engine))
    assert not state["calendars"]["shared"]["active"]
    assert state["calendars"]["shared"]["events"]["sync"] == "shared-sync"
    assert len(rows(engine, source_record)) == 2


@pytest.mark.parametrize("failure_stream", ["calendar_list", ACCOUNT.external_account])
def test_expired_stream_safe_failure_and_targeted_recovery(engine, failure_stream):
    register(engine, config()); fake = FakeCalendar(); adapter = GoogleCalendarConnector(fake)
    fake.discovery[(None, None)]["items"].append(calendar("shared"))
    fake.event_pages[("shared", None, None)] = {"items": [event()], "nextSyncToken": "shared-sync"}
    ingest(engine, "home", "cal", adapter)
    fake.event_pages[("shared", None, "shared-sync")] = {"items": [], "nextSyncToken": "shared-sync"}
    if failure_stream == "calendar_list":
        fake.discovery[(None, "list-sync")] = CalendarResyncRequiredError("calendar_list")
    else:
        fake.event_pages[(ACCOUNT.external_account, None, "event-sync")] = CalendarResyncRequiredError(ACCOUNT.external_account)
    history = rows(engine, raw_source_record)
    before = saved(engine)
    with pytest.raises(CalendarResyncRequiredError) as error:
        ingest(engine, "home", "cal", adapter)
    assert error.value.stream == failure_stream
    if failure_stream == "calendar_list":
        assert saved(engine) == before
    else:
        # The successful discovery page committed, but the failed event page did not.
        assert json.loads(saved(engine))["calendars"] == json.loads(before)["calendars"]
    recover_stream(engine, "home", "cal", calendar_id=None if failure_stream == "calendar_list" else failure_stream)
    state = json.loads(saved(engine))
    assert rows(engine, raw_source_record) == history
    assert state["calendars"]["shared"]["events"]["sync"] == "shared-sync"
    if failure_stream == "calendar_list":
        assert state["list"]["sync"] is None
        assert state["calendars"][ACCOUNT.external_account]["events"]["sync"] == "event-sync"
    else:
        assert state["list"]["sync"] == "list-sync"
        assert state["calendars"][ACCOUNT.external_account]["events"]["sync"] is None
    fake.discovery[(None, "list-sync")] = {"items": [], "nextSyncToken": "list-sync"}
    assert ingest(engine, "home", "cal", adapter).inserted == 0
    assert rows(engine, raw_source_record) == history


@pytest.mark.parametrize("meta,include,exclude,selected", [
    ({"primary": True, "hidden": True, "selected": False}, (), (), True),
    ({"hidden": True}, (), (), False), ({"selected": False}, (), (), False),
    ({"hidden": True}, ("shared",), (), True), ({"accessRole": "freeBusyReader"}, ("shared",), (), False),
    ({}, ("shared",), ("shared",), False), ({}, (), (), True),
])
def test_calendar_policy(meta, include, exclude, selected):
    from family_os.google_calendar import calendar_metadata
    assert CalendarPolicy(include, exclude).selected("shared", calendar_metadata(calendar("shared", **meta))) == selected


def test_primary_exclusion_rejected():
    from family_os.google_calendar import calendar_metadata
    with pytest.raises(CalendarPolicyError):
        CalendarPolicy(exclude=[ACCOUNT.external_account]).selected(ACCOUNT.external_account, calendar_metadata(calendar()))


def test_recurring_series_modified_and_cancelled_exceptions_all_day_and_timezone(engine):
    register(engine, config()); fake = FakeCalendar()
    fake.event_pages[(ACCOUNT.external_account, None, None)]["items"] = [
        event("series", recurrence=["RRULE:FREQ=WEEKLY;BYDAY=MO"], start={"date": "2026-10-05"}, end={"date": "2026-10-06"}),
        event("exception", recurringEventId="series", originalStartTime={"date": "2026-10-05"}),
        {"id": "cancelled", "status": "cancelled", "recurringEventId": "series", "originalStartTime": {"dateTime": "2026-10-05T10:00:00", "timeZone": "Europe/London"}}]
    assert ingest(engine, "home", "cal", GoogleCalendarConnector(fake)).inserted == 3
    metadata = {r["raw_metadata"]["event_id"]: r["raw_metadata"] for r in rows(engine, source_record)}
    assert metadata["series"]["recurrence"] == ["RRULE:FREQ=WEEKLY;BYDAY=MO"]
    assert metadata["exception"]["recurringEventId"] == "series"
    assert metadata["cancelled"]["originalStartTime"]["timeZone"] == "Europe/London"


def test_allowlist_excludes_private_fields_at_every_level(engine):
    register(engine, config()); fake = FakeCalendar()
    original = event(description=PRIVATE, attachments=[{"fileUrl": PRIVATE}], extendedProperties={"private": PRIVATE},
        privateCopy=True, gadget={"title": PRIVATE}, source={"url": PRIVATE}, conferenceData={"notes": PRIVATE}, hangoutLink=PRIVATE)
    original["organizer"]["extra"] = PRIVATE
    original["attendees"][0]["comment"] = PRIVATE
    original["start"]["unknown"] = PRIVATE
    fake.event_pages[(ACCOUNT.external_account, None, None)]["items"] = [original]
    ingest(engine, "home", "cal", GoogleCalendarConnector(fake))
    assert PRIVATE not in json.dumps(rows(engine, raw_source_record), default=str) + json.dumps(rows(engine, source_record), default=str)
    assert rows(engine, source_record)[0]["content_hash"] is None


@pytest.mark.parametrize("key", ["description", "attachments", "extendedProperties", "privateCopy", "gadget", "conferenceData", "fileUrl"])
def test_independent_forbidden_key_defense(key):
    with pytest.raises(ValueError, match="prohibited"):
        json_snapshot({"nested": [{key: PRIVATE}]}, CALENDAR_FORBIDDEN_KEYS)


@pytest.mark.parametrize("identities", [[], [calendar(primary=False)], [calendar(), calendar("other", primary=True)]])
def test_primary_must_be_unique(identities):
    fake = FakeCalendar(); fake.discovery[(None, None)]["items"] = identities
    with pytest.raises(CalendarIdentityError):
        GoogleCalendarConnector(fake).verify_account(ACCOUNT)


def test_later_account_switch_fails_without_cursor_or_record_change(engine):
    register(engine, config()); fake = FakeCalendar(); adapter = GoogleCalendarConnector(fake)
    ingest(engine, "home", "cal", adapter)
    before = {t.name: rows(engine, t) for t in (source_record, raw_source_record, source_sync_state)}
    fake.discovery[(None, None)]["items"] = [calendar("other", primary=True)]
    with pytest.raises(CalendarIdentityError):
        ingest(engine, "home", "cal", adapter)
    assert {t.name: rows(engine, t) for t in (source_record, raw_source_record, source_sync_state)} == before


@pytest.mark.parametrize("mutate", [
    lambda s: s.update(v=True), lambda s: s.update(account="other"), lambda s: s.update(household="other"),
    lambda s: s.update(identity="other"), lambda s: s.update(policy="other"), lambda s: s.update(extra=1),
    lambda s: s.update(pending=["unknown"]), lambda s: s.update(phase="unknown"),
    lambda s: s["list"].update(page="token"), lambda s: s["calendars"][ACCOUNT.external_account].update(active="yes"),
    lambda s: s["calendars"][ACCOUNT.external_account]["events"].update(sync=0),
    lambda s: s["calendars"][ACCOUNT.external_account]["meta"].update(extra=PRIVATE),
    lambda s: s["calendars"][ACCOUNT.external_account]["meta"].update(primary=False),
    lambda s: s["list"].update(sync=None),
])
def test_corrupt_cursor_fails_before_private_api_calls(mutate):
    fake = FakeCalendar(); adapter = GoogleCalendarConnector(fake)
    state = json.loads(adapter.fetch_changes(ACCOUNT, None).next_cursor)
    mutate(state); fake.calls.clear()
    with pytest.raises(CalendarResyncRequiredError):
        adapter.fetch_changes(ACCOUNT, json.dumps(state))
    assert fake.calls == []


@pytest.mark.parametrize("bad", ["not-json", "null", "[]"])
def test_invalid_json_cursor(bad):
    with pytest.raises(CalendarResyncRequiredError):
        GoogleCalendarConnector(FakeCalendar()).fetch_changes(ACCOUNT, bad)


def test_failed_event_page_keeps_committed_cursor_and_safe_logs(engine, caplog):
    register(engine, config()); fake = FakeCalendar(); adapter = GoogleCalendarConnector(fake)
    with pytest.raises(IngestionError, match="Page limit"):
        ingest(engine, "home", "cal", adapter, max_pages=1)
    before = saved(engine)
    fake.event_pages[(ACCOUNT.external_account, None, None)] = RuntimeError(PRIVATE)
    caplog.set_level(logging.DEBUG)
    with pytest.raises(CalendarAPIError) as err:
        ingest(engine, "home", "cal", adapter)
    assert saved(engine) == before
    assert PRIVATE not in str(err.value) + caplog.text
    assert rows(engine, raw_source_record) == []


@pytest.mark.parametrize("status,error", [(401, CalendarAuthError), (403, CalendarPolicyError),
    (410, CalendarResyncRequiredError), (429, CalendarAPIError), (500, CalendarAPIError), (302, CalendarAPIError)])
def test_http_errors_are_safe_and_typed(status, error, caplog):
    class Session:
        def get(self, *args, **kwargs):
            logging.getLogger("requests").debug(PRIVATE)
            return SimpleNamespace(status_code=status, json=lambda: {"error": PRIVATE})
    caplog.set_level(logging.DEBUG)
    with pytest.raises(error) as failure:
        CalendarHTTPClient(Session()).events("shared", "page-private", "sync-private", 25)
    assert PRIVATE not in str(failure.value) + caplog.text
    assert "sync-private" not in str(failure.value) + caplog.text


def test_http_requests_fixed_projection_sync_compatible_and_safe_routing():
    calls = []
    class Session:
        def get(self, url, **kwargs):
            calls.append((url, kwargs))
            return SimpleNamespace(status_code=200, json=lambda: {"items": [], "nextSyncToken": "sync"})
    client = CalendarHTTPClient(Session())
    client.calendar_list("opaque-list", "opaque-sync", 2)
    client.events("calendar/../?evil", "opaque-page", "opaque-sync", 2)
    list_params, event_params = calls[0][1]["params"], calls[1][1]["params"]
    assert list_params["fields"] == LIST_FIELDS and list_params["showDeleted"] is True
    assert event_params == {"maxResults": 2, "singleEvents": False, "showDeleted": True,
        "fields": EVENT_PROJECTION, "pageToken": "opaque-page", "syncToken": "opaque-sync"}
    assert calls[1][0].endswith("calendar%2F..%2F%3Fevil/events")
    assert all(c[1]["allow_redirects"] is False for c in calls)
    assert all(key not in event_params for key in ("timeMin", "timeMax", "orderBy", "q", "iCalUID"))
    assert all(field not in EVENT_PROJECTION for field in ("description", "attachments", "extendedProperties", "conferenceData"))


@pytest.mark.parametrize("response", [ {}, {"items": [], "nextPageToken": "a", "nextSyncToken": "b"},
    {"items": [], "nextSyncToken": ""}, {"items": [], "nextPageToken": 1}])
def test_invalid_continuation_rejected(response):
    fake = FakeCalendar(); adapter = GoogleCalendarConnector(fake)
    state = adapter.fetch_changes(ACCOUNT, None).next_cursor
    fake.event_pages[(ACCOUNT.external_account, None, None)] = response
    with pytest.raises(CalendarResyncRequiredError):
        adapter.fetch_changes(ACCOUNT, state)


def test_token_cycles_fail_closed():
    fake = FakeCalendar(); adapter = GoogleCalendarConnector(fake)
    state = adapter.fetch_changes(ACCOUNT, None).next_cursor
    fake.event_pages[(ACCOUNT.external_account, None, None)] = {"items": [], "nextPageToken": "a"}
    fake.event_pages[(ACCOUNT.external_account, "a", None)] = {"items": [], "nextPageToken": "b"}
    fake.event_pages[(ACCOUNT.external_account, "b", None)] = {"items": [], "nextPageToken": "a"}
    state = adapter.fetch_changes(ACCOUNT, state).next_cursor
    state = adapter.fetch_changes(ACCOUNT, state).next_cursor
    with pytest.raises(CalendarResyncRequiredError):
        adapter.fetch_changes(ACCOUNT, state)


@pytest.mark.parametrize("size", [0, -1, True, 251, "25"])
def test_page_size_bounded(size):
    with pytest.raises(ValueError):
        GoogleCalendarConnector(FakeCalendar(), page_size=size)


@pytest.mark.parametrize("bad", [None, "", "  "])
def test_explicit_identity_required_before_api(bad):
    fake = FakeCalendar()
    with pytest.raises(CalendarIdentityError):
        GoogleCalendarConnector(fake).fetch_changes(replace(ACCOUNT, external_account=bad), None)
    assert fake.calls == []


def test_registry_all_provider_and_owner_combinations(engine):
    c = config()
    c["source_accounts"] += [dict(c["source_accounts"][0], id="cal2", external_account="secondary@example.invalid"),
        dict(c["source_accounts"][0], id="spousecal", owner_id="spouse", external_account="spouse@example.invalid"),
        dict(c["source_accounts"][0], id="gmail", provider="gmail"), dict(c["source_accounts"][0], id="outlook", provider="outlook")]
    register(engine, c)
    assert len(list_accounts(engine, "home")) == 5
    assert calendar_identity(" Demo.Name+tag@Gmail.com ") == "demo.name+tag@gmail.com"


@pytest.mark.parametrize("reverse", [False, True])
def test_duplicate_guard_rolls_back_and_transactional_disabled_replacement(engine, reverse):
    c = config(); register(engine, c)
    before = {t.name: rows(engine, t) for t in (household, person, source_account, source_sync_state)}
    c["household"]["name"] = "Changed"
    replacement = dict(c["source_accounts"][0], id="replacement", external_account=" DEMO@EXAMPLE.INVALID ")
    c["source_accounts"].append(replacement)
    with pytest.raises(ValueError, match="Duplicate active"):
        register(engine, c)
    assert {t.name: rows(engine, t) for t in (household, person, source_account, source_sync_state)} == before
    c["source_accounts"][0]["enabled"] = False
    if reverse:
        c["source_accounts"].reverse()
    register(engine, c); register(engine, c)
    assert {a.id: a.enabled for a in list_accounts(engine, "home")} == {"cal": False, "replacement": True}


def test_direct_database_duplicate_fails_closed_before_client_access(engine):
    c = config(); c["source_accounts"].append(dict(c["source_accounts"][0], id="other", external_account="other@example.invalid"))
    register(engine, c)
    with engine.begin() as connection:
        connection.execute(update(source_account).where(source_account.c.id == "other").values(external_account=" DEMO@EXAMPLE.INVALID "))
    with engine.connect() as connection, pytest.raises(ValueError, match="Duplicate active"):
        get_account(connection, "home", "cal")
    fake = FakeCalendar()
    with pytest.raises(IngestionError):
        ingest(engine, "home", "cal", GoogleCalendarConnector(fake))
    assert fake.calls == []


def test_duplicate_json_fields_rejected():
    fake = FakeCalendar(); adapter = GoogleCalendarConnector(fake)
    state = adapter.fetch_changes(ACCOUNT, None).next_cursor
    state = state.replace('"account": "cal"', '"account": "other", "account": "cal"')
    fake.calls.clear()
    with pytest.raises(CalendarResyncRequiredError):
        adapter.fetch_changes(ACCOUNT, state)
    assert fake.calls == []


def test_reactivated_calendar_resumes_its_own_stream(engine):
    register(engine, config()); fake = FakeCalendar(); adapter = GoogleCalendarConnector(fake)
    fake.discovery[(None, None)]["items"].append(calendar("shared"))
    fake.event_pages[("shared", None, None)] = {"items": [event()], "nextSyncToken": "shared-sync"}
    ingest(engine, "home", "cal", adapter)
    fake.discovery[(None, "list-sync")] = {"items": [calendar("shared", selected=False)], "nextSyncToken": "list-sync"}
    ingest(engine, "home", "cal", adapter)
    assert not json.loads(saved(engine))["calendars"]["shared"]["active"]
    fake.discovery[(None, "list-sync")] = {"items": [calendar("shared")], "nextSyncToken": "list-sync"}
    fake.event_pages[("shared", None, "shared-sync")] = {"items": [event()], "nextSyncToken": "shared-sync"}
    assert ingest(engine, "home", "cal", adapter).unchanged == 2
    assert ("event", "shared", None, "shared-sync", 25) in fake.calls
    assert len(rows(engine, raw_source_record)) == 2


def test_event_recovery_from_completed_queue_runs_only_target(engine):
    register(engine, config()); fake = FakeCalendar(); adapter = GoogleCalendarConnector(fake)
    ingest(engine, "home", "cal", adapter)
    before = json.loads(saved(engine))["list"]
    recover_stream(engine, "home", "cal", calendar_id=ACCOUNT.external_account)
    fake.calls.clear()
    assert ingest(engine, "home", "cal", adapter).unchanged == 1
    # Identity discovery still runs, but persisted discovery is not reset or re-synced.
    assert json.loads(saved(engine))["list"] == before
    assert all(call[2] is None for call in fake.calls if call[0] == "list")
    assert len(rows(engine, raw_source_record)) == 1


def test_unknown_stream_recovery_keeps_database_unchanged(engine):
    register(engine, config()); adapter = GoogleCalendarConnector(FakeCalendar())
    ingest(engine, "home", "cal", adapter)
    before = rows(engine, source_sync_state)
    with pytest.raises(CalendarPolicyError):
        recover_stream(engine, "home", "cal", calendar_id="unregistered-stream")
    assert rows(engine, source_sync_state) == before


def test_calendar_owner_immutability_retains_history(engine):
    c = config(); register(engine, c)
    ingest(engine, "home", "cal", GoogleCalendarConnector(FakeCalendar()))
    before = {t.name: rows(engine, t) for t in (source_account, source_record, raw_source_record, source_sync_state)}
    c["source_accounts"][0]["owner_id"] = "spouse"
    with pytest.raises(ValueError, match="Explicit account owner is immutable"):
        register(engine, c)
    assert {t.name: rows(engine, t) for t in (source_account, source_record, raw_source_record, source_sync_state)} == before


@pytest.mark.parametrize("bad_event", [event(status="invalid"), event(sequence=True),
    event(start={"dateTime": "2026-10-05T10:00:00"}), event(start={"date": "not-a-date"}),
    event(start={"date": "2026-10-05", "dateTime": "2026-10-05T10:00:00Z"}),
    event(attendees="invalid"), event(recurrence=[1]), event(guestsCanModify="true")])
def test_malformed_event_page_rolls_back(engine, bad_event):
    register(engine, config()); fake = FakeCalendar(); adapter = GoogleCalendarConnector(fake)
    with pytest.raises(IngestionError, match="Page limit"):
        ingest(engine, "home", "cal", adapter, max_pages=1)
    before = rows(engine, source_sync_state)
    fake.event_pages[(ACCOUNT.external_account, None, None)]["items"] = [event(), bad_event]
    with pytest.raises(CalendarAPIError):
        ingest(engine, "home", "cal", adapter)
    assert rows(engine, source_sync_state) == before
    assert rows(engine, raw_source_record) == []


def test_same_calendar_identity_in_different_households_allowed(engine):
    c = config(); register(engine, c)
    other = {"household": {"id": "other", "name": "Other synthetic"}, "source_accounts": [
        {"id": "othercal", "provider": "google_calendar", "owner_type": "household", "owner_id": "other",
         "external_account": ACCOUNT.external_account}]}
    register(engine, other)
    assert len(list_accounts(engine, "home")) == 1
    assert len(list_accounts(engine, "other")) == 1


def test_idle_unfinished_stream_rejected():
    fake = FakeCalendar(); adapter = GoogleCalendarConnector(fake)
    state = adapter.fetch_changes(ACCOUNT, None).next_cursor
    state = json.loads(adapter.fetch_changes(ACCOUNT, state).next_cursor)
    state["calendars"][ACCOUNT.external_account]["events"]["sync"] = None
    with pytest.raises(CalendarResyncRequiredError):
        adapter.fetch_changes(ACCOUNT, json.dumps(state))


@pytest.mark.parametrize("role,readable", [
    ("reader", True), ("writerWithoutPrivateAccess", True),
    ("writer", True), ("owner", True), ("freeBusyReader", False),
])
@pytest.mark.parametrize("explicit_include", [False, True])
def test_readable_roles_default_and_explicit_inclusion(role, readable, explicit_include):
    from family_os.google_calendar import calendar_metadata
    item = calendar("shared", accessRole=role, hidden=explicit_include, selected=not explicit_include)
    meta = calendar_metadata(item)
    assert meta["accessRole"] == role
    policy = CalendarPolicy(include=["shared"] if explicit_include else [])
    assert policy.selected("shared", meta) is readable


@pytest.mark.parametrize("prior_visible_snapshot", [False, True])
def test_redacted_private_event_persists_without_filling_omitted_fields(engine, prior_visible_snapshot):
    register(engine, config())
    fake = FakeCalendar()
    cid = "shared"
    limited_role = "writerWithoutPrivateAccess"
    fake.discovery[(None, None)]["items"].append(calendar(cid,
        accessRole="writer" if prior_visible_snapshot else limited_role))
    redacted = {"id": "private-event", "status": "confirmed", "visibility": "private",
        "start": {"dateTime": "2026-10-05T10:00:00Z"},
        "end": {"dateTime": "2026-10-05T11:00:00Z"}}
    expected = {"calendar_id": cid, "event_id": redacted["id"],
        **{key: value for key, value in redacted.items() if key != "id"}}
    adapter = GoogleCalendarConnector(fake)
    minimized = minimize_event(cid, redacted)
    assert minimized == expected
    normalized = adapter.normalize(SimpleNamespace(payload=minimized,
        provider_object_id=object_identity(cid, redacted["id"])))
    assert normalized.metadata == expected
    assert normalized.subject is None and normalized.sender is None and normalized.recipients == ()
    fake.event_pages[(cid, None, None)] = {"items": [
        event(redacted["id"], location="Previously visible synthetic location", creator={"email": "creator@example.invalid"})
        if prior_visible_snapshot else redacted], "nextSyncToken": "shared-sync"}
    ingest(engine, "home", "cal", adapter)
    if prior_visible_snapshot:
        fake.discovery[(None, "list-sync")] = {"items": [calendar(cid, accessRole=limited_role)], "nextSyncToken": "list-sync"}
    fake.event_pages[(cid, None, "shared-sync")] = {"items": [redacted], "nextSyncToken": "shared-sync"}
    result = ingest(engine, "home", "cal", adapter)
    assert result.updated == int(prior_visible_snapshot)
    state = json.loads(saved(engine))["calendars"][cid]
    assert state["active"] is True and state["meta"]["accessRole"] == limited_role
    object_id = object_identity(cid, redacted["id"])
    current = next(row for row in rows(engine, source_record) if row["provider_object_id"] == object_id)
    assert current["raw_metadata"] == expected
    assert current["subject"] is None and current["sender"] is None and current["recipients"] == []
    assert current["content_hash"] is None
    snapshots = [row for row in rows(engine, raw_source_record) if row["provider_object_id"] == object_id]
    assert len(snapshots) == (2 if prior_visible_snapshot else 1)
    assert next(row for row in snapshots if row["id"] == current["raw_record_id"])["payload"] == expected
    for field in ("summary", "location", "organizer", "creator", "attendees", "iCalUID", "created", "updated"):
        assert field not in current["raw_metadata"]
    if prior_visible_snapshot:
        assert any(row["payload"].get("location") == "Previously visible synthetic location" for row in snapshots)
    # Persisted limited-role metadata also survives strict cursor validation on replay.
    assert ingest(engine, "home", "cal", adapter).updated == 0
