"""
Add objectives, flashcards, and progress tracking to as_student_notes

Revision ID: 20251126_01
Revises: 20250930_01_allow_block_only_submissions
Create Date: 2025-11-26
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20251126_01'
down_revision = '20250930_01_allow_block_only_submissions'
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table('as_student_notes') as batch_op:
        batch_op.add_column(sa.Column('objectives', postgresql.JSON(astext_type=sa.Text()), nullable=True))
        batch_op.add_column(sa.Column('objective_flashcards', postgresql.JSON(astext_type=sa.Text()), nullable=True))
        batch_op.add_column(sa.Column('overall_flashcards', postgresql.JSON(astext_type=sa.Text()), nullable=True))
        batch_op.add_column(sa.Column('objective_progress', postgresql.JSON(astext_type=sa.Text()), nullable=True))


def downgrade():
    with op.batch_alter_table('as_student_notes') as batch_op:
        batch_op.drop_column('objective_progress')
        batch_op.drop_column('overall_flashcards')
        batch_op.drop_column('objective_flashcards')
        batch_op.drop_column('objectives')
