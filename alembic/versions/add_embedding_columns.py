"""add embedding columns to questions

Revision ID: add_embedding_cols
Revises: 8d6510954c4d
Create Date: 2026-01-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_embedding_cols'
down_revision: Union[str, None] = '8d6510954c4d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgvector extension (if not already enabled)
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    
    # Add embedding column (384 dimensions for all-MiniLM-L6-v2)
    # Using raw SQL to avoid dependency on pgvector Python package at migration time
    op.execute('ALTER TABLE questions ADD COLUMN embedding vector(384)')
    
    # Add is_embedded flag to track which questions have embeddings
    op.add_column('questions', sa.Column('is_embedded', sa.Boolean(), nullable=True, server_default='false'))
    
    # Create index on is_embedded for efficient querying
    op.create_index(op.f('ix_questions_is_embedded'), 'questions', ['is_embedded'], unique=False)
    
    # Optional: Create an IVFFlat index for faster similarity search at scale
    # Uncomment if you have many questions (10k+)
    # op.execute('''
    #     CREATE INDEX questions_embedding_idx ON questions 
    #     USING ivfflat (embedding vector_cosine_ops)
    #     WITH (lists = 100)
    # ''')


def downgrade() -> None:
    # Remove index
    op.drop_index(op.f('ix_questions_is_embedded'), table_name='questions')
    
    # Remove columns
    op.drop_column('questions', 'is_embedded')
    op.execute('ALTER TABLE questions DROP COLUMN embedding')
    
    # Note: We don't drop the vector extension as other tables may use it
