"""Read-only Gmail adapter. API/auth types and unsanitized responses stay here."""
import json
import random
import time
from datetime import datetime, timezone
from email.utils import getaddresses
from typing import Protocol

from .domain import ChangeBatch, NormalizedRecord, RawRecord, SourceAccount
from .errors import GmailAPIError, GmailError, GmailTransportError, MailboxIdentityError, ResyncRequiredError
from .gmail_identity import mailbox_identity
from .gmail_privacy import private_transport
from .gmail_transport import transport_get

DEFAULT_QUERY = "newer_than:365d -in:spam -in:trash"
SAFE_HEADERS = frozenset({"from", "to", "cc", "bcc", "subject", "date", "message-id",
                          "in-reply-to", "references"})
MIME_METADATA_DEPTH = 16
GET_ATTEMPTS = 5
QUOTA_GET_ATTEMPTS = 8
GET_MAX_DELAY = 32.0
GET_MIN_INTERVAL = 0.30  # ~200 GETs / 4,000 worst-case quota units per minute.
TRANSIENT_403_REASONS = frozenset({"rateLimitExceeded", "userRateLimitExceeded"})


def _transient_403(response):
    """Read only structured reasons; return no provider strings/payloads."""
    try:
        value = response.json()
        if not isinstance(value, dict) or not isinstance(value.get("error"), dict):
            return False
        errors = value["error"].get("errors")
        if not isinstance(errors, list) or not 1 <= len(errors) <= 16:
            return False
        # A mixed permanent/transient response is not safe to blindly retry.
        return all(isinstance(item, dict) and isinstance(item.get("reason"), str)
                   and item["reason"] in TRANSIENT_403_REASONS for item in errors)
    except Exception:
        return False


def _message_fields():
    # Gmail's partial-response projection has no recursive wildcard. Explicitly
    # project each supported MIME level; never request body.data at any level.
    part = "mimeType,filename,body(size,attachmentId)"
    nested = part + ",parts(mimeType)"
    for _ in range(MIME_METADATA_DEPTH):
        nested = f"{part},parts({nested})"
    return "id,threadId,internalDate,labelIds,sizeEstimate,historyId,payload(headers(name,value)," + nested + ")"


class GmailClient(Protocol):
    def profile(self) -> dict: ...
    def list_messages(self, query: str, page_token: str | None, page_size: int) -> dict: ...
    def message(self, message_id: str) -> dict: ...
    def history(self, history_id: str, page_token: str | None, page_size: int) -> dict: ...


class GmailHTTPClient:
    """Only fixed read endpoints; no SDK discovery, attachment download or write API."""
    BASE = "https://gmail.googleapis.com/gmail/v1/users/me/"

    def __init__(self, session, *, sleep=None, jitter=None, clock=None):
        self.session = session
        self._sleep = time.sleep if sleep is None else sleep
        self._jitter = random.random if jitter is None else jitter
        self._clock = time.monotonic if clock is None else clock
        self._last_get_started = None

    def _pace_get(self):
        # Local synchronous client only; no wall clock, burst credit or DB state.
        now = self._clock()
        if self._last_get_started is not None:
            remaining = GET_MIN_INTERVAL - (now - self._last_get_started)
            if remaining > 0:
                self._sleep(remaining)
                now = self._clock()  # Include actual sleep/oversleep before recording start.
        self._last_get_started = now

    @private_transport
    def _get(self, resource, params=None):
        try:
            for attempt in range(QUOTA_GET_ATTEMPTS):
                self._pace_get()
                try:
                    response = transport_get(self.session, self.BASE + resource, params=params, timeout=30)
                except GmailTransportError:
                    if attempt >= GET_ATTEMPTS - 1:
                        raise GmailAPIError() from None
                    self._sleep(min(GET_MAX_DELAY, 2 ** attempt + self._jitter()))
                    continue
                status = response.status_code
                if status == 200:
                    value = response.json()
                    if not isinstance(value, dict):
                        raise GmailAPIError()
                    return value
                transient_403 = status == 403 and _transient_403(response)
                quota = transient_403 or status == 429
                retryable = quota or status >= 500
                # One shared attempt counter: category changes never reset the budget.
                attempts = QUOTA_GET_ATTEMPTS if quota else GET_ATTEMPTS
                if not retryable or attempt >= attempts - 1:
                    raise GmailAPIError(status, transient_403=transient_403)
                # Fixed finite budget; jitter is [0, 1) seconds. No cursor/state changes.
                self._sleep(min(GET_MAX_DELAY, 2 ** attempt + self._jitter()))
        except GmailError:
            raise
        except Exception:
            raise GmailAPIError() from None

    def profile(self):
        return self._get("profile", {"fields": "emailAddress,historyId"})

    def list_messages(self, query, page_token, page_size):
        return self._get("messages", {"q": query, "pageToken": page_token,
            "maxResults": page_size, "includeSpamTrash": False,
            "fields": "messages(id),nextPageToken"})

    def message(self, message_id):
        # Full format with a metadata-only field projection supplies MIME metadata
        # without downloading snippets, message bodies, or attachment bytes.
        from urllib.parse import quote
        return self._get("messages/" + quote(message_id, safe=""), {"format": "full",
            "fields": _message_fields()})

    def history(self, history_id, page_token, page_size):
        return self._get("history", {"startHistoryId": history_id,
            "pageToken": page_token, "maxResults": page_size,
            "fields": "history(messages(id),messagesAdded(message(id)),"
                      "labelsAdded(message(id)),labelsRemoved(message(id))),historyId,nextPageToken"})


