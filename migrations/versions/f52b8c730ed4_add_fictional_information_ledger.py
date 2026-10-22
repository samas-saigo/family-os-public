"""I5 additive bounded fictional producer ledger; no provenance rewrites."""
from alembic import op
from sqlalchemy import MetaData, Table, Column, Text, Integer, ForeignKeyConstraint, CheckConstraint
revision = 'f52b8c730ed4'
down_revision = 'e41a9b720dc3'
branch_labels = None
depends_on = None


def _table():
    metadata = MetaData()
    Table('source_account', metadata, Column('household_id', Text), Column('id', Text))
    Table('household_pending_item', metadata, Column('household_id', Text), Column('id', Text))
    # I5 opt-in fictional producer history, not another Pending/Task store.
    fictional_information_revision = Table('fictional_information_revision', metadata,
        Column('household_id', Text, primary_key=True), Column('source_account_id', Text, primary_key=True),
        Column('record_id', Text, primary_key=True), Column('generation', Integer, primary_key=True),
        Column('evidence_fingerprint', Text, nullable=False), Column('intent_hash', Text, nullable=False),
        Column('plan_hash', Text, nullable=False), Column('definition_version', Text, nullable=False),
        Column('evidence_json', Text, nullable=False), Column('origin', Text, nullable=False), Column('destination', Text, nullable=False),
        Column('effect', Text, nullable=False), Column('pending_id', Text),
        ForeignKeyConstraint(['household_id','source_account_id'], ['source_account.household_id','source_account.id']),
        ForeignKeyConstraint(['household_id','pending_id'], ['household_pending_item.household_id','household_pending_item.id']),
        CheckConstraint('generation between 1 and 1000 and generation = CAST(generation AS INTEGER)', name='valid_fictional_information_generation'),
        CheckConstraint('length(record_id) between 4 and 35 and length(evidence_fingerprint) = 64 and length(intent_hash) = 64 and length(plan_hash) = 64', name='bounded_fictional_information_identity'),
        CheckConstraint('length(definition_version) between 1 and 64 and length(evidence_json) between 1 and 1024', name='bounded_fictional_information_evidence'),
        CheckConstraint("origin = 'trusted-fictional-fixture'", name='valid_fictional_information_origin'),
        CheckConstraint("destination in ('pending','security-held','unassessed','information','promotion','abstained')", name='valid_fictional_information_destination'),
        CheckConstraint("effect in ('created','updated','recorded','blocked','accepted-history-only')", name='valid_fictional_information_effect'))
    return fictional_information_revision


def upgrade():
    _table().create(op.get_bind())


def downgrade():
    op.drop_table("fictional_information_revision")
