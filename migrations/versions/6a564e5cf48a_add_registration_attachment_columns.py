"""add registration attachment columns

Revision ID: 6a564e5cf48a
Revises: 8e98b1a58d08
Create Date: 2025-07-15 21:37:37.159899

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6a564e5cf48a'
down_revision = '8e98b1a58d08'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'email_settings',
        sa.Column('registration_files_adult', sa.JSON(), nullable=True),
    )
    op.add_column(
        'email_settings',
        sa.Column('registration_files_minor', sa.JSON(), nullable=True),
    )


def downgrade():
    op.drop_column('email_settings', 'registration_files_minor')
    op.drop_column('email_settings', 'registration_files_adult')
