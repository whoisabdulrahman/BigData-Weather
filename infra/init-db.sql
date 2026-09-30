-- ==============================================================================
-- Bharat Weather Intelligence Platform (BWIP) — Database Initialization
-- ==============================================================================

-- Enable geospatial and UUID extensions
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ------------------------------------------------------------------------------
-- 1. Reports (Raw & Normalized Observations)
-- Core Invariant: Observation/Report is NOT an Incident
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS reports (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_type VARCHAR(50) NOT NULL, -- citizen, social, weather_api, dataset, web
    source_name VARCHAR(100) NOT NULL,
    external_id VARCHAR(255),
    text TEXT,
    language VARCHAR(10) DEFAULT 'en',
    translated_text TEXT,
    observed_at TIMESTAMPTZ NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    location GEOGRAPHY(Point, 4326),
    location_provenance VARCHAR(50) DEFAULT 'unknown', -- gps, user_selected, metadata, geocoded, weather_grid, unknown
    location_confidence NUMERIC(4, 3) DEFAULT 0.000,
    city VARCHAR(100),
    district VARCHAR(100),
    state VARCHAR(100),
    event_type VARCHAR(50), -- RAIN, FLOOD, THUNDERSTORM, HEATWAVE, FOG, CYCLONE, DUST_STORM, STRONG_WIND, OTHER
    event_confidence NUMERIC(4, 3) DEFAULT 0.000,
    raw_object_key TEXT,
    media_urls JSONB DEFAULT '[]'::jsonb,
    is_duplicate BOOLEAN DEFAULT FALSE,
    duplicate_of UUID REFERENCES reports(id) ON DELETE SET NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Spatial and query indexes for reports
CREATE INDEX IF NOT EXISTS reports_location_gix ON reports USING GIST (location);
CREATE INDEX IF NOT EXISTS reports_observed_at_idx ON reports (observed_at DESC);
CREATE INDEX IF NOT EXISTS reports_source_external_idx ON reports (source_type, external_id);
CREATE INDEX IF NOT EXISTS reports_event_type_idx ON reports (event_type);

-- ------------------------------------------------------------------------------
-- 2. Incidents (Clustered Weather Events)
-- An incident aggregates multiple independent reports across time and space.
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS incidents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(255) NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL DEFAULT 'MODERATE', -- LOW, MODERATE, HIGH, CRITICAL
    confidence NUMERIC(4, 3) NOT NULL DEFAULT 0.500,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    location GEOGRAPHY(Point, 4326) NOT NULL,
    radius_meters DOUBLE PRECISION DEFAULT 5000.0,
    city VARCHAR(100),
    district VARCHAR(100),
    state VARCHAR(100) NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    last_updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status VARCHAR(50) NOT NULL DEFAULT 'ACTIVE', -- ACTIVE, CONTAINED, RESOLVED, REJECTED
    verification_status VARCHAR(50) NOT NULL DEFAULT 'UNCONFIRMED', -- UNCONFIRMED, AI_CORROBORATED, HUMAN_VERIFIED, HUMAN_REJECTED
    observation_count INT NOT NULL DEFAULT 1,
    summary TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Spatial and query indexes for incidents
CREATE INDEX IF NOT EXISTS incidents_location_gix ON incidents USING GIST (location);
CREATE INDEX IF NOT EXISTS incidents_started_at_idx ON incidents (started_at DESC);
CREATE INDEX IF NOT EXISTS incidents_status_idx ON incidents (status);
CREATE INDEX IF NOT EXISTS incidents_verification_idx ON incidents (verification_status);
CREATE INDEX IF NOT EXISTS incidents_state_district_idx ON incidents (state, district);

-- ------------------------------------------------------------------------------
-- 3. Incident Reports (Many-to-Many Bridge Table)
-- Explicitly binds multiple observations to one incident with association score.
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS incident_reports (
    incident_id UUID NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    report_id UUID NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    association_score NUMERIC(4, 3) DEFAULT 1.000,
    is_primary BOOLEAN DEFAULT FALSE,
    linked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (incident_id, report_id)
);

CREATE INDEX IF NOT EXISTS incident_reports_report_id_idx ON incident_reports (report_id);

-- ------------------------------------------------------------------------------
-- 4. Verification Results (AI & Human Corroboration Engine Signals)
-- Transparent breakdown of all contributing evidence dimensions.
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS verification_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    report_id UUID REFERENCES reports(id) ON DELETE CASCADE,
    incident_id UUID REFERENCES incidents(id) ON DELETE CASCADE,
    source_score NUMERIC(4, 3) DEFAULT 0.000,
    content_score NUMERIC(4, 3) DEFAULT 0.000,
    location_score NUMERIC(4, 3) DEFAULT 0.000,
    temporal_score NUMERIC(4, 3) DEFAULT 0.000,
    weather_correlation_score NUMERIC(4, 3) DEFAULT 0.000,
    media_score NUMERIC(4, 3) DEFAULT 0.000,
    cross_report_score NUMERIC(4, 3) DEFAULT 0.000,
    duplicate_risk NUMERIC(4, 3) DEFAULT 0.000,
    overall_confidence NUMERIC(4, 3) NOT NULL,
    status VARCHAR(50) NOT NULL, -- UNCONFIRMED, AI_CORROBORATED, HUMAN_VERIFIED, HUMAN_REJECTED
    reasons JSONB DEFAULT '[]'::jsonb,
    model_version VARCHAR(50) NOT NULL DEFAULT 'verify-v1.0',
    reviewed_by VARCHAR(100),
    review_notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ------------------------------------------------------------------------------
-- 5. Audit Logs (Immutable Security and Governance Ledger)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    action VARCHAR(100) NOT NULL,
    actor_id VARCHAR(100) NOT NULL,
    actor_role VARCHAR(50) NOT NULL,
    target_type VARCHAR(50) NOT NULL,
    target_id UUID,
    details JSONB DEFAULT '{}'::jsonb,
    ip_address VARCHAR(45),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS audit_logs_created_at_idx ON audit_logs (created_at DESC);
CREATE INDEX IF NOT EXISTS audit_logs_target_idx ON audit_logs (target_type, target_id);
