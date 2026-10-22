"""I8 personal disposition and bounded private event reason; preserve every old row."""
from alembic import op
import sqlalchemy as sa

revision = '063c9d841fe5'
down_revision = 'f52b8c730ed4'
branch_labels = None
depends_on = None

OLD_SCOPE = "(operation in ('review','defer','needs-information') and pending_id is not null and pending_revision is not null and task_id is null and task_revision is null) or (operation = 'accept' and pending_id is not null and pending_revision is not null and task_id is not null and task_revision = 1) or (operation = 'edit' and pending_id is null and pending_revision is null and task_id is not null and task_revision is not null)"
NEW_SCOPE = OLD_SCOPE.replace("'needs-information')", "'needs-information','not-applicable','resume')")
REASON = "(operation = 'not-applicable' and personal_reason is not null and personal_reason in ('not-my-responsibility','not-participating','personal-judgment')) or (operation <> 'not-applicable' and personal_reason is null)"


def _transaction():
    connection = op.get_bind()
    if connection.dialect.name == 'sqlite':
        # Alembic's context alone does not begin DDL transactions in sqlite3 legacy
        # mode. Never use autocommit_block: both leaf rebuilds AND version update
        # must remain in this same physical transaction, managed by env.py.
        driver = connection.connection.driver_connection
        if not driver.in_transaction:
            connection.exec_driver_sql('BEGIN IMMEDIATE')
        if not driver.in_transaction:
            raise RuntimeError('I8 requires an active SQLite migration transaction')
    return connection


def upgrade():
    _transaction()
    with op.batch_alter_table('pending_member_right') as batch:
        batch.drop_constraint('valid_pending_disposition', type_='check')
        batch.create_check_constraint('valid_pending_disposition',
            "disposition in ('active','deferred','needs-information','not-applicable')")
    with op.batch_alter_table('task_domain_event') as batch:
        batch.add_column(sa.Column('personal_reason', sa.Text(), nullable=True))
        batch.drop_constraint('valid_task_event_scope', type_='check')
        batch.create_check_constraint('valid_task_event_scope', NEW_SCOPE)
        batch.create_check_constraint('valid_personal_reason', REASON)
    if op.get_bind().dialect.name == 'sqlite' and op.get_bind().exec_driver_sql('PRAGMA foreign_key_check').first():
        raise RuntimeError('I8 foreign-key verification failed')


def downgrade():
    connection = _transaction()
    # Refuse even after RESUME returned the current cache to active. History is
    # never deleted, coerced or exported away to make a destructive downgrade fit.
    if (connection.execute(sa.text("SELECT 1 FROM task_domain_event WHERE operation IN ('not-applicable','resume') OR personal_reason IS NOT NULL LIMIT 1")).first()
            or connection.execute(sa.text("SELECT 1 FROM pending_member_right WHERE disposition = 'not-applicable' LIMIT 1")).first()):
        raise RuntimeError('I8 history/state exists; retain this revision and preserve audit history')
    with op.batch_alter_table('task_domain_event') as batch:
        batch.drop_constraint('valid_personal_reason', type_='check')
        batch.drop_constraint('valid_task_event_scope', type_='check')
        batch.create_check_constraint('valid_task_event_scope', OLD_SCOPE)
        batch.drop_column('personal_reason')
    with op.batch_alter_table('pending_member_right') as batch:
        batch.drop_constraint('valid_pending_disposition', type_='check')
        batch.create_check_constraint('valid_pending_disposition',
            "disposition in ('active','deferred','needs-information')")
