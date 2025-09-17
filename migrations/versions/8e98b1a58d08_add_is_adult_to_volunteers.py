"""add is_adult to volunteers

Revision ID: 8e98b1a58d08
Revises: 3fb4e7c905e4
Create Date: 2023-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8e98b1a58d08'
down_revision = '3fb4e7c905e4'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('volunteers', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_adult', sa.Boolean(), nullable=True))


def downgrade():
    with op.batch_alter_table('volunteers', schema=None) as batch_op:
        batch_op.drop_column('is_adult')
