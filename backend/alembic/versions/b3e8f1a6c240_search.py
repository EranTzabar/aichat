"""search: full-text vectors on works, messages and attachments; text of text files

Revision ID: b3e8f1a6c240
Revises: 9f4d2c7e1a35
Create Date: 2026-10-18 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# The search expressions as they were at this revision (kept here, so later model changes can't break it).
WORK_TSV = "setweight(to_tsvector('simple'::regconfig, title), 'A') || setweight(to_tsvector('simple'::regconfig, body), 'B')"
MESSAGE_TSV = "to_tsvector('simple'::regconfig, body)"
ATTACHMENT_TSV = (
    "setweight(to_tsvector('simple'::regconfig, filename), 'A') || "
    "setweight(to_tsvector('simple'::regconfig, coalesce(text_content, '')), 'B')"
)


# revision identifiers, used by Alembic.
revision: str = 'b3e8f1a6c240'
down_revision: Union[str, Sequence[str], None] = '9f4d2c7e1a35'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = (("works", WORK_TSV), ("messages", MESSAGE_TSV), ("attachments", ATTACHMENT_TSV))


def upgrade() -> None:
    op.add_column('attachments', sa.Column('text_content', sa.Text(), nullable=True))
    for table, expression in TABLES:
        op.add_column(
            table, sa.Column('search_tsv', postgresql.TSVECTOR(), sa.Computed(expression, persisted=True), nullable=True)
        )
        op.create_index(f'ix_{table}_search', table, ['search_tsv'], unique=False, postgresql_using='gin')


def downgrade() -> None:
    for table, _ in TABLES:
        op.drop_index(f'ix_{table}_search', table_name=table, postgresql_using='gin')
        op.drop_column(table, 'search_tsv')
    op.drop_column('attachments', 'text_content')
