"""Callable local application operations; no CLI, HTTP, or client authorization.

Callers own the database engine. These operations own every provider client they
load and return only aggregate results and intentional operator-display identities.
"""
from dataclasses import dataclass
import logging

from . import gmail_auth, outlook_auth, google_calendar_auth, google_drive_auth
from .gmail import GmailConnector
from .gmail_identity import mailbox_identity
from .errors import MailboxIdentityError
from .outlook import OutlookConnector, FolderPolicy
from .outlook_identity import require_outlook_account
from .google_calendar import GoogleCalendarConnector, CalendarPolicy, recover_stream
from .google_calendar_identity import require_calendar_account
from .google_drive import GoogleDriveConnector, DrivePolicy, transform_state
from .google_drive_identity import require_drive_account
from .ingestion import IngestionResult, ingest
from .registry import get_account


@dataclass(frozen=True)
class IngestionOutcome:
    ingestion: IngestionResult
    verified_identity: str | None = None


def _account(engine, household_id, account_id):
    with engine.connect() as connection:
        return get_account(connection, household_id, account_id)


def _require_gmail(account):
    if account.provider != "gmail" or not account.enabled:
        raise ValueError("Expected an enabled Gmail source account")
    try:
        mailbox_identity(account.external_account)
    except ValueError:
        raise MailboxIdentityError() from None


def _close(client, provider):
    try:
        client.session.close()
    except Exception:
        # Cleanup neither leaks private text nor masks a primary failure.
        logging.error("%s session cleanup failed", provider)


def _ingest_verified(engine, household_id, account_id, connector, identity, max_pages):
    try:
        result = ingest(engine, household_id, account_id, connector, max_pages=max_pages)
    except Exception as error:
        # Preserve the original exception/category, plus the already-verified
        # presentation value. No SDK state or raw payload is attached.
        try:
            error.verified_identity = identity
        except Exception:
            pass  # Presentation annotation must never replace the primary error.
        raise
    return IngestionOutcome(result, identity)


def ingest_gmail(engine, household_id, account_id, *, query="newer_than:365d -in:spam -in:trash",
                 page_size=25, max_pages=100) -> IngestionOutcome:
    account = _account(engine, household_id, account_id)
    _require_gmail(account)
    client = gmail_auth.load_client(account)
    try:
        connector = GmailConnector(client, query=query, page_size=page_size)
        identity = connector.verify_account(account)["emailAddress"]
        return _ingest_verified(engine, household_id, account_id, connector, identity, max_pages)
    finally:
        _close(client, "Gmail")


def ingest_outlook(engine, household_id, account_id, *, include_folder=(), exclude_folder=(),
                   page_size=25, max_pages=100) -> IngestionOutcome:
    account = _account(engine, household_id, account_id)
    require_outlook_account(account)
    client = outlook_auth.load_client(account)
    try:
        policy = FolderPolicy(include_folder, exclude_folder)
        connector = OutlookConnector(client, policy, page_size)
        identity, _ = connector.verify_account(account)
        return _ingest_verified(engine, household_id, account_id, connector, identity, max_pages)
    finally:
        _close(client, "Outlook")


def ingest_google_calendar(engine, household_id, account_id, *, include_calendar=(), exclude_calendar=(),
                           page_size=25, max_pages=100) -> IngestionOutcome:
    account = _account(engine, household_id, account_id)
    require_calendar_account(account)
    client = google_calendar_auth.load_client(account)
    try:
        policy = CalendarPolicy(include_calendar, exclude_calendar)
        connector = GoogleCalendarConnector(client, policy, page_size)
        identity = connector.verify_account(account)
        return _ingest_verified(engine, household_id, account_id, connector, identity, max_pages)
    finally:
        _close(client, "Calendar")


def ingest_google_drive(engine, household_id, account_id, *, include_shared_drive=(),
                        page_size=25, max_pages=100) -> IngestionOutcome:
    account = _account(engine, household_id, account_id)
    require_drive_account(account)
    client = google_drive_auth.load_client(account)
    try:
        policy = DrivePolicy(include_shared_drive)
        connector = GoogleDriveConnector(client, policy, page_size)
        result = ingest(engine, household_id, account_id, connector, max_pages=max_pages)
        return IngestionOutcome(result)  # Drive routine output remains aggregate-only.
    finally:
        _close(client, "Drive")


def resync_google_calendar(engine, household_id, account_id, *, include_calendar=(),
                           exclude_calendar=(), calendar_id=None) -> None:
    account = _account(engine, household_id, account_id)
    require_calendar_account(account)
    recover_stream(engine, household_id, account_id,
                   CalendarPolicy(include_calendar, exclude_calendar), calendar_id)


def resync_google_drive(engine, household_id, account_id, *, include_shared_drive=(), drive_id=None) -> None:
    account = _account(engine, household_id, account_id)
    require_drive_account(account)
    fingerprint = google_drive_auth.load_binding(account)  # Local keyring only.
    transform_state(engine, household_id, account_id, fingerprint,
                    DrivePolicy(include_shared_drive), drive_id)


def migrate_google_drive_policy(engine, household_id, account_id, *, previous_shared_drive=(),
                                include_shared_drive=()) -> None:
    account = _account(engine, household_id, account_id)
    require_drive_account(account)
    fingerprint = google_drive_auth.load_binding(account)  # No client or OAuth.
    transform_state(engine, household_id, account_id, fingerprint,
                    DrivePolicy(previous_shared_drive), new_policy=DrivePolicy(include_shared_drive))
