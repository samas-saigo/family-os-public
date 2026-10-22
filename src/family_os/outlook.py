"""Read-basic Graph adapter; opaque per-folder delta streams and immutable IDs."""
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Protocol
from urllib.parse import quote, unquote, urlsplit, parse_qsl

from .domain import ChangeBatch, NormalizedRecord, RawRecord
from .gmail_privacy import private_transport
from .outlook_identity import require_outlook_account, outlook_identity
from .outlook_errors import (OutlookError, OutlookAPIError, OutlookAuthError,
                             OutlookPolicyError, OutlookResyncRequiredError, OutlookIdentityError)

GRAPH_BASE = "https://graph.microsoft.com/v1.0/me/mailFolders"
IMMUTABLE_PREFER = 'IdType="ImmutableId"'
MESSAGE_FIELDS = ("id", "internetMessageId", "conversationId", "parentFolderId",
    "receivedDateTime", "sentDateTime", "createdDateTime", "lastModifiedDateTime",
    "subject", "from", "sender", "toRecipients", "ccRecipients", "bccRecipients",
    "categories", "importance", "isRead", "hasAttachments")
FOLDER_FIELDS = "id,displayName,childFolderCount,isHidden"
DEFAULT_EXCLUDED = ("junkemail", "deleteditems", "drafts", "outbox", "sentitems",
                    "syncissues", "conflicts", "localfailures", "serverfailures")
WELL_KNOWN = frozenset((*DEFAULT_EXCLUDED, "inbox", "archive"))


def identifier(value):
    if not isinstance(value, str) or not value or value in {".", ".."} or len(value) > 4096 or any(ord(c) < 32 for c in value):
        raise ValueError("Invalid Outlook identity")
    return value


def folder_url(folder_id):
    return GRAPH_BASE + "/" + quote(identifier(folder_id), safe="")


def canonical_folder_path(path):
    # Graph can return equivalent slash or OData-key folder routing forms and
    # different percent encoding. Normalize only the folder route for comparison;
    # send the original URL and opaque query unchanged.
    path = re.sub(r"/mailFolders\('([^']+)'\)",
                  lambda match: "/mailFolders/" + quote(unquote(match[1]), safe=""), path)
    return re.sub(r"(/mailFolders/)([^/]+)",
                  lambda match: match[1] + quote(unquote(match[2]), safe=""), path)


def validate_link(url, folder_id=None, discovery_path=None, kind=None):
    """Strict public-cloud /me boundary, exact stream path, no redirects/extra fields.

    Tokens remain opaque. Only the routing/projection envelope is validated.
    """
    try:
        if not isinstance(url, str) or len(url) > 65536 or any(c.isspace() for c in url):
            raise ValueError()
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or parsed.netloc != "graph.microsoft.com"
            or parsed.fragment or parsed.username or parsed.password):
            raise ValueError()
        expected = urlsplit(discovery_path).path if discovery_path else urlsplit(folder_url(folder_id) + "/messages/delta").path
        # Equivalent Graph folder routing forms must still bind the exact folder,
        # /me account context, operation and API version.
        if canonical_folder_path(parsed.path) != canonical_folder_path(expected):
            raise ValueError()
        seen = set()
        allowed = {"$skiptoken", "$deltatoken", "$top", "$select"}
        if discovery_path:
            allowed |= {"$skip", "includeHiddenFolders"}
        for key, value in parse_qsl(parsed.query, keep_blank_values=True):
            if key in seen or key not in allowed or not value:
                raise ValueError()
            seen.add(key)
            if key == "$select":
                fields = set(value.split(","))
                safe = set(FOLDER_FIELDS.split(",")) if discovery_path else set(MESSAGE_FIELDS)
                if not fields <= safe:
                    raise ValueError()
        if not discovery_path:
            tokens = seen & {"$skiptoken", "$deltatoken"}
            if len(tokens) != 1 or (kind == "next" and "$skiptoken" not in tokens) or (kind == "delta" and "$deltatoken" not in tokens):
                raise ValueError()
        return url
    except Exception:
        raise OutlookResyncRequiredError(folder_id) from None