def _identifier(value):
    if not isinstance(value, str) or not value or len(value) > 4096:
        raise ValueError("Invalid Gmail response identity")
    return value


def _history_id(value):
    value = _identifier(value)
    if not value.isascii() or not value.isdecimal():
        raise ValueError("Invalid Gmail history identity")
    return value


def minimize_message(message: dict) -> dict:
    """Construct an allowlist snapshot; never copy arbitrary payload/body fields."""
    result = {"id": _identifier(message["id"]), "thread_id": _identifier(message["threadId"]),
        "internal_date": str(int(message["internalDate"])),
        "label_ids": sorted({_identifier(label) for label in message.get("labelIds", [])}),
        "headers": {}, "attachments": []}
    if "historyId" in message:
        result["history_id"] = _history_id(message["historyId"])
    if "sizeEstimate" in message:
        result["size_estimate"] = int(message["sizeEstimate"])
    payload = message.get("payload", {})
    for header in payload.get("headers", []):
        name, value = header.get("name", "").casefold(), header.get("value")
        if name in SAFE_HEADERS and isinstance(value, str):
            result["headers"].setdefault(name, []).append(value)

    def attachments(part, depth=0):
        if depth > MIME_METADATA_DEPTH:
            raise ValueError("Gmail MIME nesting exceeds supported limit")
        body = part.get("body", {})
        # attachmentId also catches unnamed MIME attachments. Inline body data is ignored.
        if part.get("filename") or body.get("attachmentId"):
            item = {"filename": part.get("filename", ""),
                    "mime_type": part.get("mimeType", "application/octet-stream"),
                    "size": int(body.get("size", 0))}
            if body.get("attachmentId"):
                item["attachment_id"] = _identifier(body["attachmentId"])
            if not isinstance(item["filename"], str) or not isinstance(item["mime_type"], str):
                raise ValueError("Invalid Gmail attachment metadata")
            result["attachments"].append(item)
        for child in part.get("parts", []):
            attachments(child, depth + 1)

    attachments(payload)
    return result


