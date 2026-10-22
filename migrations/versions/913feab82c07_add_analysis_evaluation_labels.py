"""Add local human evaluation revisions without changing source/analysis history."""
from alembic import op
import sqlalchemy as sa

revision = '913feab82c07'
down_revision = '7c19ad382ea1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('analysis_evaluation_label',
        sa.Column('id', sa.Text(), primary_key=True),
        sa.Column('household_id', sa.Text(), nullable=False),
        sa.Column('analysis_id', sa.Text(), nullable=False),
        sa.Column('source_record_id', sa.Text(), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False),
        sa.Column('relevance_label', sa.Text(), nullable=False),
        sa.Column('domain_category', sa.Text()), sa.Column('domain_subcategory', sa.Text()),
        sa.Column('action_label', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['household_id', 'source_record_id', 'analysis_id'],
            ['source_analysis.household_id', 'source_analysis.source_record_id', 'source_analysis.id']),
        sa.UniqueConstraint('analysis_id', 'revision', name='uq_evaluation_label_revision'),
        sa.CheckConstraint('revision > 0 and revision = CAST(revision AS INTEGER)', name='valid_evaluation_revision'),
        sa.CheckConstraint("relevance_label in ('relevant','irrelevant','uncertain')", name='valid_evaluation_relevance'),
        sa.CheckConstraint("action_label in ('required','not_required','uncertain')", name='valid_evaluation_action'),
        sa.CheckConstraint('(domain_category is null and domain_subcategory is null) or (domain_category is not null and domain_subcategory is not null)', name='valid_evaluation_domain'))
    op.create_index('idx_evaluation_label_scope', 'analysis_evaluation_label',
                    ['household_id', 'source_record_id', 'analysis_id'])


def downgrade():
    # Only derived evaluation revisions are removed; no parent table alteration.
    op.drop_table('analysis_evaluation_label')
