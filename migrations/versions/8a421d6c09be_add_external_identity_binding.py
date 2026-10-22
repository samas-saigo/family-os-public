"""Exact external issuer/subject binding, without enrollment or grant changes."""
from alembic import op
import sqlalchemy as sa

revision = '8a421d6c09be'
down_revision = '4e82a1c70d39'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('external_identity_binding',
        sa.Column('issuer', sa.Text(), primary_key=True),
        sa.Column('subject', sa.Text(), primary_key=True),
        sa.Column('household_id', sa.Text(), nullable=False),
        sa.Column('person_id', sa.Text(), nullable=False),
        sa.Column('state', sa.Text(), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['household_id', 'person_id'], ['person.household_id', 'person.id']),
        sa.CheckConstraint('length(issuer) between 1 and 512', name='bounded_identity_issuer'),
        sa.CheckConstraint('length(subject) between 1 and 255', name='bounded_identity_subject'),
        sa.CheckConstraint("state in ('allowed','revoked')", name='valid_identity_binding_state'),
        sa.CheckConstraint('revision > 0 and revision = CAST(revision AS INTEGER)', name='valid_identity_binding_revision'))
    op.create_index('idx_identity_binding_person', 'external_identity_binding', ['household_id', 'person_id'])


def downgrade():
    op.drop_table('external_identity_binding')
