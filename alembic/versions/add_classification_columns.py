"""add classification columns to questions

Revision ID: add_classification_cols
Revises: add_embedding_cols
Create Date: 2026-01-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_classification_cols'
down_revision: Union[str, None] = 'add_embedding_cols'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add classification columns
    op.add_column('questions', sa.Column('subtopic', sa.String(255), nullable=True))
    op.add_column('questions', sa.Column('grade_level', sa.String(50), nullable=True))
    op.add_column('questions', sa.Column('cognitive_level', sa.String(50), nullable=True))
    op.add_column('questions', sa.Column('is_classified', sa.Boolean(), nullable=True, server_default='false'))
    
    # Add index on topic for filtering
    op.create_index(op.f('ix_questions_topic'), 'questions', ['topic'], unique=False)
    
    # Add index on is_classified for efficient querying
    op.create_index(op.f('ix_questions_is_classified'), 'questions', ['is_classified'], unique=False)


def downgrade() -> None:
    # Remove indexes
    op.drop_index(op.f('ix_questions_is_classified'), table_name='questions')
    op.drop_index(op.f('ix_questions_topic'), table_name='questions')
    
    # Remove columns
    op.drop_column('questions', 'is_classified')
    op.drop_column('questions', 'cognitive_level')
    op.drop_column('questions', 'grade_level')
    op.drop_column('questions', 'subtopic')
