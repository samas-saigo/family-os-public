"""Durable household authorization only; no source/history rewrites."""
from alembic import op
from sqlalchemy import (MetaData, Table, Column, Text, Boolean, Integer, DateTime,
                        ForeignKeyConstraint, UniqueConstraint, CheckConstraint, Index)

revision = '4e82a1c70d39'
down_revision = '913feab82c07'
branch_labels = None
depends_on = None


def _tables():
    m = MetaData()
    # FK target stubs are not created or changed by this migration.
    for name, columns in (('household', ('id',)), ('person', ('household_id', 'id')),
                          ('source_account', ('household_id', 'id'))):
        Table(name, m, *(Column(c, Text) for c in columns))
    household_membership = Table('household_membership', m,
        Column('household_id', Text, primary_key=True), Column('person_id', Text, primary_key=True),
        Column('state', Text, nullable=False), Column('revision', Integer, nullable=False),
        ForeignKeyConstraint(['household_id', 'person_id'], ['person.household_id', 'person.id']),
        CheckConstraint("state in ('allowed','revoked')", name='valid_membership_state'),
        CheckConstraint('revision > 0 and revision = CAST(revision AS INTEGER)', name='valid_membership_revision'))
    source_read_grant = Table('source_read_grant', m,
        Column('household_id', Text, primary_key=True), Column('source_account_id', Text, primary_key=True),
        Column('person_id', Text, primary_key=True), Column('state', Text, nullable=False),
        Column('observations', Boolean, nullable=False), Column('security', Boolean, nullable=False),
        Column('revision', Integer, nullable=False), Column('membership_revision', Integer, nullable=False),
        ForeignKeyConstraint(['household_id', 'source_account_id'], ['source_account.household_id', 'source_account.id']),
        ForeignKeyConstraint(['household_id', 'person_id'], ['household_membership.household_id', 'household_membership.person_id']),
        CheckConstraint("state in ('allowed','revoked')", name='valid_source_grant_state'),
        CheckConstraint('revision > 0 and revision = CAST(revision AS INTEGER)', name='valid_source_grant_revision'),
        CheckConstraint('membership_revision > 0', name='valid_source_membership_binding'))
    publication_scope = Table('publication_scope', m,
        Column('household_id', Text, primary_key=True), Column('publication_key', Text, primary_key=True),
        Column('approved', Boolean, nullable=False),
        ForeignKeyConstraint(['household_id'], ['household.id']),
        CheckConstraint('length(publication_key) between 1 and 64', name='bounded_publication_key'))
    publication_read_grant = Table('publication_read_grant', m,
        Column('household_id', Text, primary_key=True), Column('publication_key', Text, primary_key=True),
        Column('person_id', Text, primary_key=True), Column('state', Text, nullable=False),
        Column('revision', Integer, nullable=False), Column('membership_revision', Integer, nullable=False),
        ForeignKeyConstraint(['household_id', 'publication_key'], ['publication_scope.household_id', 'publication_scope.publication_key']),
        ForeignKeyConstraint(['household_id', 'person_id'], ['household_membership.household_id', 'household_membership.person_id']),
        CheckConstraint("state in ('allowed','revoked')", name='valid_publication_grant_state'),
        CheckConstraint('revision > 0 and revision = CAST(revision AS INTEGER)', name='valid_publication_grant_revision'),
        CheckConstraint('membership_revision > 0', name='valid_publication_membership_binding'))
    authorization_audit = Table('authorization_audit', m,
        Column('id', Text, primary_key=True), Column('household_id', Text, nullable=False),
        Column('actor_id', Text, nullable=False), Column('recipient_id', Text, nullable=False),
        Column('kind', Text, nullable=False), Column('scope_key', Text, nullable=False),
        Column('source_account_id', Text), Column('publication_key', Text),
        Column('request_id', Text, nullable=False), Column('intent_hash', Text, nullable=False),
        Column('old_state', Text), Column('new_state', Text, nullable=False),
        Column('old_observations', Boolean, nullable=False), Column('old_security', Boolean, nullable=False),
        Column('new_observations', Boolean, nullable=False), Column('new_security', Boolean, nullable=False),
        Column('old_revision', Integer, nullable=False), Column('revision', Integer, nullable=False),
        Column('old_membership_revision', Integer, nullable=False), Column('new_membership_revision', Integer, nullable=False),
        Column('outcome', Text, nullable=False), Column('created_at', DateTime(timezone=True), nullable=False),
        ForeignKeyConstraint(['household_id', 'actor_id'], ['person.household_id', 'person.id']),
        ForeignKeyConstraint(['household_id', 'recipient_id'], ['person.household_id', 'person.id']),
        ForeignKeyConstraint(['household_id', 'source_account_id'], ['source_account.household_id', 'source_account.id']),
        ForeignKeyConstraint(['household_id', 'publication_key'], ['publication_scope.household_id', 'publication_scope.publication_key']),
        UniqueConstraint('household_id', 'actor_id', 'request_id', name='uq_authorization_request'),
        UniqueConstraint('household_id', 'kind', 'scope_key', 'recipient_id', 'revision', name='uq_authorization_scope_revision'),
        CheckConstraint("(kind = 'membership' and scope_key = 'membership' and source_account_id is null and publication_key is null) or (kind = 'source' and source_account_id is not null and scope_key = source_account_id and publication_key is null) or (kind = 'publication' and publication_key is not null and scope_key = publication_key and source_account_id is null)", name='valid_authorization_audit_scope'),
        CheckConstraint("(old_state is null or old_state in ('allowed','revoked')) and new_state in ('allowed','revoked')", name='valid_authorization_audit_state'),
        CheckConstraint("outcome = 'committed'", name='valid_authorization_audit_outcome'),
        CheckConstraint('old_revision >= 0 and revision = old_revision + 1', name='valid_authorization_audit_revision'))
    Index('idx_authorization_audit_scope', authorization_audit.c.household_id,
          authorization_audit.c.kind, authorization_audit.c.scope_key, authorization_audit.c.revision)
    return (household_membership, source_read_grant, publication_scope,
            publication_read_grant, authorization_audit)


def upgrade():
    for table in _tables():
        table.create(op.get_bind())


def downgrade():
    for name in ('authorization_audit', 'publication_read_grant', 'publication_scope',
                 'source_read_grant', 'household_membership'):
        op.drop_table(name)
