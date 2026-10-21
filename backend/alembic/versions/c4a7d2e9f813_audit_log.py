"""audit log

Revision ID: c4a7d2e9f813
Revises: b3e8f1a6c240
Create Date: 2026-10-20 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4a7d2e9f813'
down_revision: Union[str, Sequence[str], None] = 'b3e8f1a6c240'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('audit_events',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('actor_id', sa.Integer(), nullable=True),
    sa.Column('via', sa.String(length=10), nullable=False),
    sa.Column('action', sa.String(length=50), nullable=False),
    sa.Column('target_type', sa.String(length=20), nullable=True),
    sa.Column('target_id', sa.Integer(), nullable=True),
    sa.Column('work_id', sa.Integer(), nullable=True),
    sa.Column('group_id', sa.Integer(), nullable=True),
    sa.Column('details', sa.JSON(), nullable=False),
    sa.Column('ip', sa.String(length=64), nullable=True),
    sa.ForeignKeyConstraint(['actor_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audit_events_at'), 'audit_events', ['at'], unique=False)
    op.create_index(op.f('ix_audit_events_work_id'), 'audit_events', ['work_id'], unique=False)
    op.create_index(op.f('ix_audit_events_group_id'), 'audit_events', ['group_id'], unique=False)
    op.create_index('ix_audit_events_actor_id_id', 'audit_events', ['actor_id', 'id'], unique=False)
    op.create_index('ix_audit_events_action_id', 'audit_events', ['action', 'id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_audit_events_action_id', table_name='audit_events')
    op.drop_index('ix_audit_events_actor_id_id', table_name='audit_events')
    op.drop_index(op.f('ix_audit_events_group_id'), table_name='audit_events')
    op.drop_index(op.f('ix_audit_events_work_id'), table_name='audit_events')
    op.drop_index(op.f('ix_audit_events_at'), table_name='audit_events')
    op.drop_table('audit_events')
