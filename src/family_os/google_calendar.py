"""Read-only CalendarList/event streams, with minimized recurring/cancelled snapshots."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Protocol
from urllib.parse import quote

from .domain import ChangeBatch, NormalizedRecord, RawRecord
from .gmail_privacy import private_transport
from .google_calendar_identity import calendar_identity, require_calendar_account
from .google_calendar_errors import (CalendarError, CalendarAPIError, CalendarAuthError,
    CalendarIdentityError, CalendarPolicyError, CalendarResyncRequiredError)

BASE = "https://www.googleapis.com/calendar/v3"
PERSON_FIELDS = "email,displayName,self"
ATTENDEE_FIELDS = PERSON_FIELDS + ",responseStatus,optional,resource"
TIME_FIELDS = "date,dateTime,timeZone"
EVENT_FIELDS = ("id,iCalUID,status,eventType,created,updated,start(" + TIME_FIELDS + "),end(" + TIME_FIELDS +
    "),endTimeUnspecified,recurrence,recurringEventId,originalStartTime(" + TIME_FIELDS +
    "),summary,location,transparency,visibility,organizer(" + PERSON_FIELDS + "),creator(" + PERSON_FIELDS +
    "),attendees(" + ATTENDEE_FIELDS + "),sequence,guestsCanModify,guestsCanInviteOthers,guestsCanSeeOtherGuests")
LIST_FIELDS = "nextPageToken,nextSyncToken,items(id,primary,hidden,selected,accessRole,deleted)"
EVENT_PROJECTION = "nextPageToken,nextSyncToken,items(" + EVENT_FIELDS + ")"


def identifier(value):
    if not isinstance(value, str) or not value or value in {".", ".."} or len(value) > 4096 or any(ord(c) < 32 for c in value):
        raise ValueError("Invalid Calendar identifier")
    return value


def token(value):
    if not isinstance(value, str) or not value or len(value) > 65536:
        raise ValueError("Invalid Calendar continuation state")
    return value


def object_identity(calendar_id, event_id):
    return "gcal:v1:" + json.dumps([identifier(calendar_id), identifier(event_id)], ensure_ascii=False, separators=(",", ":"))


class CalendarClient(Protocol):
    def calendar_list(self, page_token, sync_token, page_size) -> dict: ...
    def events(self, calendar_id, page_token, sync_token, page_size) -> dict: ...


class CalendarHTTPClient:
    def __init__(self, session):
        self.session = session

    @private_transport
    def _get(self, path, params, stream):
        try:
            response = self.session.get(BASE + path, params=params, timeout=30, allow_redirects=False)
            status = response.status_code
            if status == 401:
                raise CalendarAuthError()
            if status == 403:
                raise CalendarPolicyError()
            if status == 410:
                raise CalendarResyncRequiredError(stream)
            if status != 200:
                raise CalendarAPIError(status)
            result = response.json()
            if not isinstance(result, dict):
                raise CalendarAPIError()
            return result
        except CalendarError:
            raise
        except Exception:
            raise CalendarAPIError() from None

    def calendar_list(self, page_token=None, sync_token=None, page_size=25):
        params = {"maxResults": page_size, "showHidden": True, "showDeleted": True, "fields": LIST_FIELDS}
        if page_token is not None:
            params["pageToken"] = token(page_token)
        if sync_token is not None:
            params["syncToken"] = token(sync_token)
        return self._get("/users/me/calendarList", params, "calendar_list")

    def events(self, calendar_id, page_token=None, sync_token=None, page_size=25):
        params = {"maxResults": page_size, "singleEvents": False, "showDeleted": True, "fields": EVENT_PROJECTION}
        if page_token is not None:
            params["pageToken"] = token(page_token)
        if sync_token is not None:
            params["syncToken"] = token(sync_token)
        return self._get("/calendars/" + quote(identifier(calendar_id), safe="") + "/events", params, calendar_id)


class CalendarPolicy:
    def __init__(self, include=(), exclude=()):
        self.include = tuple(sorted({identifier(item) for item in include}))
        self.exclude = tuple(sorted({identifier(item) for item in exclude}))
        self.fingerprint = sha256(json.dumps({"v": 1, "include": self.include, "exclude": self.exclude}, sort_keys=True).encode()).hexdigest()

    def selected(self, cid, meta):
        if meta["primary"] and cid in self.exclude:
            # Primary inclusion and explicit exclusion cannot both be honored.
            raise CalendarPolicyError()
        if cid in self.exclude or meta["accessRole"] not in {"reader", "writerWithoutPrivateAccess", "writer", "owner"}:
            return False
        return meta["primary"] or cid in self.include or (not meta["hidden"] and meta["selected"])


def calendar_metadata(item):
    result = {key: item.get(key, False) for key in ("primary", "hidden", "selected")}
    if any(type(value) is not bool for value in result.values()):
        raise ValueError("Invalid Calendar flags")
    result["accessRole"] = item.get("accessRole", "none")
    if result["accessRole"] not in {"none", "freeBusyReader", "reader", "writerWithoutPrivateAccess", "writer", "owner"}:
        raise ValueError("Invalid Calendar access")
    return result


def timestamp(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Calendar timestamp must include timezone")
    return parsed.astimezone(timezone.utc)


def minimize_event(calendar_id, event):
    result = {"calendar_id": identifier(calendar_id), "event_id": identifier(event["id"])}
    strings = ("iCalUID", "status", "eventType", "created", "updated", "recurringEventId", "summary", "location", "transparency", "visibility")
    for key in strings:
        if key in event:
            if not isinstance(event[key], str):
                raise ValueError("Invalid Calendar metadata")
            if key in {"created", "updated"}:
                timestamp(event[key])
            result[key] = event[key]
    if result.get("status") not in {"confirmed", "tentative", "cancelled"}:
        raise ValueError("Invalid Calendar event status")
    for key in ("endTimeUnspecified", "guestsCanModify", "guestsCanInviteOthers", "guestsCanSeeOtherGuests"):
        if key in event:
            if type(event[key]) is not bool:
                raise ValueError("Invalid Calendar flag")
            result[key] = event[key]
    if "sequence" in event:
        if type(event["sequence"]) is not int or event["sequence"] < 0:
            raise ValueError("Invalid Calendar sequence")
        result["sequence"] = event["sequence"]
    if "recurrence" in event:
        recurrence = event["recurrence"]
        if not isinstance(recurrence, list) or not all(isinstance(item, str) for item in recurrence):
            raise ValueError("Invalid Calendar recurrence")
        result["recurrence"] = list(recurrence)
    for key in ("start", "end", "originalStartTime"):
        if key in event:
            original = event[key]
            if not isinstance(original, dict):
                raise ValueError("Invalid Calendar time")
            value = {field: original[field] for field in ("date", "dateTime", "timeZone") if field in original}
            if not all(isinstance(item, str) for item in value.values()) or ("date" in value) == ("dateTime" in value):
                raise ValueError("Invalid Calendar time")
            if "date" in value:
                from datetime import date
                date.fromisoformat(value["date"])
            if "dateTime" in value:
                # Calendar allows offset-free dateTime with an explicit IANA timeZone.
                parsed = datetime.fromisoformat(value["dateTime"].replace("Z", "+00:00"))
                if parsed.tzinfo is None and not value.get("timeZone"):
                    raise ValueError("Missing Calendar timezone")
            if "timeZone" in value:
                from zoneinfo import ZoneInfo
                ZoneInfo(value["timeZone"])
            result[key] = value
    def person(item, attendee=False):
        if not isinstance(item, dict):
            raise ValueError("Invalid Calendar participant")
        value = {}
        for field in ("email", "displayName", "responseStatus") if attendee else ("email", "displayName"):
            if field in item:
                if not isinstance(item[field], str):
                    raise ValueError("Invalid Calendar participant")
                value[field] = item[field]
        for field in ("self", "optional", "resource") if attendee else ("self",):
            if field in item:
                if type(item[field]) is not bool:
                    raise ValueError("Invalid Calendar participant flag")
                value[field] = item[field]
        return value
    for key in ("organizer", "creator"):
        if key in event:
            result[key] = person(event[key])
    if "attendees" in event:
        if not isinstance(event["attendees"], list):
            raise ValueError("Invalid Calendar attendees")
        result["attendees"] = [person(item, True) for item in event["attendees"]]
    return result


def empty_stream():
    return {"page": None, "sync": None, "trail": []}


def advance(stream, response, name):
    page, sync = response.get("nextPageToken"), response.get("nextSyncToken")
    if (page is None) == (sync is None):
        raise CalendarResyncRequiredError(name)
    try:
        token(page if page is not None else sync)
    except ValueError:
        raise CalendarResyncRequiredError(name) from None
    if page is not None:
        token(page)
        if page == stream["page"] or page in stream["trail"] or len(stream["trail"]) >= 10000:
            raise CalendarResyncRequiredError(name)
        stream["trail"].append(page)
        stream["page"] = page
        return True
    stream.update(page=None, sync=token(sync), trail=[])
    return False


class GoogleCalendarConnector:
    provider = "google_calendar"

    def __init__(self, client: CalendarClient, policy=None, page_size=25):
        if type(page_size) is not int or not 1 <= page_size <= 250:
            raise ValueError("Calendar page_size must be between 1 and 250")
        self.client, self.policy, self.page_size = client, policy or CalendarPolicy(), page_size

    def primary_identity(self, account):
        require_calendar_account(account)
        page, seen, primaries = None, set(), []
        for _ in range(10000):
            response = self.client.calendar_list(page, None, self.page_size)
            items = response.get("items", [])
            if not isinstance(items, list):
                raise CalendarAPIError()
            for item in items:
                if item.get("primary") is True and not item.get("deleted", False):
                    primaries.append(identifier(item["id"]))
            page = response.get("nextPageToken")
            if page is None:
                if len(primaries) != 1:
                    raise CalendarIdentityError()
                return primaries[0]
            token(page)
            if page in seen:
                raise CalendarIdentityError()
            seen.add(page)
        raise CalendarIdentityError()

    def verify_account(self, account):
        expected = require_calendar_account(account)
        primary = self.primary_identity(account)
        if calendar_identity(primary) != expected:
            raise CalendarIdentityError()
        return primary

    def _state(self, account, cursor):
        bound = {"v": 1, "household": account.household_id, "account": account.id,
                 "identity": require_calendar_account(account), "policy": self.policy.fingerprint}
        if cursor is None:
            return {**bound, "phase": "list", "list": empty_stream(), "seen": [], "calendars": {}, "pending": []}
        try:
            def unique_object(pairs):
                value = {}
                for key, item in pairs:
                    if key in value:
                        raise ValueError("Duplicate cursor field")
                    value[key] = item
                return value
            state = json.loads(cursor, object_pairs_hook=unique_object)
            if not isinstance(state, dict) or set(state) != {*bound, "phase", "list", "seen", "calendars", "pending"}:
                raise ValueError()
            if type(state["v"]) is not int or any(state[key] != value for key, value in bound.items()):
                raise ValueError()
            if state["phase"] not in {"list", "events", "idle"} or not isinstance(state["calendars"], dict):
                raise ValueError()
            def check_stream(stream):
                if not isinstance(stream, dict) or set(stream) != {"page", "sync", "trail"}:
                    raise ValueError()
                for key in ("page", "sync"):
                    if stream[key] is not None:
                        token(stream[key])
                if not isinstance(stream["trail"], list) or len(stream["trail"]) > 10000 or len(set(stream["trail"])) != len(stream["trail"]):
                    raise ValueError()
                for value in stream["trail"]:
                    token(value)
                if bool(stream["trail"]) != (stream["page"] is not None) or (stream["trail"] and stream["trail"][-1] != stream["page"]):
                    raise ValueError()
            check_stream(state["list"])
            for cid, value in state["calendars"].items():
                identifier(cid)
                if not isinstance(value, dict) or set(value) != {"meta", "active", "events"} or type(value["active"]) is not bool:
                    raise ValueError()
                meta = value["meta"]
                if not isinstance(meta, dict) or set(meta) != {"primary", "hidden", "selected", "accessRole"} or calendar_metadata(meta) != meta:
                    raise ValueError()
                if meta["primary"] != (cid.strip().casefold() == bound["identity"]):
                    raise ValueError()
                if value["active"] and not self.policy.selected(cid, meta):
                    raise ValueError()
                check_stream(value["events"])
            for key in ("seen", "pending"):
                if not isinstance(state[key], list) or len(set(state[key])) != len(state[key]):
                    raise ValueError()
                if any(cid not in state["calendars"] for cid in state[key]):
                    raise ValueError()
            if any(not state["calendars"][cid]["active"] for cid in state["pending"]):
                raise ValueError()
            if state["phase"] in {"events", "idle"}:
                primaries = [value for value in state["calendars"].values() if value["meta"]["primary"]]
                if state["list"]["sync"] is None or len(primaries) != 1 or not primaries[0]["active"]:
                    raise ValueError()
            if state["seen"] and state["list"]["page"] is None:
                raise ValueError()
            if state["phase"] == "events":
                if not state["pending"] or state["list"]["page"] is not None or state["seen"]:
                    raise ValueError()
            elif state["pending"] or (state["phase"] == "idle" and (state["list"]["page"] is not None or state["seen"])):
                raise ValueError()
            if state["list"]["sync"] is not None and state["seen"]:
                raise ValueError()
            if state["phase"] == "idle" and any(v["active"] and (v["events"]["page"] is not None or v["events"]["sync"] is None) for v in state["calendars"].values()):
                raise ValueError()
            if state["phase"] == "events" and any(v["active"] and (v["events"]["page"] is not None or v["events"]["sync"] is None) and cid not in state["pending"] for cid, v in state["calendars"].items()):
                raise ValueError()
            return state
        except CalendarPolicyError:
            raise
        except Exception:
            raise CalendarResyncRequiredError() from None

    def fetch_changes(self, account, cursor):
        try:
            state = self._state(account, cursor)
            primary = self.verify_account(account)
            if state["phase"] == "idle":
                state["phase"] = "list"
            if state["phase"] == "list":
                stream = state["list"]
                full = stream["sync"] is None
                response = self.client.calendar_list(stream["page"], stream["sync"], self.page_size)
                items = response.get("items", [])
                if not isinstance(items, list):
                    raise ValueError()
                for item in items:
                    cid = identifier(item["id"])
                    deleted = item.get("deleted", False)
                    if type(deleted) is not bool:
                        raise ValueError()
                    if deleted:
                        if cid in state["calendars"]:
                            state["calendars"][cid]["active"] = False
                        continue
                    meta = calendar_metadata(item)
                    if meta["primary"] != (cid == primary):
                        raise CalendarIdentityError()
                    value = state["calendars"].setdefault(cid, {"meta": meta, "active": False, "events": empty_stream()})
                    value.update(meta=meta, active=self.policy.selected(cid, meta))
                    if full and cid not in state["seen"]:
                        state["seen"].append(cid)
                more = advance(stream, response, "calendar_list")
                if not more:
                    if full:
                        for cid, value in state["calendars"].items():
                            if cid not in state["seen"]:
                                value["active"] = False
                    if primary not in state["calendars"] or not state["calendars"][primary]["active"]:
                        raise CalendarIdentityError()
                    state["seen"] = []
                    state["pending"] = sorted(cid for cid, value in state["calendars"].items() if value["active"])
                    state["phase"] = "events"
                return ChangeBatch((), json.dumps(state, sort_keys=True), True)
            cid = state["pending"][0]
            stream = state["calendars"][cid]["events"]
            response = self.client.events(cid, stream["page"], stream["sync"], self.page_size)
            items = response.get("items", [])
            if not isinstance(items, list):
                raise ValueError()
            records = []
            for item in items:
                snapshot = minimize_event(cid, item)
                records.append(RawRecord(object_identity(cid, snapshot["event_id"]), snapshot))
            if not advance(stream, response, cid):
                state["pending"].pop(0)
            if not state["pending"]:
                state["phase"] = "idle"
            return ChangeBatch(tuple(records), json.dumps(state, sort_keys=True), bool(state["pending"]))
        except CalendarError:
            raise
        except Exception:
            raise CalendarAPIError() from None

    def reset_cursor(self, account, cursor, calendar_id=None):
        """Pure explicit recovery transformation; caller persists with compare-and-swap."""
        state = self._state(account, cursor)
        if calendar_id is None:
            state.update(phase="list", list=empty_stream(), seen=[], pending=[])
        else:
            if calendar_id not in state["calendars"]:
                raise CalendarPolicyError()
            state["calendars"][calendar_id]["events"] = empty_stream()
            # Keep in-progress discovery intact. Otherwise resume only unfinished
            # work and this stream; unrelated saved event tokens are untouched.
            if state["phase"] != "list":
                if state["calendars"][calendar_id]["active"] and calendar_id not in state["pending"]:
                    state["pending"].append(calendar_id)
                state["phase"] = "events" if state["pending"] else "idle"
        return json.dumps(state, sort_keys=True)

    def normalize(self, record):
        data = record.payload
        date = data.get("created") or data.get("updated")
        return NormalizedRecord(record.provider_object_id, "calendar_event",
            occurred_at=timestamp(date) if date else None, subject=data.get("summary"),
            sender=data.get("organizer", {}).get("email"),
            recipients=tuple(dict.fromkeys(item["email"] for item in data.get("attendees", []) if item.get("email"))),
            metadata=data)


def recover_stream(engine, household_id, account_id, policy=None, calendar_id=None):
    """Explicit local cursor reset; no OAuth, API calls, or history deletion."""
    from sqlalchemy import select, update
    from .registry import get_account
    from .schema import source_sync_state
    from .errors import ConcurrentSyncError
    with engine.begin() as connection:
        account = get_account(connection, household_id, account_id)
        require_calendar_account(account)
        row = connection.execute(select(source_sync_state).where(
            source_sync_state.c.source_account_id == account_id)).mappings().one()
        cursor = GoogleCalendarConnector(None, policy).reset_cursor(account, row["cursor"], calendar_id)
        changed = connection.execute(update(source_sync_state).where(
            source_sync_state.c.source_account_id == account_id,
            source_sync_state.c.version == row["version"]).values(
            cursor=cursor, version=row["version"] + 1, updated_at=datetime.now(timezone.utc)))
        if changed.rowcount != 1:
            raise ConcurrentSyncError("Account sync changed; retry recovery from its saved cursor")
        if get_account(connection, household_id, account_id) != account:
            raise ConcurrentSyncError("Account changed; retry recovery")
