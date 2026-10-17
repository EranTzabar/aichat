"""message views (seen by)

Revision ID: 7c1e9a4b2d10
Revises: 52d3e6ad0660
Create Date: 2026-10-17 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7c1e9a4b2d10'
down_revision: Union[str, Sequence[str], None] = '52d3e6ad0660'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('message_views',
    sa.Column('message_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('seen_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['message_id'], ['messages.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('message_id', 'user_id')
    )
    op.create_index(op.f('ix_message_views_user_id'), 'message_views', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_message_views_user_id'), table_name='message_views')
    op.drop_table('message_views')
