"""work automation: tags, repeat and auto-close on works; workflows removed

Revision ID: e5c9a2b7d104
Revises: d8b1f5c3a920
Create Date: 2026-10-21 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'e5c9a2b7d104'
down_revision: Union[str, Sequence[str], None] = 'd8b1f5c3a920'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index('ix_workflow_runs_workflow_id_id', table_name='workflow_runs')
    op.drop_table('workflow_runs')
    op.drop_index(op.f('ix_workflows_group_id'), table_name='workflows')
    op.drop_table('workflows')
    op.execute("UPDATE audit_events SET via = 'auto' WHERE via = 'workflow'")

    op.add_column('works', sa.Column('tagged_user_ids', postgresql.JSONB(), server_default='[]', nullable=False))
    op.add_column('works', sa.Column('repeat', sa.JSON(), nullable=True))
    op.add_column('works', sa.Column('repeat_last_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('works', sa.Column('series_id', sa.Integer(), nullable=True))
    op.add_column('works', sa.Column('close_at', sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key('works_series_id_fkey', 'works', 'works', ['series_id'], ['id'], ondelete='SET NULL')
    op.create_index(op.f('ix_works_series_id'), 'works', ['series_id'], unique=False)
    op.create_index(op.f('ix_works_close_at'), 'works', ['close_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_works_close_at'), table_name='works')
    op.drop_index(op.f('ix_works_series_id'), table_name='works')
    op.drop_constraint('works_series_id_fkey', 'works', type_='foreignkey')
    for column in ('close_at', 'series_id', 'repeat_last_at', 'repeat', 'tagged_user_ids'):
        op.drop_column('works', column)
    op.execute("UPDATE audit_events SET via = 'workflow' WHERE via = 'auto'")

    # The workflow tables come back empty.
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
