"""initial schema

Revision ID: 0001
Revises: 
Create Date: 2026-10-26 13:42:52.721756
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():

    op.create_table('alerts',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('fingerprint', sa.String(length=200), nullable=False),
    sa.Column('kind', sa.String(length=32), nullable=False),
    sa.Column('severity', sa.String(length=16), nullable=False),
    sa.Column('series_id', sa.String(length=96), nullable=True),
    sa.Column('source_id', sa.String(length=64), nullable=True),
    sa.Column('geo', sa.String(length=32), nullable=True),
    sa.Column('dim', sa.String(length=64), nullable=True),
    sa.Column('period', sa.String(length=32), nullable=True),
    sa.Column('title', sa.String(length=300), nullable=False),
    sa.Column('detail', sa.Text(), nullable=False),
    sa.Column('payload', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('fingerprint')
    )
    with op.batch_alter_table('alerts', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_alerts_series_id'), ['series_id'], unique=False)

    op.create_table('geo_areas',
    sa.Column('code', sa.String(length=32), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('level', sa.String(length=16), nullable=False),
    sa.Column('parent_code', sa.String(length=32), nullable=True),
    sa.Column('alt_codes', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.PrimaryKeyConstraint('code')
    )
    with op.batch_alter_table('geo_areas', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_geo_areas_parent_code'), ['parent_code'], unique=False)

    op.create_table('geo_boundaries',
    sa.Column('level', sa.String(length=16), nullable=False),
    sa.Column('geojson', sa.Text(), nullable=False),
    sa.Column('source_url', sa.Text(), nullable=False),
    sa.Column('retrieved_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('feature_count', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('level')
    )
    op.create_table('http_cache',
    sa.Column('key', sa.String(length=64), nullable=False),
    sa.Column('url', sa.Text(), nullable=False),
    sa.Column('status', sa.Integer(), nullable=False),
    sa.Column('etag', sa.String(length=300), nullable=True),
    sa.Column('last_modified', sa.String(length=100), nullable=True),
    sa.Column('content_type', sa.String(length=200), nullable=True),
    sa.Column('body', sa.LargeBinary(), nullable=False),
    sa.Column('fetched_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('key')
    )
    op.create_table('saved_views',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('path', sa.String(length=400), nullable=False),
    sa.Column('state', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('sources',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('publisher', sa.String(length=200), nullable=False),
    sa.Column('meta', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('enabled', sa.Boolean(), nullable=False),
    sa.Column('disabled_reason', sa.Text(), nullable=True),
    sa.Column('last_attempt_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_success_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_error', sa.Text(), nullable=True),
    sa.Column('consecutive_failures', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('ingestion_runs',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('source_id', sa.String(length=64), nullable=False),
    sa.Column('job', sa.String(length=96), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('fetched', sa.Integer(), nullable=False),
    sa.Column('inserted', sa.Integer(), nullable=False),
    sa.Column('updated', sa.Integer(), nullable=False),
    sa.Column('revised', sa.Integer(), nullable=False),
    sa.Column('unchanged', sa.Integer(), nullable=False),
    sa.Column('errors', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('requests', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('message', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['source_id'], ['sources.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('ingestion_runs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_ingestion_runs_source_id'), ['source_id'], unique=False)

    op.create_table('series',
    sa.Column('id', sa.String(length=96), nullable=False),
    sa.Column('source_id', sa.String(length=64), nullable=False),
    sa.Column('source_key', sa.String(length=200), nullable=False),
    sa.Column('title', sa.String(length=300), nullable=False),
    sa.Column('definition', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('source_title', sa.String(length=400), nullable=True),
    sa.Column('last_period', sa.String(length=32), nullable=True),
    sa.Column('release_date', sa.DateTime(timezone=True), nullable=True),
    sa.Column('next_release', sa.String(length=64), nullable=True),
    sa.Column('last_retrieved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_request_url', sa.Text(), nullable=True),
    sa.Column('source_meta', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.ForeignKeyConstraint(['source_id'], ['sources.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('series', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_series_source_id'), ['source_id'], unique=False)

    op.create_table('observation_revisions',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('series_id', sa.String(length=96), nullable=False),
    sa.Column('geo', sa.String(length=32), nullable=False),
    sa.Column('dim', sa.String(length=64), nullable=False),
    sa.Column('period', sa.String(length=32), nullable=False),
    sa.Column('old_value', sa.Float(), nullable=True),
    sa.Column('new_value', sa.Float(), nullable=True),
    sa.Column('old_release_date', sa.DateTime(timezone=True), nullable=True),
    sa.Column('new_release_date', sa.DateTime(timezone=True), nullable=True),
    sa.Column('detected_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('run_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['run_id'], ['ingestion_runs.id'], ),
    sa.ForeignKeyConstraint(['series_id'], ['series.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('observation_revisions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_observation_revisions_series_id'), ['series_id'], unique=False)

    op.create_table('observations',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('series_id', sa.String(length=96), nullable=False),
    sa.Column('geo', sa.String(length=32), nullable=False),
    sa.Column('dim', sa.String(length=64), nullable=False),
    sa.Column('period', sa.String(length=32), nullable=False),
    sa.Column('period_start', sa.Date(), nullable=False),
    sa.Column('period_end', sa.Date(), nullable=False),
    sa.Column('value', sa.Float(), nullable=True),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('flags', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('release_date', sa.DateTime(timezone=True), nullable=True),
    sa.Column('retrieved_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('run_id', sa.Integer(), nullable=True),
    sa.Column('is_demo', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['run_id'], ['ingestion_runs.id'], ),
    sa.ForeignKeyConstraint(['series_id'], ['series.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('series_id', 'geo', 'dim', 'period', 'is_demo', name='uq_obs_key')
    )
    with op.batch_alter_table('observations', schema=None) as batch_op:
        batch_op.create_index('ix_obs_series_geo_dim_start', ['series_id', 'geo', 'dim', 'period_start'], unique=False)




def downgrade():

    with op.batch_alter_table('observations', schema=None) as batch_op:
        batch_op.drop_index('ix_obs_series_geo_dim_start')

    op.drop_table('observations')
    with op.batch_alter_table('observation_revisions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_observation_revisions_series_id'))

    op.drop_table('observation_revisions')
    with op.batch_alter_table('series', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_series_source_id'))

    op.drop_table('series')
    with op.batch_alter_table('ingestion_runs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_ingestion_runs_source_id'))

    op.drop_table('ingestion_runs')
    op.drop_table('sources')
    op.drop_table('saved_views')
    op.drop_table('http_cache')
    op.drop_table('geo_boundaries')
    with op.batch_alter_table('geo_areas', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_geo_areas_parent_code'))

    op.drop_table('geo_areas')
    with op.batch_alter_table('alerts', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_alerts_series_id'))

    op.drop_table('alerts')

