"""Offline PostgreSQL DDL validation even when a server is unavailable locally."""
from pathlib import Path
from io import StringIO
from alembic import command
from alembic.config import Config

def test_postgresql_migration_compiles(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://unused:unused@localhost/unused")
    output = StringIO()
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"), output_buffer=output)
    command.upgrade(config, "head", sql=True)
    ddl = output.getvalue()
    assert "JSONB" in ddl
    assert "TIMESTAMP WITH TIME ZONE" in ddl
    assert "CREATE TABLE source_record" in ddl
    assert "FOREIGN KEY(household_id, person_owner_id)" in ddl
