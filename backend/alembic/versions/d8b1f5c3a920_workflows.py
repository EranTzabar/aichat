"""workflows

Revision ID: d8b1f5c3a920
Revises: c4a7d2e9f813
Create Date: 2026-10-20 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd8b1f5c3a920'
down_revision: Union[str, Sequence[str], None] = 'c4a7d2e9f813'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('workflows',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('enabled', sa.Boolean(), nullable=False),
    sa.Column('group_id', sa.Integer(), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=False),
    sa.Column('trigger', sa.String(length=20), nullable=False),
    sa.Column('trigger_config', sa.JSON(), nullable=False),
    sa.Column('action', sa.String(length=20), nullable=False),
    sa.Column('action_config', sa.JSON(), nullable=False),
    sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id']),
    sa.ForeignKeyConstraint(['group_id'], ['groups.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_workflows_group_id'), 'workflows', ['group_id'], unique=False)
    op.create_table('workflow_runs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('workflow_id', sa.Integer(), nullable=False),
    sa.Column('at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('ok', sa.Boolean(), nullable=False),
    sa.Column('detail', sa.Text(), nullable=False),
    sa.Column('work_id', sa.Integer(), nullable=True),
    sa.Column('message_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['workflow_id'], ['workflows.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_workflow_runs_workflow_id_id', 'workflow_runs', ['workflow_id', 'id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_workflow_runs_workflow_id_id', table_name='workflow_runs')
    op.drop_table('workflow_runs')
    op.drop_index(op.f('ix_workflows_group_id'), table_name='workflows')
    op.drop_table('workflows')
