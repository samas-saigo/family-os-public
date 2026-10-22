"""Transactional account registry, with explicit ownership and tenancy checks."""
from datetime import datetime, timezone
from pathlib import Path
import yaml
from sqlalchemy import select
from .domain import SourceAccount
from .gmail_identity import mailbox_identity
from .outlook_identity import outlook_identity
from .google_calendar_identity import calendar_identity
from .google_drive_identity import drive_identity
from .schema import household, person, source_account, source_sync_state
from .storage import insert_for, upsert

def require_id(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("IDs and names must be nonempty strings")
    return value

def load_registry(engine, path: str | Path):
    config = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    register(engine, config)

def register(engine, config: dict):
    home = config["household"]
    home_id = require_id(home["id"])
    require_id(home["name"])
    people = config.get("people", [])
    accounts = config.get("source_accounts", [])
    person_ids = [require_id(p["id"]) for p in people]
    account_ids = [require_id(a["id"]) for a in accounts]
    if len(set(person_ids)) != len(person_ids) or len(set(account_ids)) != len(account_ids):
        raise ValueError("Duplicate registry IDs")
    with engine.begin() as connection:
        upsert(connection, household, home, ["id"], ["name"])
        for member in people:
            require_id(member["display_name"])
            existing = connection.execute(select(person).where(person.c.id == member["id"])).mappings().first()
            if existing and existing["household_id"] != home_id:
                raise ValueError("Cannot transfer a person between households")
            upsert(connection, person, dict(id=member["id"], household_id=home_id,
                   display_name=member["display_name"], metadata={"aliases": member.get("aliases", [])}),
                   ["id"], ["display_name", "metadata"])
        for account in accounts:
            require_id(account["provider"])
            owner_type, owner_id = account["owner_type"], account.get("owner_id")
            if owner_type == "person":
                member = connection.execute(select(person).where(person.c.id == owner_id, person.c.household_id == home_id)).first()
                if not member:
                    raise ValueError("Person owner must exist in the same household")
            elif owner_type == "household":
                if owner_id != home_id:
                    raise ValueError("Shared account owner must equal its household")
            elif owner_type != "unknown" or owner_id is not None:
                raise ValueError("Unknown accounts must have no owner")
            enabled = account.get("enabled", True)
            if not isinstance(enabled, bool):
                raise ValueError("enabled must be a boolean")
            if account["provider"] == "gmail":
                mailbox_identity(account.get("external_account"))
            if account["provider"] == "outlook":
                outlook_identity(account.get("external_account"))
            if account["provider"] == "google_calendar":
                calendar_identity(account.get("external_account"))
            if account["provider"] == "google_drive":
                drive_identity(account.get("external_account"))
            existing = connection.execute(select(source_account).where(source_account.c.id == account["id"])).mappings().first()
            if existing and any(existing[k] != v for k, v in {
                "household_id": home_id, "provider": account["provider"],
                "external_account": account.get("external_account")}.items()):
                raise ValueError("Account identity is immutable; create a new account ID")
            # Unknown ownership may be resolved once. Explicit ownership is part
            # of historical attribution and cannot be reassigned on registry reload.
            if existing and existing["owner_type"] != "unknown" and (
                existing["owner_type"], existing["owner_id"]
            ) != (owner_type, owner_id):
                raise ValueError("Explicit account owner is immutable; create a new account ID")
            values = dict(id=account["id"], household_id=home_id, provider=account["provider"],
                          owner_type=owner_type, owner_id=owner_id,
                          person_owner_id=owner_id if owner_type == "person" else None,
                          external_account=account.get("external_account"), enabled=enabled, metadata={})
            upsert(connection, source_account, values, ["id"], ["owner_type", "owner_id", "person_owner_id", "enabled"])
            statement = insert_for(connection, source_sync_state).values(source_account_id=account["id"],
                cursor=None, version=0, updated_at=datetime.now(timezone.utc))
            connection.execute(statement.on_conflict_do_nothing(index_elements=["source_account_id"]))
        # The household upsert above serializes registry writers on both supported DBs.
        # Check final state so disabling one account and enabling its replacement is atomic.
        validate_gmail_identities(connection, home_id)
        validate_outlook_identities(connection, home_id)
        validate_calendar_identities(connection, home_id)
        validate_drive_identities(connection, home_id)

def validate_gmail_identities(connection, household_id: str):
    seen = set()
    identities = connection.execute(select(source_account.c.external_account).where(
        source_account.c.household_id == household_id,
        source_account.c.provider == "gmail", source_account.c.enabled.is_(True))).scalars()
    for address in identities:
        identity = mailbox_identity(address)
        if identity in seen:
            raise ValueError("Duplicate active Gmail mailbox in this household")
        seen.add(identity)

def validate_outlook_identities(connection, household_id: str):
    seen = set()
    identities = connection.execute(select(source_account.c.external_account).where(
        source_account.c.household_id == household_id,
        source_account.c.provider == "outlook", source_account.c.enabled.is_(True))).scalars()
    for address in identities:
        identity = outlook_identity(address)
        if identity in seen:
            raise ValueError("Duplicate active Outlook mailbox in this household")
        seen.add(identity)

def validate_calendar_identities(connection, household_id: str):
    seen = set()
    identities = connection.execute(select(source_account.c.external_account).where(
        source_account.c.household_id == household_id,
        source_account.c.provider == "google_calendar", source_account.c.enabled.is_(True))).scalars()
    for address in identities:
        identity = calendar_identity(address)
        if identity in seen:
            raise ValueError("Duplicate active Google Calendar identity in this household")
        seen.add(identity)

def validate_drive_identities(connection, household_id: str):
    seen = set()
    identities = connection.execute(select(source_account.c.external_account).where(
        source_account.c.household_id == household_id,
        source_account.c.provider == "google_drive", source_account.c.enabled.is_(True))).scalars()
    for address in identities:
        identity = drive_identity(address)
        if identity in seen:
            raise ValueError("Duplicate active Google Drive identity in this household")
        seen.add(identity)

def get_account(connection, household_id: str, account_id: str) -> SourceAccount:
    row = connection.execute(select(source_account).where(source_account.c.id == account_id,
        source_account.c.household_id == household_id)).mappings().first()
    if row is None:
        raise ValueError("Account not found in this household")
    if row["provider"] == "gmail":
        validate_gmail_identities(connection, household_id)
    if row["provider"] == "outlook":
        validate_outlook_identities(connection, household_id)
    if row["provider"] == "google_calendar":
        validate_calendar_identities(connection, household_id)
    if row["provider"] == "google_drive":
        validate_drive_identities(connection, household_id)
    return SourceAccount(**{key: row[key] for key in SourceAccount.__dataclass_fields__})

def list_accounts(engine, household_id: str) -> list[SourceAccount]:
    with engine.connect() as connection:
        ids = connection.execute(select(source_account.c.id).where(source_account.c.household_id == household_id)).scalars().all()
        return [get_account(connection, household_id, account_id) for account_id in ids]
