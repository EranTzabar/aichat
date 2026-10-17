"""attachments

Revision ID: 9f4d2c7e1a35
Revises: 7c1e9a4b2d10
Create Date: 2026-10-17 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9f4d2c7e1a35'
down_revision: Union[str, Sequence[str], None] = '7c1e9a4b2d10'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('attachments',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('work_id', sa.Integer(), nullable=False),
    sa.Column('uploader_id', sa.Integer(), nullable=False),
    sa.Column('message_id', sa.Integer(), nullable=True),
    sa.Column('on_work', sa.Boolean(), nullable=False),
    sa.Column('filename', sa.String(length=255), nullable=False),
    sa.Column('content_type', sa.String(length=200), nullable=False),
    sa.Column('size', sa.BigInteger(), nullable=False),
    sa.Column('storage_key', sa.String(length=300), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['message_id'], ['messages.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['uploader_id'], ['users.id']),
    sa.ForeignKeyConstraint(['work_id'], ['works.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_attachments_message_id'), 'attachments', ['message_id'], unique=False)
    op.create_index(op.f('ix_attachments_work_id'), 'attachments', ['work_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_attachments_work_id'), table_name='attachments')
    op.drop_index(op.f('ix_attachments_message_id'), table_name='attachments')
    op.drop_table('attachments')
