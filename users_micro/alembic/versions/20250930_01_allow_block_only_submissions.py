"""Allow block-only submissions - make lesson_id nullable

Revision ID: 20250930_01
Revises: 20250923_01
Create Date: 2025-09-30

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import reflection

revision = '20250930_01'
down_revision = '20250923_01'
branch_labels = None
depends_on = None

def constraint_exists(constraint_name: str, bind) -> bool:
    """Check if a constraint exists in the database"""
    inspector = reflection.Inspector.from_engine(bind)
    # Check all tables for the constraint
    for table_name in inspector.get_table_names():
        constraints = inspector.get_check_constraints(table_name)
        if any(c['name'] == constraint_name for c in constraints):
            return True
    return False

def upgrade():
    bind = op.get_bind()
    
    # Check if as_ai_submissions table exists
    inspector = reflection.Inspector.from_engine(bind)
    if 'as_ai_submissions' in inspector.get_table_names():
        # 1. Make lesson_id nullable on as_ai_submissions
        op.alter_column(
            'as_ai_submissions',
            'lesson_id',
            existing_type=sa.Integer(),
            nullable=True
        )

        # 2. Add a CHECK constraint enforcing at least one of lesson_id or block_id
        if not constraint_exists('ck_as_ai_submissions_lesson_or_block', bind):
            op.execute(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.table_constraints 
                        WHERE constraint_name = 'ck_as_ai_submissions_lesson_or_block'
                    ) THEN
                        ALTER TABLE as_ai_submissions
                        ADD CONSTRAINT ck_as_ai_submissions_lesson_or_block
                        CHECK ((lesson_id IS NOT NULL) OR (block_id IS NOT NULL));
                    END IF;
                END $$;
                """
            )

def downgrade():
    bind = op.get_bind()
    
    # Drop CHECK constraint if exists
    if constraint_exists('ck_as_ai_submissions_lesson_or_block', bind):
        op.execute(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.table_constraints 
                    WHERE constraint_name = 'ck_as_ai_submissions_lesson_or_block'
                ) THEN
                    ALTER TABLE as_ai_submissions
                    DROP CONSTRAINT ck_as_ai_submissions_lesson_or_block;
                END IF;
            END $$;
            """
        )

    # Revert lesson_id to NOT NULL (only if your data guarantees backfill)
    # WARNING: This may fail if there are NULL values in lesson_id
    op.alter_column(
        'as_ai_submissions',
        'lesson_id',
        existing_type=sa.Integer(),
        nullable=False
    )