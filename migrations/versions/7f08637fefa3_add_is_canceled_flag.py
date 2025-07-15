"""add is_canceled flag

Revision ID: 7f08637fefa3
Revises: eb0ac69d8f6c
Create Date: 2025-07-15 21:05:41.177861

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7f08637fefa3'
down_revision = 'eb0ac69d8f6c'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'trainings',
        sa.Column(
            'is_canceled',
            sa.Boolean(),
            nullable=False,
            server_default='0',
        ),
    )



def downgrade():
    op.drop_column('trainings', 'is_canceled')
