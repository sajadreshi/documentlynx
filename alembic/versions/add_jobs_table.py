"""add jobs table for tracking processing status

Revision ID: add_jobs_table
Revises: add_classification_cols
Create Date: 2026-02-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = 'add_jobs_table'
down_revision: Union[str, None] = 'add_classification_cols'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create jobs table
    op.create_table(
        'jobs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', sa.String(255), nullable=False, index=True),
        sa.Column('document_url', sa.Text(), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='queued', index=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('document_id', UUID(as_uuid=True), sa.ForeignKey('documents.id', ondelete='SET NULL'), nullable=True),
        sa.Column('question_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('jobs')
