"""Add phone request sent flag to volunteers

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-01-29 22:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c3d4e5f6a7b8'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('volunteers', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('phone_request_sent', sa.Boolean(), nullable=True, default=False)
        )
        batch_op.add_column(
            sa.Column('phone_update_token', sa.String(64), nullable=True)
        )


def downgrade():
    with op.batch_alter_table('volunteers', schema=None) as batch_op:
        batch_op.drop_column('phone_request_sent')
        batch_op.drop_column('phone_update_token')