class GmailConnector:
    provider = "gmail"

    def __init__(self, client: GmailClient, query=DEFAULT_QUERY, page_size=25):
        if not isinstance(query, str) or not query.strip() or len(query) > 4096:
            raise ValueError("A bounded initial Gmail query is required")
        if isinstance(page_size, bool) or not isinstance(page_size, int) or not 1 <= page_size <= 100:
            raise ValueError("Gmail page_size must be between 1 and 100")
        self.client, self.query, self.page_size = client, query, page_size

    def verify_account(self, account: SourceAccount):
        if account.provider != self.provider or not account.enabled:
            raise MailboxIdentityError()
        try:
            expected = mailbox_identity(account.external_account)
            profile = self.client.profile()
            if mailbox_identity(profile.get("emailAddress")) != expected:
                raise MailboxIdentityError()
            _history_id(profile["historyId"])
            return profile
        except GmailError:
            raise
        except ValueError:
            raise MailboxIdentityError() from None
        except Exception:
            raise GmailAPIError() from None

    def _state(self, account, cursor, profile):
        binding = {"v": 1, "account": account.id, "household": account.household_id,
                   "mailbox": mailbox_identity(account.external_account), "query": self.query}
        if cursor is None:
            return {**binding, "phase": "initial", "history_id": profile["historyId"], "page_token": None}
        try:
            state = json.loads(cursor)
            if any(state.get(key) != value for key, value in binding.items()):
                raise ValueError()
            if state["phase"] not in {"initial", "history"}:
                raise ValueError()
            _history_id(state["history_id"])
            if state["page_token"] is not None:
                _identifier(state["page_token"])
            return state
        except Exception:
            raise ResyncRequiredError() from None

    def fetch_changes(self, account, cursor):
        try:
            # Recheck on every page, including resumed runs and injected clients.
            profile = self.verify_account(account)
            state = self._state(account, cursor, profile)
            if state["phase"] == "initial":
                try:
                    response = self.client.list_messages(self.query, state["page_token"], self.page_size)
                except GmailAPIError as error:
                    if error.status == 400 and state["page_token"]:
                        raise ResyncRequiredError() from None
                    raise
                ids = [_identifier(item["id"]) for item in response.get("messages", [])]
                next_token = response.get("nextPageToken")
                next_state = {**state, "page_token": next_token,
                              "phase": "initial" if next_token else "history"}
                # Immediately drain history since the pre-list baseline, closing the
                # race between the initial listing and ongoing mailbox changes.
                has_more = True
            else:
                try:
                    response = self.client.history(state["history_id"], state["page_token"], self.page_size)
                except GmailAPIError as error:
                    if error.status in {400, 404}:
                        raise ResyncRequiredError() from None
                    raise
                ids = []
                for event in response.get("history", []):
                    ids.extend(_identifier(item["id"]) for item in event.get("messages", []))
                    for key in ("messagesAdded", "labelsAdded", "labelsRemoved"):
                        ids.extend(_identifier(item["message"]["id"]) for item in event.get(key, []))
                next_token = response.get("nextPageToken")
                tip = _history_id(response["historyId"])
                if int(tip) < int(state["history_id"]):
                    raise ResyncRequiredError()
                # Keep the original startHistoryId for all pages in the history scan.
                next_state = {**state, "page_token": next_token,
                    "history_id": state["history_id"] if next_token else tip}
                has_more = bool(next_token)
            if next_token is not None:
                _identifier(next_token)
                if next_token == state["page_token"]:
                    raise ResyncRequiredError()
            records = []
            for message_id in dict.fromkeys(ids):
                try:
                    snapshot = minimize_message(self.client.message(message_id))
                except GmailAPIError as error:
                    if error.status == 404:
                        # Source-side disappearance: keep all prior Family OS provenance.
                        continue
                    raise
                if snapshot["id"] != message_id:
                    raise ValueError("Gmail message identity changed")
                records.append(RawRecord(message_id, snapshot))
            return ChangeBatch(tuple(records), json.dumps(next_state, sort_keys=True), has_more)
        except GmailError:
            raise
        except Exception:
            raise GmailAPIError() from None

    def normalize(self, record):
        data = record.payload
        headers = data["headers"]
        recipients = getaddresses([value for name in ("to", "cc", "bcc") for value in headers.get(name, [])])
        return NormalizedRecord(record.provider_object_id, "message",
            provider_thread_id=data["thread_id"],
            occurred_at=datetime.fromtimestamp(int(data["internal_date"]) / 1000, timezone.utc),
            subject=next(iter(headers.get("subject", [])), None),
            sender=next(iter(headers.get("from", [])), None),
            recipients=tuple(dict.fromkeys(address for _, address in recipients if address)),
            metadata=data)
