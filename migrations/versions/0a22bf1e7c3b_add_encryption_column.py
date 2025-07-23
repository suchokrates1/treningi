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
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_column('email_settings', 'encryption'):
        op.add_column(
            'email_settings',
            sa.Column('encryption', sa.String(length=10), nullable=True),
        )
    op.execute(
        "UPDATE email_settings SET encryption='tls' WHERE encryption IS NULL"
    )


def downgrade():
    op.drop_column('email_settings', 'encryption')
