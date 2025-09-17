"""add attachment metadata columns to email settings

Revision ID: 4ae0a2f4d8fd
Revises: 3fb4e7c905e4
Create Date: 2025-08-05 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "4ae0a2f4d8fd"
down_revision = "3fb4e7c905e4"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "email_settings",
        sa.Column("adult_attachments", sa.JSON(), nullable=True),
    )
    op.add_column(
        "email_settings",
        sa.Column("minor_attachments", sa.JSON(), nullable=True),
    )


def downgrade():
    op.drop_column("email_settings", "minor_attachments")
    op.drop_column("email_settings", "adult_attachments")
