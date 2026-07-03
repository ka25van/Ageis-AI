"""add_memory_tables

Revision ID: f3a1b2c3d4e5
Revises: e290d78de314
Create Date: 2026-07-03 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import pgvector.sqlalchemy.vector

revision: str = 'f3a1b2c3d4e5'
down_revision: Union[str, None] = 'e290d78de314'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('long_term_memory',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('key', sa.String(length=255), nullable=False),
        sa.Column('value', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_long_term_memory')),
    )
    op.create_index(op.f('ix_long_term_memory_user_id'), 'long_term_memory', ['user_id'], unique=False)

    op.create_table('semantic_memory',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('embedding', pgvector.sqlalchemy.vector.VECTOR(dim=768), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_semantic_memory')),
    )
    op.create_index('ix_semantic_memory_embedding', 'semantic_memory', ['embedding'], unique=False, postgresql_using='ivfflat')


def downgrade() -> None:
    op.drop_index('ix_semantic_memory_embedding', table_name='semantic_memory', postgresql_using='ivfflat')
    op.drop_table('semantic_memory')
    op.drop_index(op.f('ix_long_term_memory_user_id'), table_name='long_term_memory')
    op.drop_table('long_term_memory')
