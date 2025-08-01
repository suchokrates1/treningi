"""add max volunteers

Revision ID: 29fa7370dfde
Revises: 0a22bf1e7c3b
Create Date: 2025-07-23 16:24:52.602726

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '29fa7370dfde'
down_revision = '0a22bf1e7c3b'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('trainings', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('max_volunteers', sa.Integer(), server_default='2', nullable=False)
        )

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('trainings', schema=None) as batch_op:
        batch_op.drop_column('max_volunteers')

    # ### end Alembic commands ###
