"""initial_canonical_schema

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-09-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _schema_already_bootstrapped() -> bool:
    """The PostGIS bootstrap script (infra/init-db.sql) may have created the
    application tables before Alembic ran (fresh Docker volume). In that case
    this revision must be a no-op and revision 002 reconciles the shape."""
    inspector = sa.inspect(op.get_bind())
    return inspector.has_table("reports")


def upgrade() -> None:
    if _schema_already_bootstrapped():
        return

    # 1. Reports table
    op.create_table(
        'reports',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('source_type', sa.String(length=50), nullable=False),
        sa.Column('source_name', sa.String(length=100), nullable=False),
        sa.Column('external_id', sa.String(length=255), nullable=True),
        sa.Column('report_hash', sa.String(length=64), nullable=True),
        sa.Column('text', sa.Text(), nullable=True),
        sa.Column('language', sa.String(length=10), server_default='en', nullable=True),
        sa.Column('translated_text', sa.Text(), nullable=True),
        sa.Column('observed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ingested_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('location_provenance', sa.String(length=50), server_default='unknown', nullable=True),
        sa.Column('location_confidence', sa.Numeric(precision=4, scale=3), server_default='0.0', nullable=True),
        sa.Column('city', sa.String(length=100), nullable=True),
        sa.Column('district', sa.String(length=100), nullable=True),
        sa.Column('state', sa.String(length=100), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('event_confidence', sa.Numeric(precision=4, scale=3), server_default='0.0', nullable=True),
        sa.Column('raw_object_key', sa.Text(), nullable=True),
        sa.Column('media_urls', sa.JSON(), nullable=True),
        sa.Column('is_duplicate', sa.Boolean(), server_default='false', nullable=True),
        sa.Column('duplicate_of', sa.String(length=36), nullable=True),
        sa.Column('processing_status', sa.String(length=50), server_default='VALIDATED', nullable=False),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['duplicate_of'], ['reports.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_reports_geo', 'reports', ['latitude', 'longitude'])
    op.create_index('ix_reports_observed_at', 'reports', ['observed_at'])
    op.create_index('ix_reports_event_type', 'reports', ['event_type'])
    op.create_index('ix_reports_report_hash', 'reports', ['report_hash'], unique=True)
    op.create_index('ix_reports_source_external', 'reports', ['source_type', 'external_id'])

    # 2. Incidents table
    op.create_table(
        'incidents',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('severity', sa.String(length=20), server_default='MODERATE', nullable=False),
        sa.Column('confidence', sa.Numeric(precision=4, scale=3), server_default='0.5', nullable=False),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('radius_meters', sa.Float(), server_default='5000.0', nullable=True),
        sa.Column('city', sa.String(length=100), nullable=True),
        sa.Column('district', sa.String(length=100), nullable=True),
        sa.Column('state', sa.String(length=100), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.String(length=50), server_default='ACTIVE', nullable=False),
        sa.Column('verification_status', sa.String(length=50), server_default='UNCONFIRMED', nullable=False),
        sa.Column('observation_count', sa.Integer(), server_default='1', nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_incidents_geo', 'incidents', ['latitude', 'longitude'])
    op.create_index('ix_incidents_started_at', 'incidents', ['started_at'])
    op.create_index('ix_incidents_state_event', 'incidents', ['state', 'event_type'])

    # 3. Incident Reports relationship table
    op.create_table(
        'incident_reports',
        sa.Column('incident_id', sa.String(length=36), primary_key=True),
        sa.Column('report_id', sa.String(length=36), primary_key=True),
        sa.Column('association_score', sa.Numeric(precision=4, scale=3), server_default='1.0', nullable=True),
        sa.Column('is_primary', sa.Boolean(), server_default='false', nullable=True),
        sa.Column('linked_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['incident_id'], ['incidents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['report_id'], ['reports.id'], ondelete='CASCADE'),
    )

    # 4. Verification Results table
    op.create_table(
        'verification_results',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('report_id', sa.String(length=36), nullable=True),
        sa.Column('incident_id', sa.String(length=36), nullable=True),
        sa.Column('source_score', sa.Numeric(precision=4, scale=3), server_default='0.0', nullable=True),
        sa.Column('content_score', sa.Numeric(precision=4, scale=3), server_default='0.0', nullable=True),
        sa.Column('location_score', sa.Numeric(precision=4, scale=3), server_default='0.0', nullable=True),
        sa.Column('temporal_score', sa.Numeric(precision=4, scale=3), server_default='0.0', nullable=True),
        sa.Column('weather_correlation_score', sa.Numeric(precision=4, scale=3), server_default='0.0', nullable=True),
        sa.Column('media_score', sa.Numeric(precision=4, scale=3), server_default='0.0', nullable=True),
        sa.Column('cross_report_score', sa.Numeric(precision=4, scale=3), server_default='0.0', nullable=True),
        sa.Column('duplicate_risk', sa.Numeric(precision=4, scale=3), server_default='0.0', nullable=True),
        sa.Column('overall_confidence', sa.Numeric(precision=4, scale=3), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('reasons', sa.JSON(), nullable=True),
        sa.Column('model_version', sa.String(length=50), server_default='verify-v1.0', nullable=True),
        sa.Column('reviewed_by', sa.String(length=100), nullable=True),
        sa.Column('review_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['incident_id'], ['incidents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['report_id'], ['reports.id'], ondelete='CASCADE'),
    )

    # 5. Audit Logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('actor_id', sa.String(length=100), nullable=False),
        sa.Column('actor_role', sa.String(length=50), nullable=False),
        sa.Column('target_type', sa.String(length=50), nullable=False),
        sa.Column('target_id', sa.String(length=36), nullable=True),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_audit_logs_action', 'audit_logs', ['action'])
    op.create_index('ix_audit_logs_created_at', 'audit_logs', ['created_at'])
    op.create_index('ix_audit_logs_target', 'audit_logs', ['target_type', 'target_id'])


def downgrade() -> None:
    import os

    if os.environ.get("ALLOW_DESTRUCTIVE_DOWNGRADE") != "1":
        raise RuntimeError(
            "Refusing to drop application tables. Re-run with ALLOW_DESTRUCTIVE_DOWNGRADE=1 "
            "if you intentionally want to destroy the reports/incidents schema."
        )
    op.drop_table('audit_logs')
    op.drop_table('verification_results')
    op.drop_table('incident_reports')
    op.drop_table('incidents')
    op.drop_table('reports')
