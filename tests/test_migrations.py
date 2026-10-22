from pathlib import Path
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

def test_upgrade_downgrade_upgrade(engine):
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    assert "raw_source_record" in inspect(engine).get_table_names()
    command.check(config)
    command.downgrade(config, "base")
    assert inspect(engine).get_table_names() == ["alembic_version"]
    command.upgrade(config, "head")
    assert "source_sync_state" in inspect(engine).get_table_names()
