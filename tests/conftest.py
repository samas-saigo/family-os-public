from pathlib import Path
import os
from uuid import uuid4
import pytest
from alembic import command
from alembic.config import Config
from family_os.db import create_db
from sqlalchemy import text
from sqlalchemy.engine import make_url

@pytest.fixture
def engine(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'test.sqlite3').as_posix()}"
    admin = None
    test_schema = None
    if os.environ.get("TEST_DATABASE_URL"):
        # Use only a dedicated disposable test database. Each test owns a unique schema.
        parsed = make_url(os.environ["TEST_DATABASE_URL"])
        if parsed.get_backend_name() != "postgresql":
            raise ValueError("TEST_DATABASE_URL must be PostgreSQL")
        admin = create_db(parsed)
        test_schema = "test_" + uuid4().hex
        with admin.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{test_schema}"'))
        url = parsed.update_query_dict({"options": f"-csearch_path={test_schema}"}).render_as_string(hide_password=False)
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    engine = None
    try:
        command.upgrade(config, "head")
        engine = create_db(url)
        yield engine
    finally:
        if engine is not None:
            engine.dispose()
        if admin is not None:
            with admin.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{test_schema}" CASCADE'))
            admin.dispose()
