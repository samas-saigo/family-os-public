"""Add versioned source analysis foundation"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision = '508ac6578044'
down_revision = 'a08cf2190da9'
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table('raw_source_record', schema=None) as batch_op:
        batch_op.create_index('uq_raw_source_analysis_identity', ['household_id', 'source_account_id', 'provider_object_id', 'id'], unique=True)

    with op.batch_alter_table('source_record', schema=None) as batch_op:
        batch_op.create_index('idx_source_record_analysis_pending', ['household_id', 'id', 'raw_record_id'], unique=False)
        batch_op.create_index('uq_source_record_analysis_identity', ['household_id', 'source_account_id', 'provider_object_id', 'id'], unique=True)

    op.create_table('source_analysis',
    sa.Column('id', sa.Text(), nullable=False),
    sa.Column('household_id', sa.Text(), nullable=False),
    sa.Column('source_account_id', sa.Text(), nullable=False),
    sa.Column('source_record_id', sa.Text(), nullable=False),
    sa.Column('raw_record_id', sa.Text(), nullable=False),
    sa.Column('provider_object_id', sa.Text(), nullable=False),
    sa.Column('analyzer_name', sa.Text(), nullable=False),
    sa.Column('analyzer_version', sa.Text(), nullable=False),
    sa.Column('taxonomy_version', sa.Text(), nullable=False),
    sa.Column('threshold_policy_version', sa.Text(), nullable=False),
    sa.Column('input_fingerprint', sa.Text(), nullable=False),
    sa.Column('definition_fingerprint', sa.Text(), nullable=False),
    sa.Column('relevance_label', sa.Text(), nullable=False),
    sa.Column('relevance_confidence', sa.Float(), nullable=False),
    sa.Column('domain_category', sa.Text(), nullable=False),
    sa.Column('domain_subcategory', sa.Text(), nullable=False),
    sa.Column('domain_confidence', sa.Float(), nullable=False),
    sa.Column('action_label', sa.Text(), nullable=False),
    sa.Column('action_confidence', sa.Float(), nullable=False),
    sa.Column('review_recommended', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("action_label in ('required','not_required','uncertain')", name='valid_analysis_action'),
    sa.CheckConstraint("relevance_label in ('relevant','irrelevant','uncertain')", name='valid_analysis_relevance'),
    sa.CheckConstraint('action_confidence >= 0 and action_confidence <= 1', name='valid_analysis_action_confidence'),
    sa.CheckConstraint('domain_confidence >= 0 and domain_confidence <= 1', name='valid_analysis_domain_confidence'),
    sa.CheckConstraint('relevance_confidence >= 0 and relevance_confidence <= 1', name='valid_analysis_relevance_confidence'),
    sa.ForeignKeyConstraint(['household_id', 'source_account_id', 'provider_object_id', 'raw_record_id'], ['raw_source_record.household_id', 'raw_source_record.source_account_id', 'raw_source_record.provider_object_id', 'raw_source_record.id'], ),
    sa.ForeignKeyConstraint(['household_id', 'source_account_id', 'provider_object_id', 'source_record_id'], ['source_record.household_id', 'source_record.source_account_id', 'source_record.provider_object_id', 'source_record.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('household_id', 'source_record_id', 'id', name='uq_source_analysis_fact_scope'),
    sa.UniqueConstraint('source_record_id', 'raw_record_id', 'analyzer_name', 'analyzer_version', 'taxonomy_version', 'threshold_policy_version', name='uq_source_analysis_definition')
    )
    with op.batch_alter_table('source_analysis', schema=None) as batch_op:
        batch_op.create_index('idx_source_analysis_history', ['household_id', 'source_record_id', 'created_at', 'id'], unique=False)

    op.create_table('analysis_fact',
    sa.Column('id', sa.Text(), nullable=False),
    sa.Column('analysis_id', sa.Text(), nullable=False),
    sa.Column('household_id', sa.Text(), nullable=False),
    sa.Column('source_record_id', sa.Text(), nullable=False),
    sa.Column('fact_name', sa.Text(), nullable=False),
    sa.Column('fact_value', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('confidence', sa.Float(), nullable=False),
    sa.Column('evidence_refs', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('ordinal', sa.Integer(), nullable=False),
    sa.Column('review_recommended', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint('confidence >= 0 and confidence <= 1', name='valid_fact_confidence'),
    sa.CheckConstraint('ordinal >= 0', name='valid_fact_ordinal'),
    sa.ForeignKeyConstraint(['household_id', 'source_record_id', 'analysis_id'], ['source_analysis.household_id', 'source_analysis.source_record_id', 'source_analysis.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('analysis_id', 'ordinal', name='uq_analysis_fact_ordinal')
    )

def downgrade():
    # Drop dependants before removing their composite foreign-key targets.
    op.drop_table('analysis_fact')
    op.drop_table('source_analysis')
    op.drop_index('uq_source_record_analysis_identity', table_name='source_record')
    op.drop_index('idx_source_record_analysis_pending', table_name='source_record')
    op.drop_index('uq_raw_source_analysis_identity', table_name='raw_source_record')
