"""Dialect-specific upsert kept outside domain and connector layers."""
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.dialects.postgresql import insert as postgres_insert

def insert_for(connection, table):
    if connection.dialect.name == "sqlite":
        return sqlite_insert(table)
    if connection.dialect.name == "postgresql":
        return postgres_insert(table)
    raise ValueError("Supported databases: SQLite and PostgreSQL")

def upsert(connection, table, values, keys, update_fields):
    statement = insert_for(connection, table).values(**values)
    connection.execute(statement.on_conflict_do_update(
        index_elements=keys, set_={name: statement.excluded[name] for name in update_fields}))
