"""rename works to chats (tables, columns, indexes, audit actions and links)

Revision ID: f7d3b8e1c562
Revises: e5c9a2b7d104
Create Date: 2026-10-21 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'f7d3b8e1c562'
down_revision: Union[str, Sequence[str], None] = 'e5c9a2b7d104'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = [('works', 'chats'), ('work_likes', 'chat_likes'), ('work_reads', 'chat_reads')]
COLUMNS = [
    ('messages', 'work_id', 'chat_id'),
    ('attachments', 'work_id', 'chat_id'),
    ('attachments', 'on_work', 'on_chat'),
    ('audit_events', 'work_id', 'chat_id'),
    ('chat_likes', 'work_id', 'chat_id'),
    ('chat_reads', 'work_id', 'chat_id'),
]
INDEXES = [
    ('ix_works_group_id', 'ix_chats_group_id'),
    ('ix_works_last_activity_at', 'ix_chats_last_activity_at'),
    ('ix_works_search', 'ix_chats_search'),
    ('ix_works_series_id', 'ix_chats_series_id'),
    ('ix_works_close_at', 'ix_chats_close_at'),
    ('ix_messages_work_id_id', 'ix_messages_chat_id_id'),
    ('ix_attachments_work_id', 'ix_attachments_chat_id'),
    ('ix_audit_events_work_id', 'ix_audit_events_chat_id'),
]
# (table after the rename, old name, new name)
CONSTRAINTS = [
    ('chats', 'works_pkey', 'chats_pkey'),
    ('chats', 'works_created_by_fkey', 'chats_created_by_fkey'),
    ('chats', 'works_group_id_fkey', 'chats_group_id_fkey'),
    ('chats', 'works_series_id_fkey', 'chats_series_id_fkey'),
    ('messages', 'messages_work_id_fkey', 'messages_chat_id_fkey'),
    ('attachments', 'attachments_work_id_fkey', 'attachments_chat_id_fkey'),
    ('chat_likes', 'work_likes_pkey', 'chat_likes_pkey'),
    ('chat_likes', 'work_likes_user_id_fkey', 'chat_likes_user_id_fkey'),
    ('chat_likes', 'work_likes_work_id_fkey', 'chat_likes_chat_id_fkey'),
    ('chat_reads', 'work_reads_pkey', 'chat_reads_pkey'),
    ('chat_reads', 'work_reads_user_id_fkey', 'chat_reads_user_id_fkey'),
    ('chat_reads', 'work_reads_work_id_fkey', 'chat_reads_chat_id_fkey'),
]


def _links(old: str, new: str) -> None:
    """Links inside texts, e.g. [Plan](/works/3#m41). Runs while the table is called "chats"."""
    for table in ('messages', 'chats'):
        op.execute(f"UPDATE {table} SET body = replace(body, '(/{old}/', '(/{new}/') WHERE body LIKE '%(/{old}/%'")


def upgrade() -> None:
    op.execute("ALTER TABLE works DROP COLUMN IF EXISTS kind")  # left over from a removed feature
    for old, new in TABLES:
        op.rename_table(old, new)
    op.execute("ALTER SEQUENCE works_id_seq RENAME TO chats_id_seq")
    for table, old, new in COLUMNS:
        op.alter_column(table, old, new_column_name=new)
    for old, new in INDEXES:
        op.execute(f"ALTER INDEX {old} RENAME TO {new}")
    for table, old, new in CONSTRAINTS:
        op.execute(f"ALTER TABLE {table} RENAME CONSTRAINT {old} TO {new}")

    op.execute("UPDATE audit_events SET action = 'chat.' || substr(action, 6) WHERE action LIKE 'work.%'")
    op.execute("UPDATE audit_events SET target_type = 'chat' WHERE target_type = 'work'")
    _links('works', 'chats')


def downgrade() -> None:
    _links('chats', 'works')
    op.execute("UPDATE audit_events SET target_type = 'work' WHERE target_type = 'chat'")
    op.execute("UPDATE audit_events SET action = 'work.' || substr(action, 6) WHERE action LIKE 'chat.%'")

    for table, old, new in CONSTRAINTS:
        op.execute(f"ALTER TABLE {table} RENAME CONSTRAINT {new} TO {old}")
    for old, new in INDEXES:
        op.execute(f"ALTER INDEX {new} RENAME TO {old}")
    for table, old, new in COLUMNS:
        op.alter_column(table, new, new_column_name=old)
    op.execute("ALTER SEQUENCE chats_id_seq RENAME TO works_id_seq")
    for old, new in TABLES:
        op.rename_table(new, old)