class OutlookClient(Protocol):
    def identity(self) -> tuple[str, str]: ...
    def discover_folders(self) -> tuple[list[dict], dict[str, str]]: ...
    def delta(self, folder_id: str, link: str | None, page_size: int) -> dict: ...
    def message(self, message_id: str) -> dict: ...


class GraphHTTPClient:
    def __init__(self, session):
        self.session = session

    def identity(self):
        return self.session.identity()

    @private_transport
    def _get(self, url, params=None, page_size=None):
        try:
            prefer = IMMUTABLE_PREFER
            if page_size is not None:
                prefer += f",odata.maxpagesize={page_size}"
            response = self.session.get(url, params=params, headers={"Prefer": prefer},
                                        timeout=30, allow_redirects=False)
            if response.status_code == 401:
                raise OutlookAuthError()
            if response.status_code == 403:
                raise OutlookPolicyError()
            if response.status_code != 200:
                raise OutlookAPIError(response.status_code)
            value = response.json()
            if not isinstance(value, dict):
                raise OutlookAPIError()
            return value
        except OutlookError:
            raise
        except Exception:
            raise OutlookAPIError() from None

    def discover_folders(self):
        # Resolve system identities via well-known names, never localized display names.
        known = {}
        for name in sorted(WELL_KNOWN):
            try:
                folder = self._get(folder_url(name), {"$select": FOLDER_FIELDS})
                known[name] = identifier(folder["id"])
            except OutlookAPIError as error:
                if error.status != 404:
                    raise
        folders, pending, seen_paths = [], [GRAPH_BASE], set()
        for _ in range(10000):
            if not pending:
                return folders, known
            path = pending.pop(0)
            if path in seen_paths:
                raise OutlookResyncRequiredError()
            seen_paths.add(path)
            link, visited = None, set()
            for _ in range(1000):
                response = self._get(link or path, None if link else {"$select": FOLDER_FIELDS,
                                    "includeHiddenFolders": "false"})
                values = response["value"]
                if not isinstance(values, list):
                    raise OutlookAPIError()
                for original in values:
                    folder = original
                    fid = identifier(folder["id"])
                    folder = {"id": fid, "name": folder.get("displayName", ""),
                              "parent": None if path == GRAPH_BASE else unquote(path.split("/")[-2]),
                              "hidden": folder.get("isHidden", False)}
                    folders.append(folder)
                    # Traverse visible folders to discover nested custom folders.
                    if original.get("childFolderCount", 0) and not folder["hidden"]:
                        pending.append(folder_url(fid) + "/childFolders")
                next_link = response.get("@odata.nextLink")
                if not next_link:
                    break
                link = validate_link(next_link, discovery_path=path)
                if link in visited:
                    raise OutlookResyncRequiredError()
                visited.add(link)
            else:
                raise OutlookResyncRequiredError()
        raise OutlookResyncRequiredError()

    def message(self, message_id):
        url = "https://graph.microsoft.com/v1.0/me/messages/" + quote(identifier(message_id), safe="")
        return self._get(url, {"$select": ",".join(MESSAGE_FIELDS)})

    def delta(self, folder_id, link, page_size):
        path = folder_url(folder_id) + "/messages/delta"
        return self._get(validate_link(link, folder_id) if link else path,
                         None if link else {"$select": ",".join(MESSAGE_FIELDS)}, page_size)


