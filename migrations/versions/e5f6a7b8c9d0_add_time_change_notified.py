"""add time_change_notified to bookings

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-02-06 16:37:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e5f6a7b8c9d0'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'bookings',
        sa.Column('time_change_notified', sa.Boolean(), nullable=False, server_default='0'),
    )


def downgrade():
    op.drop_column('bookings', 'time_change_notified')
