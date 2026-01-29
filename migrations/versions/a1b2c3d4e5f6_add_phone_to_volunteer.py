"""Add phone_number to volunteers

Revision ID: a1b2c3d4e5f6
Revises: 8e98b1a58d08
Create Date: 2026-01-29 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '8e98b1a58d08'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('volunteers', schema=None) as batch_op:
        batch_op.add_column(sa.Column('phone_number', sa.String(length=20), nullable=True))


def downgrade():
    with op.batch_alter_table('volunteers', schema=None) as batch_op:
        batch_op.drop_column('phone_number')