class FolderPolicy:
    def __init__(self, include=(), exclude=()):
        self.include = tuple(sorted({identifier(item) for item in include}))
        self.exclude = tuple(sorted({identifier(item) for item in exclude}))
        self.fingerprint = sha256(json.dumps({"v": 1, "include": self.include,
                    "exclude": self.exclude, "default_excluded": DEFAULT_EXCLUDED}, sort_keys=True).encode()).hexdigest()

    def select(self, folders, known):
        resolve = lambda items: {known.get(item, item) for item in items}
        included, excluded = resolve(self.include), resolve((*DEFAULT_EXCLUDED, *self.exclude))
        # Explicit includes can opt in to a default-excluded folder, but explicit
        # excludes always win. Descendants of excluded/hidden folders are excluded.
        excluded -= included
        excluded |= resolve(self.exclude)
        by_id = {identifier(folder["id"]): folder for folder in folders}
        if len(by_id) != len(folders):
            raise OutlookResyncRequiredError()
        for _ in range(len(folders) + 1):
            before = len(excluded)
            for fid, folder in by_id.items():
                if folder.get("hidden") or folder.get("parent") in excluded:
                    excluded.add(fid)
            if len(excluded) == before:
                break
        return {fid: folder for fid, folder in by_id.items()
                if fid not in excluded and (not included or fid in included)}


def minimize_message(message):
    result = {"id": identifier(message["id"]), "parent_folder_id": identifier(message["parentFolderId"])}
    scalar = {"internetMessageId": "internet_message_id", "conversationId": "conversation_id",
        "receivedDateTime": "received_at", "sentDateTime": "sent_at", "createdDateTime": "created_at",
        "lastModifiedDateTime": "modified_at", "subject": "subject", "importance": "importance"}
    for source, target in scalar.items():
        if source in message:
            value = message[source]
            if value is not None and not isinstance(value, str):
                raise ValueError("Invalid Outlook metadata")
            if source.endswith("DateTime") and value:
                timestamp(value)
            result[target] = value
    for key in ("isRead", "hasAttachments"):
        if key in message:
            if not isinstance(message[key], bool):
                raise ValueError("Invalid Outlook flag")
            result[{"isRead": "is_read", "hasAttachments": "has_attachments"}[key]] = message[key]
    categories = message.get("categories", [])
    if not isinstance(categories, list) or not all(isinstance(item, str) for item in categories):
        raise ValueError("Invalid Outlook categories")
    result["categories"] = sorted(set(categories))

    def address(item):
        email = item["emailAddress"]
        return {key: email[key] for key in ("name", "address") if key in email and isinstance(email[key], str)}
    for key in ("from", "sender"):
        if message.get(key):
            result[key] = address(message[key])
    for key, target in (("toRecipients", "to"), ("ccRecipients", "cc"), ("bccRecipients", "bcc")):
        result[target] = [address(item) for item in message.get(key, [])]
    return result


