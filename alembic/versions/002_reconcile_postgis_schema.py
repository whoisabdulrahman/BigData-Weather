"""reconcile postgis spatial schema with application models

Two bootstrap paths exist in this repository:

1. ``infra/init-db.sql`` runs on a fresh Docker volume and creates the
   PostGIS-enabled application tables (``location geography``, ``metadata``
   jsonb) *before* Alembic starts.
2. Revision ``001_initial_schema`` creates the application tables directly
   when the bootstrap script did not run.

This revision is therefore written defensively: every statement is guarded so
that either bootstrap path converges on one canonical schema:

* application columns required by ``apps/api/models`` (``report_hash``,
  ``processing_status``, ``metadata_json``)
* PostGIS ``geography(Point, 4326)`` location columns kept in sync with
  latitude/longitude through a database trigger
* GiST spatial indexes plus the indexes declared by the ORM models

Revision ID: 002_reconcile_postgis_schema
Revises: 001_initial_schema
Create Date: 2026-09-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002_reconcile_postgis_schema'
down_revision: Union[str, None] = '001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SYNC_LOCATION_FUNCTION = """
CREATE OR REPLACE FUNCTION bwip_sync_location_column() RETURNS trigger AS $$
BEGIN
    IF NEW.latitude IS NOT NULL AND NEW.longitude IS NOT NULL THEN
        NEW.location := ST_SetSRID(ST_MakePoint(NEW.longitude, NEW.latitude), 4326)::geography;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql
