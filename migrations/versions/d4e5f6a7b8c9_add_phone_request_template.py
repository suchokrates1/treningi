"""Add phone_request_template to email_settings

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2025-01-20 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd4e5f6a7b8c9'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('email_settings', sa.Column('phone_request_template', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('email_settings', 'phone_request_template')
