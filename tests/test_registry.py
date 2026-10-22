from copy import deepcopy
import pytest
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from family_os.registry import register, list_accounts
from family_os.schema import household, person, source_account

@pytest.fixture
def config():
    return {"household": {"id": "home", "name": "Demo household"},
        "people": [{"id": "alex", "display_name": "Alex"}],
        "source_accounts": [
            {"id": "personal", "provider": "fixture", "owner_type": "person", "owner_id": "alex"},
            {"id": "secondary", "provider": "fixture", "owner_type": "person", "owner_id": "alex"},
            {"id": "shared", "provider": "fixture", "owner_type": "household", "owner_id": "home"},
            {"id": "unresolved", "provider": "fixture", "owner_type": "unknown"}]}

def test_multiple_accounts_shared_and_unknown(engine, config):
    register(engine, config)
    register(engine, config)
    accounts = list_accounts(engine, "home")
    assert len(accounts) == 4
    assert [a.owner_id for a in accounts if a.owner_type == "person"] == ["alex", "alex"]
    assert next(a for a in accounts if a.id == "shared").owner_id == "home"
    assert next(a for a in accounts if a.id == "unresolved").owner_id is None
    assert list_accounts(engine, "other") == []

@pytest.mark.parametrize("changes", [
    {"owner_id": "missing"}, {"owner_type": "household", "owner_id": "other"},
    {"owner_type": "unknown", "owner_id": "alex"}, {"enabled": "false"}])
def test_invalid_registry_rolls_back(engine, config, changes):
    config["source_accounts"][0].update(changes)
    with pytest.raises(ValueError):
        register(engine, config)
    with engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(household)) == 0

def test_cannot_transfer_person_or_reuse_account_identity(engine, config):
    register(engine, config)
    other = deepcopy(config)
    other["household"]["id"] = "other"
    with pytest.raises(ValueError):
        register(engine, other)
    config["source_accounts"][0]["external_account"] = "different@example.invalid"
    with pytest.raises(ValueError):
        register(engine, config)

def test_database_rejects_cross_household_owner(engine, config):
    register(engine, config)
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(household.insert().values(id="other", name="Other"))
        connection.execute(source_account.insert().values(id="invalid", household_id="other",
            provider="fixture", owner_type="person", owner_id="alex", person_owner_id="alex",
            enabled=True, metadata={}))

def test_database_rejects_shared_account_without_owner(engine, config):
    register(engine, config)
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(source_account.insert().values(id="invalid", household_id="home",
            provider="fixture", owner_type="household", owner_id=None, person_owner_id=None,
            enabled=True, metadata={}))


@pytest.mark.parametrize("initial_owner, next_owner, allowed", [
    (("unknown", None), ("person", "alex"), True),
    (("unknown", None), ("household", "home"), True),
    (("unknown", None), ("unknown", None), True),
    (("person", "alex"), ("person", "alex"), True),
    (("household", "home"), ("household", "home"), True),
    (("person", "alex"), ("person", "spouse"), False),
    (("person", "alex"), ("household", "home"), False),
    (("household", "home"), ("person", "alex"), False),
    (("person", "alex"), ("unknown", None), False),
    (("household", "home"), ("unknown", None), False),
])
def test_account_ownership_transitions_preserve_attribution(engine, config, initial_owner, next_owner, allowed):
    from family_os.ingestion import ingest
    from family_os.schema import raw_source_record, source_record, source_sync_state
    from test_ingestion import FakeConnector

    config["people"].append({"id": "spouse", "display_name": "Spouse"})
    config["source_accounts"] = [dict(config["source_accounts"][0],
        owner_type=initial_owner[0], owner_id=initial_owner[1])]
    register(engine, config)
    ingest(engine, "home", "personal", FakeConnector())

    def snapshot(table):
        with engine.connect() as connection:
            return connection.execute(select(table).order_by(*table.primary_key.columns)).mappings().all()

    history = {table.name: snapshot(table) for table in (raw_source_record, source_record, source_sync_state)}
    original_accounts = snapshot(source_account)
    original_people = snapshot(person)
    original_household = snapshot(household)
    changed = deepcopy(config)
    changed["household"]["name"] = "Updated synthetic household"
    changed["people"][0]["display_name"] = "Updated Alex"
    changed["source_accounts"][0].update(owner_type=next_owner[0], owner_id=next_owner[1], enabled=False)
    if allowed:
        register(engine, changed)
        register(engine, changed)  # Reloading the resolved owner is idempotent.
        current = snapshot(source_account)[0]
        assert (current["owner_type"], current["owner_id"]) == next_owner
        assert current["person_owner_id"] == (next_owner[1] if next_owner[0] == "person" else None)
        assert current["enabled"] is False
        changed["source_accounts"][0]["enabled"] = True
        register(engine, changed)
        assert snapshot(source_account)[0]["enabled"] is True
    else:
        with pytest.raises(ValueError, match="Explicit account owner is immutable"):
            register(engine, changed)
        # Rejected reassignment rolls back the entire registry reload, including
        # enabled and unrelated household/person changes preceding the check.
        assert snapshot(source_account) == original_accounts
        assert snapshot(person) == original_people
        assert snapshot(household) == original_household
    assert {table.name: snapshot(table) for table in (raw_source_record, source_record, source_sync_state)} == history
