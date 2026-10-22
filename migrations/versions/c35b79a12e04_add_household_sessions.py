"""Durable internal sessions and protected lifecycle audit."""
from alembic import op
from sqlalchemy import (MetaData, Table, Column, Text, Integer, BigInteger, Boolean,
                        Index, ForeignKeyConstraint, UniqueConstraint, CheckConstraint)
revision = 'c35b79a12e04'
down_revision = '8a421d6c09be'
branch_labels = None
depends_on = None


def _tables():
    metadata = MetaData()
    Table('person', metadata, Column('household_id', Text), Column('id', Text))
    Table('household_membership', metadata, Column('household_id', Text), Column('person_id', Text))
    external_identity_binding = Table('external_identity_binding', metadata,
        Column('issuer', Text), Column('subject', Text), Column('household_id', Text), Column('person_id', Text))
    Index('uq_identity_binding_session_scope', external_identity_binding.c.issuer,
          external_identity_binding.c.subject, external_identity_binding.c.household_id,
          external_identity_binding.c.person_id, unique=True)

    household_session = Table('household_session', metadata,
        Column('id', Text, primary_key=True), Column('household_id', Text, nullable=False),
        Column('person_id', Text, nullable=False), Column('issuer', Text, nullable=False),
        Column('subject', Text, nullable=False), Column('secret_hash', Text, nullable=False, unique=True),
        Column('binding_revision', Integer, nullable=False), Column('membership_revision', Integer, nullable=False),
        Column('revision', Integer, nullable=False), Column('revoked', Boolean, nullable=False),
        *[Column(n, BigInteger, nullable=False) for n in ('created_at','last_active','absolute_expiry','idle_expiry')],
        ForeignKeyConstraint(['issuer','subject','household_id','person_id'],
            ['external_identity_binding.issuer','external_identity_binding.subject','external_identity_binding.household_id','external_identity_binding.person_id']),
        ForeignKeyConstraint(['household_id','person_id'], ['household_membership.household_id','household_membership.person_id']),
        UniqueConstraint('household_id','person_id','id', name='uq_session_actor_scope'),
        CheckConstraint('length(secret_hash) = 64', name='bounded_session_hash'),
        CheckConstraint('revision > 0 and revision = CAST(revision AS INTEGER) and binding_revision > 0 and binding_revision = CAST(binding_revision AS INTEGER) and membership_revision > 0 and membership_revision = CAST(membership_revision AS INTEGER)', name='valid_session_revisions'),
        CheckConstraint('created_at > 0 and created_at <= last_active and last_active < absolute_expiry and last_active < idle_expiry and idle_expiry <= absolute_expiry and absolute_expiry <= created_at + 86400', name='valid_session_times'))
    Index('idx_session_member', household_session.c.household_id, household_session.c.person_id)
    session_audit = Table('session_audit', metadata,
        Column('id', Text, primary_key=True), Column('household_id', Text, nullable=False),
        Column('actor_id', Text, nullable=False), Column('person_id', Text, nullable=False),
        Column('session_id', Text), Column('previous_session_id', Text), Column('request_id', Text, nullable=False),
        Column('intent_hash', Text, nullable=False), Column('event', Text, nullable=False),
        Column('outcome', Text, nullable=False), Column('created_at', BigInteger, nullable=False),
        ForeignKeyConstraint(['household_id','actor_id'], ['person.household_id','person.id']),
        ForeignKeyConstraint(['household_id','person_id'], ['person.household_id','person.id']),
        ForeignKeyConstraint(['household_id','person_id','session_id'], ['household_session.household_id','household_session.person_id','household_session.id']),
        ForeignKeyConstraint(['household_id','person_id','previous_session_id'], ['household_session.household_id','household_session.person_id','household_session.id']),
        UniqueConstraint('household_id','actor_id','request_id', name='uq_session_request'),
        CheckConstraint("event in ('establish','logout','rotate','revoke_all')", name='valid_session_event'),
        CheckConstraint("outcome = 'committed'", name='valid_session_outcome'))
    return household_session, session_audit


def upgrade():
    op.create_index('uq_identity_binding_session_scope', 'external_identity_binding',
                    ['issuer','subject','household_id','person_id'], unique=True)
    for table in _tables():
        table.create(op.get_bind())


def downgrade():
    op.drop_table('session_audit')
    op.drop_table('household_session')
    op.drop_index('uq_identity_binding_session_scope', table_name='external_identity_binding')
