"""Metadata-only Drive adapter: start token → baseline → catch-up → incremental."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Protocol

from .domain import ChangeBatch, NormalizedRecord, RawRecord
from .gmail_privacy import private_transport
from .google_drive_identity import drive_identity, require_drive_account
from .google_drive_errors import (DriveError, DriveAPIError, DriveAuthError, DriveIdentityError,
    DrivePolicyError, DriveResponseError, DriveResyncRequiredError, SharedDriveUnavailableError)

BASE = "https://www.googleapis.com/drive/v3"
ABOUT_FIELDS = "user(permissionId,emailAddress,me)"
FILE_FIELDS = ("id,name,mimeType,createdTime,modifiedTime,modifiedByMeTime,viewedByMeTime,trashed,"
    "explicitlyTrashed,starred,parents,driveId,ownedByMe,shared,sharedWithMeTime,originalFilename,"
    "fileExtension,fullFileExtension,size,version,md5Checksum,sha1Checksum,sha256Checksum,headRevisionId,"
    "shortcutDetails(targetId,targetMimeType),owners(permissionId,emailAddress,displayName,me),capabilities(canDownload)")
FILES_FIELDS = "nextPageToken,incompleteSearch,files(" + FILE_FIELDS + ")"
CHANGES_FIELDS = "nextPageToken,newStartPageToken,changes(changeType,fileId,removed,driveId,file(" + FILE_FIELDS + "))"


def identifier(value):
    if not isinstance(value, str) or not value or value in {".", ".."} or len(value) > 4096 or any(c.isspace() or ord(c) < 32 for c in value):
        raise ValueError("Invalid Drive identifier")
    return value


def opaque(value):
    if not isinstance(value, str) or not value or len(value) > 65536:
        raise ValueError("Invalid Drive continuation")
    return value


def binding_fingerprint(permission_id):
    return sha256(json.dumps(["drive-permission/v1", identifier(permission_id)], separators=(",", ":")).encode()).hexdigest()


def about_identity(value):
    try:
        user = value["user"]
        if user["me"] is not True:
            raise ValueError()
        email = identifier(user["emailAddress"])
        drive_identity(email)
        return email, identifier(user["permissionId"])
    except Exception:
        raise DriveIdentityError() from None


class DriveClient(Protocol):
    bound_permission_id: str
    def about(self) -> dict: ...
    def drives(self, page_token, page_size) -> dict: ...
    def start_token(self, drive_id) -> dict: ...
    def files(self, drive_id, page_token, page_size) -> dict: ...
    def changes(self, drive_id, page_token, page_size) -> dict: ...


class DriveHTTPClient:
    """Fixed metadata GET operations only; no file-get, media, export, or Workspace API."""
    def __init__(self, session, bound_permission_id=None):
        self.session, self.bound_permission_id = session, bound_permission_id

    @private_transport
    def _get(self, path, params, stream=None, shared=False):
        try:
            response = self.session.get(BASE + path, params=params, timeout=30, allow_redirects=False)
            status = response.status_code
            if status == 401:
                raise DriveAuthError()
            if shared and status in {403, 404}:
                raise SharedDriveUnavailableError()
            if status == 403:
                raise DrivePolicyError()
            if status == 410 and stream is not None:
                raise DriveResyncRequiredError(stream)
            if status == 400 and stream is not None:
                # Only recognize the pageToken-specific invalid-token envelope;
                # no error messages/response bodies escape this boundary.
                try:
                    errors = response.json()["error"]["errors"]
                    invalid = any(item.get("reason") == "invalidPageToken" or
                        (item.get("reason") == "invalid" and item.get("location") == "pageToken") for item in errors)
                except Exception:
                    invalid = False
                if invalid:
                    raise DriveResyncRequiredError(stream)
            if status != 200:
                raise DriveAPIError(status)
            value = response.json()
            if not isinstance(value, dict):
                raise DriveResponseError()
            return value
        except DriveError:
            raise
        except Exception:
            raise DriveAPIError() from None

    def about(self):
        return self._get("/about", {"fields": ABOUT_FIELDS})

    def drives(self, page_token, page_size):
        params = {"pageSize": min(page_size, 100), "fields": "nextPageToken,drives(id)", "useDomainAdminAccess": False}
        if page_token is not None:
            params["pageToken"] = opaque(page_token)
        return self._get("/drives", params)

    def start_token(self, drive_id):
        params = {"fields": "startPageToken", "supportsAllDrives": True}
        if drive_id is not None:
            params["driveId"] = identifier(drive_id)
        return self._get("/changes/startPageToken", params, shared=drive_id is not None)

    def files(self, drive_id, page_token, page_size):
        params = {"spaces": "drive", "corpora": "user" if drive_id is None else "drive",
            "includeItemsFromAllDrives": drive_id is not None, "supportsAllDrives": True,
            "fields": FILES_FIELDS, "pageSize": page_size}
        if drive_id is not None:
            params["driveId"] = identifier(drive_id)
        if page_token is not None:
            params["pageToken"] = opaque(page_token)
        return self._get("/files", params, stream_key(drive_id), shared=drive_id is not None)

    def changes(self, drive_id, page_token, page_size):
        params = {"spaces": "drive", "includeRemoved": True, "includeCorpusRemovals": True,
            "restrictToMyDrive": False, "includeItemsFromAllDrives": drive_id is not None,
            "supportsAllDrives": True, "fields": CHANGES_FIELDS, "pageSize": page_size,
            "pageToken": opaque(page_token)}
        if drive_id is not None:
            params["driveId"] = identifier(drive_id)
        return self._get("/changes", params, stream_key(drive_id), shared=drive_id is not None)


def stream_key(drive_id):
    return "user" if drive_id is None else "drive:" + identifier(drive_id)


class DrivePolicy:
    def __init__(self, include_shared=()):
        try:
            self.include_shared = tuple(sorted({identifier(item) for item in include_shared}))
        except Exception:
            raise DrivePolicyError() from None
        self.fingerprint = sha256(json.dumps({"v": 1, "include_shared": self.include_shared}, sort_keys=True).encode()).hexdigest()


def timestamp(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Drive timestamp needs timezone")
    return parsed.astimezone(timezone.utc)


def minimize_file(file):
    result = {"file_id": identifier(file["id"])}
    strings = ("name", "mimeType", "createdTime", "modifiedTime", "modifiedByMeTime", "viewedByMeTime",
        "driveId", "sharedWithMeTime", "originalFilename", "fileExtension", "fullFileExtension",
        "size", "version", "md5Checksum", "sha1Checksum", "sha256Checksum", "headRevisionId")
    for key in strings:
        if key in file:
            value = file[key]
            if not isinstance(value, str):
                raise ValueError("Invalid Drive metadata")
            if key.endswith("Time"):
                timestamp(value)
            if key in {"size", "version"} and (not value.isascii() or not value.isdigit()):
                raise ValueError("Invalid Drive integer string")
            result[key] = value
    for key in ("trashed", "explicitlyTrashed", "starred", "ownedByMe", "shared"):
        if key in file:
            if type(file[key]) is not bool:
                raise ValueError("Invalid Drive flag")
            result[key] = file[key]
    if "parents" in file:
        if not isinstance(file["parents"], list):
            raise ValueError("Invalid Drive parents")
        result["parents"] = [identifier(value) for value in file["parents"]]
    if "shortcutDetails" in file:
        original = file["shortcutDetails"]
        if not isinstance(original, dict):
            raise ValueError("Invalid Drive shortcut")
        result["shortcutDetails"] = {key: identifier(original[key]) for key in ("targetId", "targetMimeType") if key in original}
    if "owners" in file:
        if not isinstance(file["owners"], list):
            raise ValueError("Invalid Drive owners")
        owners = []
        for original in file["owners"]:
            if not isinstance(original, dict):
                raise ValueError("Invalid Drive owner")
            owner = {}
            for key in ("permissionId", "emailAddress", "displayName"):
                if key in original:
                    if not isinstance(original[key], str):
                        raise ValueError("Invalid Drive owner")
                    owner[key] = original[key]
            if "me" in original:
                if type(original["me"]) is not bool:
                    raise ValueError("Invalid Drive owner")
                owner["me"] = original["me"]
            owners.append(owner)
        result["owners"] = owners
    if "capabilities" in file:
        original = file["capabilities"]
        if not isinstance(original, dict):
            raise ValueError("Invalid Drive capability")
        result["capabilities"] = {}
        if "canDownload" in original:
            if type(original["canDownload"]) is not bool:
                raise ValueError("Invalid Drive capability")
            result["capabilities"]["canDownload"] = original["canDownload"]
    return result


def routing(drive_id):
    return {"kind": "personal"} if drive_id is None else {"kind": "shared_drive", "drive_id": drive_id}


def fresh_stream(drive_id, active=True):
    return {"drive_id": drive_id, "active": active, "stage": "start", "start": None,
        "baseline_page": None, "change_page": None, "steady": None, "baseline_trail": [], "change_trail": []}


def append_page(trail, page, stream):
    try:
        opaque(page)
        if page in trail or len(trail) >= 10000:
            raise ValueError()
        trail.append(page)
    except Exception:
        raise DriveResyncRequiredError(stream) from None


def decode_cursor(cursor):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate Drive cursor key")
            result[key] = value
        return result
    return json.loads(cursor, object_pairs_hook=unique)


class GoogleDriveConnector:
    provider = "google_drive"

    def __init__(self, client: DriveClient, policy=None, page_size=25):
        if type(page_size) is not int or not 1 <= page_size <= 1000:
            raise ValueError("Drive page_size must be between 1 and 1000")
        self.client, self.policy, self.page_size = client, policy or DrivePolicy(), page_size

    def verify_account(self, account):
        expected = require_drive_account(account)
        try:
            bound = identifier(self.client.bound_permission_id)
            email, permission = about_identity(self.client.about())
            if drive_identity(email) != expected or permission != bound:
                raise DriveIdentityError()
            return email, binding_fingerprint(bound)
        except DriveError:
            raise
        except Exception:
            raise DriveIdentityError() from None

    def _state(self, account, cursor, fingerprint):
        bound = {"v": 1, "household": account.household_id, "account": account.id,
            "identity": require_drive_account(account), "binding": fingerprint, "policy": self.policy.fingerprint}
        if cursor is None:
            streams = {"user": fresh_stream(None)}
            streams.update({stream_key(did): fresh_stream(did) for did in self.policy.include_shared})
            return {**bound, "phase": "discover" if self.policy.include_shared else "sync",
                "discovery": {"page": None, "trail": [], "found": []}, "streams": streams, "pending": list(streams)}
        try:
            state = decode_cursor(cursor)
            if not isinstance(state, dict) or set(state) != {*bound, "phase", "discovery", "streams", "pending"}:
                raise ValueError()
            if type(state["v"]) is not int or any(state[key] != value for key, value in bound.items()):
                raise ValueError()
            if state["phase"] not in {"discover", "sync", "idle"} or not isinstance(state["streams"], dict):
                raise ValueError()
            discovery = state["discovery"]
            if not isinstance(discovery, dict) or set(discovery) != {"page", "trail", "found"}:
                raise ValueError()
            def trail(value, page):
                if not isinstance(value, list) or len(value) > 10000 or len(value) != len(set(value)):
                    raise ValueError()
                for item in value:
                    opaque(item)
                if value and value[-1] != page:
                    raise ValueError()
                if page is None and value:
                    raise ValueError()
            if discovery["page"] is not None:
                opaque(discovery["page"])
            trail(discovery["trail"], discovery["page"])
            if (discovery["page"] is not None) != bool(discovery["trail"]):
                raise ValueError()
            if not isinstance(discovery["found"], list) or len(discovery["found"]) != len(set(discovery["found"])) or not set(discovery["found"]) <= set(self.policy.include_shared):
                raise ValueError()
            if discovery["page"] is None and discovery["found"]:
                raise ValueError()
            if state["phase"] != "discover" and discovery != {"page": None, "trail": [], "found": []}:
                raise ValueError()
            if state["phase"] == "discover" and not self.policy.include_shared:
                raise ValueError()
            expected_active = {"user", *(stream_key(did) for did in self.policy.include_shared)}
            if not expected_active <= set(state["streams"]):
                raise ValueError()
            for key, value in state["streams"].items():
                if not isinstance(value, dict) or set(value) != set(fresh_stream(None)) or type(value["active"]) is not bool:
                    raise ValueError()
                if key != stream_key(value["drive_id"]) or value["active"] != (key in expected_active):
                    raise ValueError()
                stage = value["stage"]
                if stage not in {"start", "baseline", "catchup", "incremental"}:
                    raise ValueError()
                for name in ("start", "baseline_page", "change_page", "steady"):
                    if value[name] is not None:
                        opaque(value[name])
                trail(value["baseline_trail"], value["baseline_page"])
                trail(value["change_trail"], value["change_page"])
                if (value["baseline_page"] is not None) != bool(value["baseline_trail"]):
                    raise ValueError()
                if stage == "start" and value != fresh_stream(value["drive_id"], value["active"]):
                    raise ValueError()
                if stage in {"baseline", "catchup"} and (value["start"] is None or value["steady"] is not None or value["change_page"] is None):
                    raise ValueError()
                if stage == "baseline" and (value["change_page"] != value["start"] or value["change_trail"]):
                    raise ValueError()
                if stage != "baseline" and (value["baseline_page"] is not None or value["baseline_trail"]):
                    raise ValueError()
                if stage == "catchup" and ((not value["change_trail"] and value["change_page"] != value["start"]) or
                    (value["change_trail"] and value["change_trail"][0] != value["start"])):
                    raise ValueError()
                if stage == "incremental" and value["change_trail"] and value["change_trail"][0] != value["steady"]:
                    raise ValueError()
                if stage == "incremental" and (value["steady"] is None or value["start"] is not None or bool(value["change_page"]) != bool(value["change_trail"])):
                    raise ValueError()
            pending = state["pending"]
            if not isinstance(pending, list) or len(pending) != len(set(pending)) or not set(pending) <= expected_active:
                raise ValueError()
            if state["phase"] == "sync" and not pending or state["phase"] == "idle" and pending:
                raise ValueError()
            if any(v["active"] and (v["stage"] != "incremental" or v["change_page"] is not None) and key not in pending for key, v in state["streams"].items()):
                raise ValueError()
            return state
        except Exception:
            raise DriveResyncRequiredError() from None

    def fetch_changes(self, account, cursor):
        try:
            # Check structure/binding against the securely stored identity before private I/O.
            fingerprint = binding_fingerprint(self.client.bound_permission_id)
            state = self._state(account, cursor, fingerprint)
            _, verified = self.verify_account(account)
            if verified != fingerprint:
                raise DriveIdentityError()
            if state["phase"] == "idle":
                state["pending"] = [key for key, value in state["streams"].items() if value["active"]]
                state["phase"] = "discover" if self.policy.include_shared else "sync"
            if state["phase"] == "discover":
                d = state["discovery"]
                response = self.client.drives(d["page"], self.page_size)
                values = response.get("drives", [])
                if not isinstance(values, list):
                    raise ValueError()
                for drive in values:
                    did = identifier(drive["id"])
                    if did in self.policy.include_shared and did not in d["found"]:
                        d["found"].append(did)
                page = response.get("nextPageToken")
                if page is not None:
                    append_page(d["trail"], page, None)
                    d["page"] = page
                else:
                    if set(d["found"]) != set(self.policy.include_shared):
                        raise SharedDriveUnavailableError()
                    state["discovery"] = {"page": None, "trail": [], "found": []}
                    state["phase"] = "sync" if state["pending"] else "idle"
                return ChangeBatch((), json.dumps(state, sort_keys=True), state["phase"] != "idle")
            key = state["pending"][0]
            stream = state["streams"][key]
            did, stage = stream["drive_id"], stream["stage"]
            records = []
            if stage == "start":
                token = opaque(self.client.start_token(did)["startPageToken"])
                stream.update(stage="baseline", start=token, change_page=token)
            elif stage == "baseline":
                response = self.client.files(did, stream["baseline_page"], self.page_size)
                if response.get("incompleteSearch", False) is not False:
                    raise DriveResponseError()
                files = response.get("files", [])
                if not isinstance(files, list):
                    raise ValueError()
                for file in files:
                    # User logs/listings may expose Shared Drive files despite request
                    # flags. Only their exact-ID opt-in stream may observe them.
                    if did is None and file.get("driveId"):
                        continue
                    snapshot = {**minimize_file(file), "removed": False, "stream": routing(did)}
                    records.append(RawRecord(snapshot["file_id"], snapshot))
                page = response.get("nextPageToken")
                if page is not None:
                    append_page(stream["baseline_trail"], page, key)
                    stream["baseline_page"] = page
                else:
                    stream.update(stage="catchup", baseline_page=None, baseline_trail=[])
            else:
                current = stream["change_page"] or stream["steady"]
                response = self.client.changes(did, current, self.page_size)
                values = response.get("changes", [])
                if not isinstance(values, list):
                    raise ValueError()
                for change in values:
                    removed = change.get("removed", False)
                    if type(removed) is not bool:
                        raise ValueError()
                    kind = change.get("changeType", "file")
                    if kind == "drive":
                        changed_drive = identifier(change["driveId"])
                        if did is not None and changed_drive != did:
                            raise ValueError()
                        if removed and changed_drive in self.policy.include_shared:
                            raise SharedDriveUnavailableError()
                        continue  # Drive resources are routing, not file source records.
                    if kind != "file":
                        raise ValueError()
                    if did is None and (change.get("driveId") or
                        isinstance(change.get("file"), dict) and change["file"].get("driveId")):
                        continue  # Includes sparse removals; never fetch to classify.
                    fid = identifier(change["fileId"])
                    snapshot = {"file_id": fid, "removed": removed, "stream": routing(did)}
                    if "driveId" in change:
                        snapshot["driveId"] = identifier(change["driveId"])
                    if "file" in change:
                        minimized = minimize_file(change["file"])
                        if minimized["file_id"] != fid:
                            raise ValueError()
                        if "driveId" in change:
                            snapshot["change_drive_id"] = identifier(change["driveId"])
                        snapshot.update(minimized)
                    elif not removed:
                        raise ValueError()
                    records.append(RawRecord(fid, snapshot))
                page, new = response.get("nextPageToken"), response.get("newStartPageToken")
                if (page is None) == (new is None):
                    raise DriveResyncRequiredError(key)
                if page is not None:
                    if not stream["change_trail"]:
                        stream["change_trail"].append(current)
                    append_page(stream["change_trail"], page, key)
                    stream["change_page"] = page
                else:
                    stream.update(stage="incremental", start=None, change_page=None,
                        steady=opaque(new), change_trail=[])
                    state["pending"].pop(0)
                    if not state["pending"]:
                        state["phase"] = "idle"
            return ChangeBatch(tuple(records), json.dumps(state, sort_keys=True), state["phase"] != "idle")
        except DriveError:
            raise
        except Exception:
            raise DriveResponseError() from None

    def normalize(self, record):
        data = record.payload
        time = data.get("modifiedTime") or data.get("createdTime")
        return NormalizedRecord(record.provider_object_id, "document",
            occurred_at=timestamp(time) if time else None, subject=data.get("name"), metadata=data)

    def reset_cursor(self, account, cursor, fingerprint, drive_id=None):
        state = self._state(account, cursor, fingerprint)
        key = stream_key(drive_id)
        if key not in state["streams"]:
            raise DrivePolicyError()
        active = state["streams"][key]["active"]
        state["streams"][key] = fresh_stream(drive_id, active)
        if active and key not in state["pending"]:
            state["pending"].append(key)
        if state["phase"] != "discover":
            state["phase"] = "sync" if state["pending"] else "idle"
        return json.dumps(state, sort_keys=True)

    def migrate_cursor(self, account, cursor, fingerprint, new_policy):
        state = self._state(account, cursor, fingerprint)
        active_keys = {"user", *(stream_key(did) for did in new_policy.include_shared)}
        for key, value in state["streams"].items():
            value["active"] = key in active_keys
        pending = [key for key in state["pending"] if key in active_keys]
        for did in new_policy.include_shared:
            key = stream_key(did)
            if key not in state["streams"]:
                state["streams"][key] = fresh_stream(did)
            else:
                state["streams"][key]["active"] = True
            if key not in pending:
                pending.append(key)
        state.update(policy=new_policy.fingerprint, pending=pending,
            phase="discover" if new_policy.include_shared else "sync" if pending else "idle",
            discovery={"page": None, "trail": [], "found": []})
        GoogleDriveConnector(None, new_policy)._state(account, json.dumps(state), fingerprint)
        return json.dumps(state, sort_keys=True)


def transform_state(engine, household_id, account_id, fingerprint, policy=None, drive_id=None, new_policy=None):
    """Local explicit recovery/policy transformation with CAS; no provider I/O."""
    from sqlalchemy import select, update
    from .registry import get_account
    from .schema import source_sync_state
    from .errors import ConcurrentSyncError
    with engine.begin() as connection:
        account = get_account(connection, household_id, account_id)
        require_drive_account(account)
        row = connection.execute(select(source_sync_state).where(source_sync_state.c.source_account_id == account_id)).mappings().one()
        adapter = GoogleDriveConnector(None, policy)
        if row["cursor"] is None:
            raise DrivePolicyError()  # There is no saved stream to reset/migrate yet.
        if new_policy is not None:
            cursor = adapter.migrate_cursor(account, row["cursor"], fingerprint, new_policy)
        else:
            cursor = adapter.reset_cursor(account, row["cursor"], fingerprint, drive_id)
        changed = connection.execute(update(source_sync_state).where(source_sync_state.c.source_account_id == account_id,
            source_sync_state.c.version == row["version"]).values(cursor=cursor, version=row["version"] + 1,
                updated_at=datetime.now(timezone.utc)))
        if changed.rowcount != 1 or get_account(connection, household_id, account_id) != account:
            raise ConcurrentSyncError("Account changed; retry recovery from its saved state")
