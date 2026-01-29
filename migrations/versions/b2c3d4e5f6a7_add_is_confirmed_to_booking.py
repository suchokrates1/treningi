"""Add is_confirmed column to bookings.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-01-29 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('bookings', sa.Column('is_confirmed', sa.Boolean(), nullable=True))


def downgrade():
    op.drop_column('bookings', 'is_confirmed')