def timestamp(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Outlook timestamp must include timezone")
    return parsed.astimezone(timezone.utc)


class OutlookConnector:
    provider = "outlook"

    def __init__(self, client: OutlookClient, policy=None, page_size=25):
        if isinstance(page_size, bool) or not isinstance(page_size, int) or not 1 <= page_size <= 100:
            raise ValueError("Outlook page_size must be between 1 and 100")
        self.client, self.policy, self.page_size = client, policy or FolderPolicy(), page_size

    def verify_account(self, account):
        expected = require_outlook_account(account)
        username, binding = self.client.identity()
        if outlook_identity(username) != expected:
            raise OutlookIdentityError()
        return expected, identifier(binding)

    def fetch_changes(self, account, cursor):
        try:
            mailbox, binding = self.verify_account(account)
            bound = {"v": 1, "household": account.household_id, "account": account.id,
                     "mailbox": mailbox, "binding": binding, "policy": self.policy.fingerprint}
            state = {**bound, "folders": {}, "pending": []}
            if cursor is not None:
                try:
                    state = json.loads(cursor)
                    if set(state) != {*bound, "folders", "pending"} or type(state.get("v")) is not int:
                        raise ValueError()
                    if any(state.get(key) != value for key, value in bound.items()):
                        raise ValueError()
                    if not isinstance(state["folders"], dict) or not isinstance(state["pending"], list):
                        raise ValueError()
                    if len(set(state["pending"])) != len(state["pending"]):
                        raise ValueError()
                    for fid, folder in state["folders"].items():
                        identifier(fid)
                        if set(folder) != {"name", "link", "kind", "active"}:
                            raise ValueError()
                        if not isinstance(folder["name"], str) or not isinstance(folder["active"], bool):
                            raise ValueError()
                        if folder["kind"] not in {"initial", "next", "delta"}:
                            raise ValueError()
                        if folder["link"] is None:
                            if folder["kind"] != "initial":
                                raise ValueError()
                        else:
                            if folder["kind"] == "initial":
                                raise ValueError()
                            validate_link(folder["link"], fid, kind=folder["kind"])
                    if any(fid not in state["folders"] for fid in state["pending"]):
                        raise ValueError()
                    if any(folder["active"] and folder["kind"] in {"initial", "next"} and fid not in state["pending"]
                           for fid, folder in state["folders"].items()):
                        raise ValueError()
                except Exception:
                    raise OutlookResyncRequiredError() from None
            # Refresh discovery each page so new folders join without resetting old
            # streams. Removed/excluded streams stay in the cursor but are inactive.
            folders, known = self.client.discover_folders()
            selected = self.policy.select(folders, known)
            for fid, folder in state["folders"].items():
                folder["active"] = fid in selected
            new = []
            for fid, folder in selected.items():
                if not isinstance(folder["name"], str):
                    raise ValueError()
                if fid not in state["folders"]:
                    state["folders"][fid] = {"name": folder["name"], "link": None, "kind": "initial", "active": True}
                    new.append(fid)
                else:
                    state["folders"][fid]["name"] = folder["name"]
            pending = [fid for fid in state["pending"] if fid in selected]
            pending += [fid for fid in sorted(new) if fid not in pending]
            if not pending:
                pending = sorted(selected)
            if not pending:
                state["pending"] = []
                return ChangeBatch((), json.dumps(state, sort_keys=True), False)
            fid = pending[0]
            stream = state["folders"][fid]
            try:
                response = self.client.delta(fid, stream["link"], self.page_size)
            except OutlookAPIError as error:
                if error.status in {400, 404, 410}:
                    raise OutlookResyncRequiredError(fid) from None
                raise
            records = []
            if not isinstance(response["value"], list):
                raise ValueError()
            # Re-fetch current basic metadata once per changed immutable ID. This
            # avoids partial delta payloads and stale folder snapshots overwriting
            # a later move when independently paged folder streams overlap.
            ids = dict.fromkeys(identifier(item["id"]) for item in response["value"] if "@removed" not in item)
            for mid in ids:
                try:
                    snapshot = minimize_message(self.client.message(mid))
                except OutlookAPIError as error:
                    if error.status == 404:
                        continue  # Preserve historical provenance on disappearance.
                    raise
                if snapshot["id"] != mid:
                    raise ValueError("Outlook message identity changed")
                records.append(RawRecord(mid, snapshot))
            next_link, delta_link = response.get("@odata.nextLink"), response.get("@odata.deltaLink")
            if bool(next_link) == bool(delta_link):
                raise OutlookResyncRequiredError(fid)
            link = validate_link(next_link or delta_link, fid, kind="next" if next_link else "delta")
            if next_link and link == stream["link"]:
                raise OutlookResyncRequiredError(fid)
            stream.update(link=link, kind="next" if next_link else "delta")
            if not next_link:
                pending.pop(0)
            state["pending"] = pending
            return ChangeBatch(tuple(records), json.dumps(state, sort_keys=True), bool(pending))
        except OutlookError:
            raise
        except Exception:
            raise OutlookAPIError() from None

    def normalize(self, record):
        data = record.payload
        date = data.get("received_at") or data.get("sent_at") or data.get("created_at")
        recipients = tuple(dict.fromkeys(item["address"] for key in ("to", "cc", "bcc")
                                         for item in data[key] if item.get("address")))
        sender = data.get("from") or data.get("sender") or {}
        return NormalizedRecord(record.provider_object_id, "message",
            provider_thread_id=data.get("conversation_id"), occurred_at=timestamp(date) if date else None,
            subject=data.get("subject"), sender=sender.get("address"), recipients=recipients, metadata=data)
