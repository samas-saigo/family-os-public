"""Allow explicit domain abstention without relabeling analysis history."""
from contextlib import contextmanager
from alembic import op
import sqlalchemy as sa

revision = '7c19ad382ea1'
down_revision = '508ac6578044'
branch_labels = None
depends_on = None


@contextmanager
def sqlite_parent_rebuild():
    # SQLite rebuilds this parent table to change nullability. Referencing facts
    # retain all values/FKs; disable enforcement only on the migration connection.
    sqlite = op.get_bind().dialect.name == 'sqlite'
    if sqlite:
        with op.get_context().autocommit_block():
            op.execute('PRAGMA foreign_keys=OFF')
    try:
        yield
    finally:
        if sqlite:
            with op.get_context().autocommit_block():
                op.execute('PRAGMA foreign_keys=ON')
            if op.get_bind().exec_driver_sql('PRAGMA foreign_key_check').first():
                raise RuntimeError('Analysis migration foreign-key verification failed')


def upgrade():
    with sqlite_parent_rebuild(), op.batch_alter_table('source_analysis') as batch:
        batch.alter_column('domain_category', existing_type=sa.Text(), nullable=True)
        batch.alter_column('domain_subcategory', existing_type=sa.Text(), nullable=True)
        batch.create_check_constraint('valid_analysis_domain_state',
            '(domain_category is null and domain_subcategory is null and review_recommended = true) '
            'or (domain_category is not null and domain_subcategory is not null)')


def downgrade():
    # Never guess a domain, delete history, or rewrite an abstained result.
    if op.get_bind().execute(sa.text('SELECT 1 FROM source_analysis WHERE domain_category IS NULL '
                                    'OR domain_subcategory IS NULL LIMIT 1')).first():
        raise RuntimeError('Cannot downgrade while abstained analyses exist; preserve history and retain this revision')
    with sqlite_parent_rebuild(), op.batch_alter_table('source_analysis') as batch:
        batch.drop_constraint('valid_analysis_domain_state', type_='check')
        batch.alter_column('domain_category', existing_type=sa.Text(), nullable=False)
        batch.alter_column('domain_subcategory', existing_type=sa.Text(), nullable=False)
