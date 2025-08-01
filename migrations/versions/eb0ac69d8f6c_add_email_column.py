"""add email column

Revision ID: eb0ac69d8f6c
Revises: 6ef85ec0c835
Create Date: 2025-07-15 16:35:52.120158

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'eb0ac69d8f6c'
down_revision = '6ef85ec0c835'
branch_labels = None
depends_on = None


def upgrade():
    """Add unique ``email`` column replacing ``phone_number``."""
    # Add the column as nullable with a temporary default so SQLite can insert
    # values when recreating the table.
    op.add_column(
        "volunteers",
        sa.Column("email", sa.String(length=128), nullable=True, server_default=""),
    )

    # Populate the new column for existing rows. ``phone_number`` is still
    # present at this stage so we can copy its value or set any placeholder.
    op.execute("UPDATE volunteers SET email = phone_number")

    # Alter the column to be non-nullable and drop the default while also
    # dropping the old ``phone_number`` column.
    with op.batch_alter_table("volunteers", schema=None) as batch_op:
        batch_op.alter_column("email", nullable=False, server_default=None)
        batch_op.create_unique_constraint("uq_volunteers_email", ["email"])
        batch_op.drop_column("phone_number")



def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('volunteers', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('phone_number', sa.VARCHAR(length=20), nullable=False)
        )
        batch_op.drop_constraint('uq_volunteers_email', type_='unique')
        batch_op.drop_column('email')

    # ### end Alembic commands ###
