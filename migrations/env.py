import os
from alembic import context
from family_os.db import create_db
from family_os.schema import metadata

config = context.config
url = os.environ.get("DATABASE_URL") or config.get_main_option("sqlalchemy.url")

if context.is_offline_mode():
    context.configure(url=url, target_metadata=metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_db(url)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=metadata, render_as_batch=engine.dialect.name == "sqlite")
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()