"""


def _columns(inspector, table: str) -> set:
    return {column["name"] for column in inspector.get_columns(table)}


def _indexes(inspector, table: str) -> set:
    return {index["name"] for index in inspector.get_indexes(table)}


def _ensure_column(connection, table: str, name: str, ddl: str) -> None:
    connection.execute(sa.text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {name} {ddl}"))


def _ensure_index(connection, inspector, table: str, name: str, ddl: str) -> None:
    if name not in _indexes(inspector, table):
        connection.execute(sa.text(f"CREATE INDEX {name} ON {table} {ddl}"))


def _ensure_unique_index(connection, inspector, table: str, name: str, ddl: str) -> None:
    if name not in _indexes(inspector, table):
        connection.execute(sa.text(f"CREATE UNIQUE INDEX {name} ON {table} {ddl}"))


def _set_not_null_when_safe(connection, table: str, column: str, backfill: str = "") -> None:
    nulls = connection.execute(
        sa.text(f"SELECT count(*) FROM {table} WHERE {column} IS NULL")
    ).scalar()
    if nulls:
        if backfill:
            connection.execute(sa.text(backfill))
            nulls = connection.execute(
                sa.text(f"SELECT count(*) FROM {table} WHERE {column} IS NULL")
            ).scalar()
    if not nulls:
        connection.execute(sa.text(f"ALTER TABLE {table} ALTER COLUMN {column} SET NOT NULL"))


def upgrade() -> None:
    connection = op.get_bind()
    if connection.dialect.name != "postgresql":
        return

    inspector = sa.inspect(connection)

    # ------------------------------------------------------------------
    # Extensions (idempotent; also asserted by infra/init-db.sql)
    # ------------------------------------------------------------------
    connection.execute(sa.text('CREATE EXTENSION IF NOT EXISTS postgis'))
    connection.execute(sa.text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))

    # ------------------------------------------------------------------
    # 1. reports
    # ------------------------------------------------------------------
    report_columns = _columns(inspector, "reports")

    _ensure_column(connection, "reports", "report_hash", "VARCHAR(64)")
    _ensure_column(
        connection,
        "reports",
        "processing_status",
        "VARCHAR(50) NOT NULL DEFAULT 'VALIDATED'",
    )
    _ensure_column(connection, "reports", "location", "geography(Point, 4326)")

    if "metadata" in report_columns and "metadata_json" not in report_columns:
        connection.execute(sa.text("ALTER TABLE reports RENAME COLUMN metadata TO metadata_json"))
    _ensure_column(connection, "reports", "metadata_json", "JSONB DEFAULT '{}'::jsonb")

    _set_not_null_when_safe(connection, "reports", "latitude")
    _set_not_null_when_safe(connection, "reports", "longitude")
    _set_not_null_when_safe(
        connection,
        "reports",
        "state",
        backfill="UPDATE reports SET state = 'India' WHERE state IS NULL",
    )

    # Backfill spatial column for rows written before the trigger existed
    connection.execute(
        sa.text(
            """
            UPDATE reports
               SET location = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography
             WHERE latitude IS NOT NULL
               AND longitude IS NOT NULL
               AND location IS NULL
            """
        )
    )

    inspector = sa.inspect(connection)
    _ensure_unique_index(connection, inspector, "reports", "ix_reports_report_hash", "(report_hash)")
    _ensure_index(connection, inspector, "reports", "ix_reports_geo", "(latitude, longitude)")
    _ensure_index(connection, inspector, "reports", "ix_reports_observed_at", "(observed_at)")
    _ensure_index(connection, inspector, "reports", "ix_reports_event_type", "(event_type)")
    _ensure_index(
        connection, inspector, "reports", "ix_reports_source_external", "(source_type, external_id)"
    )
    _ensure_index(connection, inspector, "reports", "ix_reports_external_id", "(external_id)")
    connection.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS reports_location_gix ON reports USING GIST (location)"
        )
    )

    # ------------------------------------------------------------------
    # 2. incidents
    # ------------------------------------------------------------------
    incident_columns = _columns(inspector, "incidents")

    _ensure_column(connection, "incidents", "location", "geography(Point, 4326)")
    if "metadata" in incident_columns and "metadata_json" not in incident_columns:
        connection.execute(
            sa.text("ALTER TABLE incidents RENAME COLUMN metadata TO metadata_json")
        )
    _ensure_column(connection, "incidents", "metadata_json", "JSONB DEFAULT '{}'::jsonb")

    _set_not_null_when_safe(connection, "incidents", "latitude")
    _set_not_null_when_safe(connection, "incidents", "longitude")

    connection.execute(
        sa.text(
            """
            UPDATE incidents
               SET location = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography
             WHERE latitude IS NOT NULL
               AND longitude IS NOT NULL
               AND location IS NULL
            """
        )
    )

    if "location" not in _columns(inspector, "incidents"):
        raise RuntimeError("incidents.location geography column could not be created")
    _set_not_null_when_safe(connection, "incidents", "location")

    inspector = sa.inspect(connection)
    _ensure_index(connection, inspector, "incidents", "ix_incidents_geo", "(latitude, longitude)")
    _ensure_index(connection, inspector, "incidents", "ix_incidents_started_at", "(started_at)")
    _ensure_index(
        connection, inspector, "incidents", "ix_incidents_state_event", "(state, event_type)"
    )
    _ensure_index(connection, inspector, "incidents", "ix_incidents_event_type", "(event_type)")
    _ensure_index(connection, inspector, "incidents", "ix_incidents_state", "(state)")
    _ensure_index(connection, inspector, "incidents", "ix_incidents_status", "(status)")
    _ensure_index(
        connection, inspector, "incidents", "ix_incidents_verification_status", "(verification_status)"
    )
    connection.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS incidents_location_gix ON incidents USING GIST (location)"
        )
    )

    # ------------------------------------------------------------------
    # 3. bridge / audit tables: make sure they exist on both bootstrap paths
    # ------------------------------------------------------------------
    connection.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS incident_reports (
                incident_id VARCHAR(36) NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
                report_id VARCHAR(36) NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
                association_score NUMERIC(4, 3) DEFAULT 1.000,
                is_primary BOOLEAN DEFAULT FALSE,
                linked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY (incident_id, report_id)
            )
            """
        )
    )
    connection.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS incident_reports_report_id_idx ON incident_reports (report_id)"
        )
    )
    connection.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS incident_reports_incident_id_idx ON incident_reports (incident_id)"
        )
    )

    # ------------------------------------------------------------------
    # 4. Keep the PostGIS geography column consistent with lat/lon
    # ------------------------------------------------------------------
    connection.execute(sa.text(SYNC_LOCATION_FUNCTION))
    connection.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS trg_reports_sync_location ON reports"
        )
    )
    connection.execute(
        sa.text(
            """
            CREATE TRIGGER trg_reports_sync_location
            BEFORE INSERT OR UPDATE OF latitude, longitude
            ON reports
            FOR EACH ROW
            EXECUTE FUNCTION bwip_sync_location_column()
            """
        )
    )
    connection.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS trg_incidents_sync_location ON incidents"
        )
    )
    connection.execute(
        sa.text(
            """
            CREATE TRIGGER trg_incidents_sync_location
            BEFORE INSERT OR UPDATE OF latitude, longitude
            ON incidents
            FOR EACH ROW
            EXECUTE FUNCTION bwip_sync_location_column()
            """
        )
    )


def downgrade() -> None:
    connection = op.get_bind()
    if connection.dialect.name != "postgresql":
        return

    connection.execute(sa.text("DROP TRIGGER IF EXISTS trg_reports_sync_location ON reports"))
    connection.execute(sa.text("DROP TRIGGER IF EXISTS trg_incidents_sync_location ON incidents"))
    connection.execute(sa.text("DROP FUNCTION IF EXISTS bwip_sync_location_column()"))

    inspector = sa.inspect(connection)
    report_columns = _columns(inspector, "reports")
    incident_columns = _columns(inspector, "incidents")

    for table, columns in (("reports", report_columns), ("incidents", incident_columns)):
        for column in ("report_hash", "processing_status"):
            if table == "reports" and column in columns:
                connection.execute(sa.text(f"ALTER TABLE {table} DROP COLUMN {column}"))

    if "metadata_json" in report_columns and "metadata" not in report_columns:
        connection.execute(sa.text("ALTER TABLE reports RENAME COLUMN metadata_json TO metadata"))
    if "metadata_json" in incident_columns and "metadata" not in incident_columns:
        connection.execute(sa.text("ALTER TABLE incidents RENAME COLUMN metadata_json TO metadata"))
