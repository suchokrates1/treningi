"""add coach email column

Revision ID: g7h8i9j0k1l2
Revises: f6a7b8c9d0e1
Create Date: 2026-02-23 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'g7h8i9j0k1l2'
down_revision = 'f6a7b8c9d0e1'
branch_labels = None
depends_on = None


def upgrade():
    """Add optional email column to coaches table."""
    with op.batch_alter_table("coaches", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("email", sa.String(length=128), nullable=True),
        )

    # Set emails for existing coaches
    coaches_table = sa.table(
        "coaches",
        sa.column("first_name", sa.String),
        sa.column("last_name", sa.String),
        sa.column("email", sa.String),
    )
    coach_emails = {
        ("Mariusz", "Jodkowski"): "mariusz.jodkowski@gmail.com",
        ("Antoni", "Polaszek"): "katalonia13x@gmail.com",
        ("Mariusz", "Appel"): "mappel@op.pl",
        ("Radosław", "Banasz"): "banasz.radek1@gmail.com",
    }
    for (first, last), email in coach_emails.items():
        op.execute(
            coaches_table.update()
            .where(
                sa.and_(
                    coaches_table.c.first_name == first,
                    coaches_table.c.last_name == last,
                )
            )
            .values(email=email)
        )


def downgrade():
    with op.batch_alter_table("coaches", schema=None) as batch_op:
        batch_op.drop_column("email")
