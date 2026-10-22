"""T1 internal fictional pending decisions, task publication and immutable history."""
from alembic import op
from sqlalchemy import (MetaData, Table, Column, Text, Integer, BigInteger, Boolean, Date,
                        ForeignKeyConstraint, UniqueConstraint, CheckConstraint, Index)
revision = 'e41a9b720dc3'
down_revision = 'c35b79a12e04'
branch_labels = None
depends_on = None


def _tables():
    metadata = MetaData()
    Table('person', metadata, Column('household_id', Text), Column('id', Text))
    Table('source_account', metadata, Column('household_id', Text), Column('id', Text))
    Table('household_membership', metadata, Column('household_id', Text), Column('person_id', Text))

    # T1 internal fictional domain: evidence is private; task publication is independent.
    household_pending_item = Table('household_pending_item', metadata,
        Column('household_id', Text, primary_key=True), Column('id', Text, primary_key=True),
        Column('source_account_id', Text, nullable=False), Column('kind', Text, nullable=False),
        Column('step', Text), Column('supported', Boolean, nullable=False),
        Column('safety', Text, nullable=False), Column('supported_date', Date),
        Column('generation', Integer, nullable=False), Column('evidence_fingerprint', Text, nullable=False),
        Column('definition_version', Text, nullable=False), Column('resolution', Text, nullable=False),
        Column('revision', Integer, nullable=False),
        ForeignKeyConstraint(['household_id','source_account_id'], ['source_account.household_id','source_account.id']),
        CheckConstraint("kind in ('action','question','mixed-service','information','promotion')", name='valid_pending_kind'),
        CheckConstraint("step is null or step in ('school-session','home-visit')", name='valid_pending_step'),
        CheckConstraint("safety in ('clear','unknown','high-risk')", name='valid_pending_safety'),
        CheckConstraint("resolution in ('unresolved','accepted')", name='valid_pending_resolution'),
        CheckConstraint("(supported = false and supported_date is null) or (supported = true and step is not null and kind in ('action','mixed-service'))", name='valid_pending_support'),
        CheckConstraint('revision between 1 and 1000000 and revision = CAST(revision AS INTEGER) and generation between 1 and 1000000 and generation = CAST(generation AS INTEGER)', name='valid_pending_versions'),
        CheckConstraint('length(evidence_fingerprint) = 64 and length(definition_version) between 1 and 64', name='bounded_pending_definition'))
    pending_member_right = Table('pending_member_right', metadata,
        Column('household_id', Text, primary_key=True), Column('pending_id', Text, primary_key=True),
        Column('person_id', Text, primary_key=True), Column('state', Text, nullable=False),
        Column('can_read', Boolean, nullable=False), Column('can_review', Boolean, nullable=False),
        Column('can_publish', Boolean, nullable=False), Column('revision', Integer, nullable=False),
        Column('membership_revision', Integer, nullable=False), Column('reviewed', Boolean, nullable=False),
        Column('disposition', Text, nullable=False),
        ForeignKeyConstraint(['household_id','pending_id'], ['household_pending_item.household_id','household_pending_item.id']),
        ForeignKeyConstraint(['household_id','person_id'], ['household_membership.household_id','household_membership.person_id']),
        CheckConstraint("state in ('allowed','revoked')", name='valid_pending_right_state'),
        CheckConstraint('revision > 0 and revision = CAST(revision AS INTEGER) and membership_revision > 0', name='valid_pending_right_revision'),
        CheckConstraint('(can_review = false and can_publish = false) or can_read = true', name='valid_pending_right_scope'),
        CheckConstraint("disposition in ('active','deferred','needs-information')", name='valid_pending_disposition'))
    pending_task_publication = Table('pending_task_publication', metadata,
        Column('household_id', Text, primary_key=True), Column('pending_id', Text, primary_key=True),
        Column('person_id', Text, primary_key=True), Column('state', Text, nullable=False),
        Column('can_read', Boolean, nullable=False), Column('can_edit', Boolean, nullable=False),
        Column('can_history', Boolean, nullable=False), Column('revision', Integer, nullable=False),
        Column('membership_revision', Integer, nullable=False),
        ForeignKeyConstraint(['household_id','pending_id'], ['household_pending_item.household_id','household_pending_item.id']),
        ForeignKeyConstraint(['household_id','person_id'], ['household_membership.household_id','household_membership.person_id']),
        CheckConstraint("state in ('allowed','revoked')", name='valid_task_plan_state'),
        CheckConstraint('revision > 0 and revision = CAST(revision AS INTEGER) and membership_revision > 0', name='valid_task_plan_revision'),
        CheckConstraint('(can_edit = false and can_history = false) or can_read = true', name='valid_task_plan_scope'))
    household_task = Table('household_task', metadata,
        Column('household_id', Text, primary_key=True), Column('id', Text, primary_key=True),
        Column('pending_id', Text, nullable=False), Column('step', Text, nullable=False),
        Column('assignee_kind', Text, nullable=False), Column('assignee_id', Text),
        Column('status', Text, nullable=False), Column('approved_date', Date),
        Column('revision', Integer, nullable=False), Column('created_at', BigInteger, nullable=False),
        Column('accepted_generation', Integer, nullable=False), Column('accepted_fingerprint', Text, nullable=False),
        Column('accepted_definition', Text, nullable=False),
        ForeignKeyConstraint(['household_id','pending_id'], ['household_pending_item.household_id','household_pending_item.id']),
        ForeignKeyConstraint(['household_id','assignee_id'], ['person.household_id','person.id']),
        UniqueConstraint('household_id','pending_id', name='uq_task_pending_identity'),
        CheckConstraint("step in ('school-session','home-visit')", name='valid_task_step'),
        CheckConstraint("(assignee_kind = 'joint' and assignee_id is null) or (assignee_kind = 'person' and assignee_id is not null)", name='valid_task_assignee'),
        CheckConstraint("status in ('pending','completed')", name='valid_task_status'),
        CheckConstraint('revision between 1 and 1000000 and revision = CAST(revision AS INTEGER) and accepted_generation > 0 and created_at > 0', name='valid_task_revision'),
        CheckConstraint('length(accepted_fingerprint) = 64 and length(accepted_definition) between 1 and 64', name='bounded_task_provenance'))
    task_member_grant = Table('task_member_grant', metadata,
        Column('household_id', Text, primary_key=True), Column('task_id', Text, primary_key=True),
        Column('person_id', Text, primary_key=True), Column('state', Text, nullable=False),
        Column('can_read', Boolean, nullable=False), Column('can_edit', Boolean, nullable=False),
        Column('can_history', Boolean, nullable=False), Column('revision', Integer, nullable=False),
        Column('membership_revision', Integer, nullable=False),
        ForeignKeyConstraint(['household_id','task_id'], ['household_task.household_id','household_task.id']),
        ForeignKeyConstraint(['household_id','person_id'], ['household_membership.household_id','household_membership.person_id']),
        CheckConstraint("state in ('allowed','revoked')", name='valid_task_grant_state'),
        CheckConstraint('revision > 0 and revision = CAST(revision AS INTEGER) and membership_revision > 0', name='valid_task_grant_revision'),
        CheckConstraint('(can_edit = false and can_history = false) or can_read = true', name='valid_task_grant_scope'))
    task_domain_event = Table('task_domain_event', metadata,
        Column('id', Text, primary_key=True), Column('household_id', Text, nullable=False),
        Column('actor_id', Text, nullable=False), Column('request_id', Text, nullable=False),
        Column('intent_hash', Text, nullable=False), Column('operation', Text, nullable=False),
        Column('pending_id', Text), Column('pending_revision', Integer),
        Column('task_id', Text), Column('task_revision', Integer),
        Column('generation', Integer), Column('evidence_fingerprint', Text), Column('definition_version', Text),
        Column('step', Text), Column('assignee_kind', Text), Column('assignee_id', Text),
        Column('status', Text), Column('approved_date', Date),
        Column('outcome', Text, nullable=False), Column('created_at', BigInteger, nullable=False),
        ForeignKeyConstraint(['household_id','actor_id'], ['person.household_id','person.id']),
        ForeignKeyConstraint(['household_id','assignee_id'], ['person.household_id','person.id']),
        ForeignKeyConstraint(['household_id','pending_id'], ['household_pending_item.household_id','household_pending_item.id']),
        ForeignKeyConstraint(['household_id','task_id'], ['household_task.household_id','household_task.id']),
        UniqueConstraint('household_id','actor_id','request_id', name='uq_task_domain_request'),
        UniqueConstraint('household_id','pending_id','pending_revision', name='uq_pending_event_revision'),
        UniqueConstraint('household_id','task_id','task_revision', name='uq_task_event_revision'),
        CheckConstraint("(operation in ('review','defer','needs-information') and pending_id is not null and pending_revision is not null and task_id is null and task_revision is null) or (operation = 'accept' and pending_id is not null and pending_revision is not null and task_id is not null and task_revision = 1) or (operation = 'edit' and pending_id is null and pending_revision is null and task_id is not null and task_revision is not null)", name='valid_task_event_scope'),
        CheckConstraint("outcome = 'committed'", name='valid_task_event_outcome'),
        CheckConstraint('length(intent_hash) = 64 and created_at > 0', name='bounded_task_event'))
    Index('idx_pending_household', household_pending_item.c.household_id, household_pending_item.c.resolution, household_pending_item.c.id)
    Index('idx_task_household', household_task.c.household_id, household_task.c.status, household_task.c.id)
    Index('idx_task_event_actor', task_domain_event.c.household_id, task_domain_event.c.actor_id, task_domain_event.c.created_at)

    return (household_pending_item, pending_member_right, pending_task_publication,
            household_task, task_member_grant, task_domain_event)


def upgrade():
    for table in _tables():
        table.create(op.get_bind())


def downgrade():
    for name in ('task_domain_event','task_member_grant','household_task',
                 'pending_task_publication','pending_member_right','household_pending_item'):
        op.drop_table(name)
