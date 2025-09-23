"""add training series table

Revision ID: 0f8f42b67d12
Revises: 6a564e5cf48a
Create Date: 2024-05-04 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0f8f42b67d12'
down_revision = '6a564e5cf48a'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'training_series',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('start_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('repeat', sa.Boolean(), nullable=False),
        sa.Column('repeat_interval_weeks', sa.Integer(), nullable=True),
        sa.Column('repeat_until', sa.Date(), nullable=True),
        sa.Column('planned_count', sa.Integer(), nullable=False),
        sa.Column('created_count', sa.Integer(), nullable=False),
        sa.Column('skipped_dates', sa.JSON(), nullable=False),
        sa.Column('coach_id', sa.Integer(), nullable=False),
        sa.Column('location_id', sa.Integer(), nullable=False),
        sa.Column('max_volunteers', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['coach_id'], ['coaches.id']),
        sa.ForeignKeyConstraint(['location_id'], ['locations.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.add_column(
        'trainings',
        sa.Column('series_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        'fk_trainings_series_id_training_series',
        'trainings',
        'training_series',
        ['series_id'],
        ['id'],
    )


def downgrade():
    op.drop_constraint(
        'fk_trainings_series_id_training_series',
        'trainings',
        type_='foreignkey',
    )
    op.drop_column('trainings', 'series_id')
    op.drop_table('training_series')
