"""fix_embedding_dimension

Align document_chunks.embedding dimension with actual nomic-embed-text output (768).
Initial migration incorrectly created the column as VECTOR(1536).

Revision ID: a6b7c8d9e0f1
Revises: f3a1b2c3d4e5
Create Date: 2026-07-03 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import vector

revision: str = "a6b7c8d9e0f1"
down_revision: Union[str, None] = "f3a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE document_chunks ALTER COLUMN embedding TYPE vector(768) USING embedding::vector(768)"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE document_chunks ALTER COLUMN embedding TYPE vector(1536) USING embedding::vector(1536)"
    )
