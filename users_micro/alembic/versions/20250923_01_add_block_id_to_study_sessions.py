"""Add block_id column to as_study_sessions (idempotent)

Revision ID: 20250923_01
Revises:
Create Date: 2025-09-23

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import reflection

revision = '20250923_01'
down_revision = None  # First migration for this microservice
branch_labels = None
depends_on = None

def column_exists(table_name: str, column_name: str, bind) -> bool:
    inspector = reflection.Inspector.from_engine(bind)
    return column_name in [c['name'] for c in inspector.get_columns(table_name)]

def upgrade():
    bind = op.get_bind()
    if not column_exists('as_study_sessions', 'block_id', bind):
        op.add_column('as_study_sessions', sa.Column('block_id', sa.Integer(), nullable=True))
        try:
            op.create_foreign_key(
                'fk_as_study_sessions_block_id',
                'as_study_sessions', 'as_course_blocks',
                ['block_id'], ['id'], ondelete='SET NULL'
            )
        except Exception:
            pass


def downgrade():
    bind = op.get_bind()
    if column_exists('as_study_sessions', 'block_id', bind):
        try:
            op.drop_constraint('fk_as_study_sessions_block_id', 'as_study_sessions', type_='foreignkey')
        except Exception:
            pass
        op.drop_column('as_study_sessions', 'block_id')
