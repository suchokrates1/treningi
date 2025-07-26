"""add booking limit check constraint

Revision ID: 3fb4e7c905e4
Revises: 29fa7370dfde
Create Date: 2025-08-01 12:00:00
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '3fb4e7c905e4'
down_revision = '29fa7370dfde'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name != 'sqlite':
        op.create_check_constraint(
            'booking_limit',
            'trainings',
            '(SELECT COUNT(*) FROM bookings WHERE bookings.training_id = id) <= max_volunteers',
        )


def downgrade():
    bind = op.get_bind()
    if bind.dialect.name != 'sqlite':
        op.drop_constraint('booking_limit', 'trainings', type_='check')
