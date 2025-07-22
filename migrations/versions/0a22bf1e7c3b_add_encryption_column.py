"""add encryption column to email settings

Revision ID: 0a22bf1e7c3b
Revises: 4299368c4dd9
Create Date: 2025-07-21 18:00:00
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0a22bf1e7c3b'
down_revision = '4299368c4dd9'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'email_settings',
        sa.Column('encryption', sa.String(length=10), nullable=True, server_default='tls'),
    )
    op.alter_column('email_settings', 'encryption', server_default=None)


def downgrade():
    op.drop_column('email_settings', 'encryption')
