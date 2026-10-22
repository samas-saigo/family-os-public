import json
from pathlib import Path
from sqlalchemy import select
from family_os.cli import main
from family_os.connectors import FixtureConnector
from family_os.ingestion import ingest, IngestionError
from family_os.registry import load_registry
from family_os.schema import source_record
import pytest

ROOT = Path(__file__).parents[1]

def test_fixture_pagination_and_restart(engine):
    load_registry(engine, ROOT / "config/household.demo.yaml")
    connector = FixtureConnector(ROOT / "fixtures/messages.json", page_size=1)
    result = ingest(engine, "demo_household", "demo_mailbox", connector)
    assert (result.pages, result.inserted) == (2, 2)
    restarted = ingest(engine, "demo_household", "demo_mailbox",
                       FixtureConnector(ROOT / "fixtures/messages.json", page_size=1))
    assert restarted.inserted == restarted.updated == 0
    with engine.connect() as connection:
        assert len(connection.execute(select(source_record)).all()) == 2

def test_cli_demo_and_household_scoped_status(engine, capsys):
    assert main(["register", str(ROOT / "config/household.demo.yaml")]) == 0
    assert main(["ingest-fixture", "--household", "demo_household", "--account", "demo_mailbox",
                 "--file", str(ROOT / "fixtures/messages.json")]) == 0
    capsys.readouterr()
    assert main(["status", "--household", "other"]) == 0
    assert json.loads(capsys.readouterr().out) == {"source_account": 0, "raw_source_record": 0, "source_record": 0}
    assert main(["status", "--household", "demo_household"]) == 0
    assert json.loads(capsys.readouterr().out)["source_record"] == 2

def test_shared_account_can_ingest(engine):
    load_registry(engine, ROOT / "config/household.demo.yaml")
    assert ingest(engine, "demo_household", "demo_shared",
                  FixtureConnector(ROOT / "fixtures/messages.json")).inserted == 2

def test_pagination_limit_can_resume(engine):
    load_registry(engine, ROOT / "config/household.demo.yaml")
    connector = FixtureConnector(ROOT / "fixtures/messages.json", page_size=1)
    with pytest.raises(IngestionError, match="Page limit"):
        ingest(engine, "demo_household", "demo_mailbox", connector, max_pages=1)
    assert ingest(engine, "demo_household", "demo_mailbox", connector).inserted == 1
