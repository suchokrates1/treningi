"""add training series table

Revision ID: 0f8f42b67d12
Revises: 6a564e5cf48a
Create Date: 2024-05-04 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0f8f42b67d12"
down_revision = "6a564e5cf48a"
branch_labels = None
depends_on = None

TABLE_NAME = "training_series"
TRAININGS_TABLE = "trainings"
SERIES_ID_COL = "series_id"
FK_NAME = "fk_trainings_series_id_training_series"


def _table_exists(bind, table_name: str) -> bool:
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _column_exists(bind, table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns(table_name)}
    return column_name in cols


def _fk_exists(bind, table_name: str, fk_name: str) -> bool:
    inspector = sa.inspect(bind)
    fks = inspector.get_foreign_keys(table_name)
    for fk in fks:
        if fk.get("name") == fk_name:
            return True
    return False


def upgrade():
    bind = op.get_bind()

    # 1) Tabela training_series
    if not _table_exists(bind, TABLE_NAME):
        op.create_table(
            TABLE_NAME,
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("start_date", sa.DateTime(timezone=True), nullable=False),
            sa.Column("repeat", sa.Boolean(), nullable=False),
            sa.Column("repeat_interval_weeks", sa.Integer(), nullable=True),
            sa.Column("repeat_until", sa.Date(), nullable=True),
            sa.Column("planned_count", sa.Integer(), nullable=False),
            sa.Column("created_count", sa.Integer(), nullable=False),
            sa.Column("skipped_dates", sa.JSON(), nullable=False),
            sa.Column("coach_id", sa.Integer(), nullable=False),
            sa.Column("location_id", sa.Integer(), nullable=False),
            sa.Column("max_volunteers", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["coach_id"], ["coaches.id"]),
            sa.ForeignKeyConstraint(["location_id"], ["locations.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    # 2) Kolumna trainings.series_id + FK do training_series
    if _table_exists(bind, TRAININGS_TABLE) and not _column_exists(
        bind, TRAININGS_TABLE, SERIES_ID_COL
    ):
        op.add_column(
            TRAININGS_TABLE,
            sa.Column(SERIES_ID_COL, sa.Integer(), nullable=True),
        )

    if (
        _table_exists(bind, TRAININGS_TABLE)
        and _column_exists(bind, TRAININGS_TABLE, SERIES_ID_COL)
        and not _fk_exists(bind, TRAININGS_TABLE, FK_NAME)
    ):
        op.create_foreign_key(
            FK_NAME,
            TRAININGS_TABLE,
            TABLE_NAME,
            [SERIES_ID_COL],
            ["id"],
        )


def downgrade():
    bind = op.get_bind()

    # 1) Usuń FK jeśli istnieje
    if _table_exists(bind, TRAININGS_TABLE) and _fk_exists(bind, TRAININGS_TABLE, FK_NAME):
        op.drop_constraint(FK_NAME, TRAININGS_TABLE, type_="foreignkey")

    # 2) Usuń kolumnę series_id z trainings jeśli istnieje
    if _table_exists(bind, TRAININGS_TABLE) and _column_exists(bind, TRAININGS_TABLE, SERIES_ID_COL):
        op.drop_column(TRAININGS_TABLE, SERIES_ID_COL)

    # 3) Usuń tabelę training_series jeśli istnieje
    if _table_exists(bind, TABLE_NAME):
        op.drop_table(TABLE_NAME)
