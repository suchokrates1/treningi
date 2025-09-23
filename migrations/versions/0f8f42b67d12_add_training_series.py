"""add training series table

Revision ID: 0f8f42b67d12
Revises: 6a564e5cf48a
Create Date: 2024-01-01 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0f8f42b67d12"
down_revision = "6a564e5cf48a"
branch_labels = None
depends_on = None


TABLE_NAME = "training_series"


def _table_exists(bind, table_name):
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade():
    bind = op.get_bind()
    if not _table_exists(bind, TABLE_NAME):
        op.create_table(
            TABLE_NAME,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("start_date", sa.DateTime(), nullable=False),
            sa.Column("repeat", sa.Boolean(), nullable=False),
            sa.Column("repeat_interval_weeks", sa.Integer()),
            sa.Column("repeat_until", sa.Date()),
            sa.Column("planned_count", sa.Integer(), nullable=False),
            sa.Column("created_count", sa.Integer(), nullable=False),
            sa.Column("skipped_dates", sa.JSON(), nullable=False),
            sa.Column("coach_id", sa.Integer(), nullable=False),
            sa.Column("location_id", sa.Integer(), nullable=False),
            sa.Column("max_volunteers", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["coach_id"], ["coaches.id"]),
            sa.ForeignKeyConstraint(["location_id"], ["locations.id"]),
        )


def downgrade():
    bind = op.get_bind()
    if _table_exists(bind, TABLE_NAME):
        op.drop_table(TABLE_NAME)
