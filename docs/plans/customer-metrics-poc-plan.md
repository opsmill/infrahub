# Customer Metrics Tracking System - Proof of Concept Plan

## Overview

This document outlines the step-by-step plan for creating a Proof of Concept (PoC) for the Customer Metrics Tracking System. The PoC will demonstrate the end-to-end flow from telemetry generation in Infrahub instances through to customer dashboards.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           PoC Architecture                                       │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐         │
│  │ Test Infrahub    │     │ Cloudflare R2    │     │ Metrics Platform │         │
│  │ Instance         │────▶│ (S3-compatible)  │────▶│ (New Repo)       │         │
│  │                  │     │                  │     │                  │         │
│  │ - License file   │     │ - Telemetry JSON │     │ ┌──────────────┐ │         │
│  │ - 5-min telemetry│     │   files          │     │ │ TimescaleDB  │ │         │
│  │ - Export command │     │                  │     │ │ (time-series)│ │         │
│  └──────────────────┘     └──────────────────┘     │ └──────────────┘ │         │
│                                                     │        ▲        │         │
│  ┌──────────────────┐                              │        │        │         │
│  │ infrahubctl      │──────────────────────────────│────────┘        │         │
│  │ telemetry export │  (airgapped import)          │                 │         │
│  └──────────────────┘                              │ ┌──────────────┐ │         │
│                                                     │ │ Infrahub     │ │         │
│                                                     │ │ (Customer    │ │         │
│                                                     │ │  Metadata)   │ │         │
│                                                     │ └──────────────┘ │         │
│                                                     │        │        │         │
│                                                     │        ▼        │         │
│                                                     │ ┌──────────────┐ │         │
│                                                     │ │ Grafana      │ │         │
│                                                     │ │ Dashboards   │ │         │
│                                                     │ └──────────────┘ │         │
│                                                     └──────────────────┘         │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Part 1: New PoC Repository Setup

### 1.1 Repository Structure

Create a new repository with the following structure:

```
infrahub-customer-metrics/
├── README.md
├── pyproject.toml                    # uv-based Python project
├── docker-compose.yml                # All services
├── .env.example                      # Environment variables template
├── .infrahub.yml                     # Infrahub component registry
│
├── schemas/                          # Infrahub schema definitions
│   └── customer_metrics.yml          # Customer and metrics schema
│
├── objects/                          # Sample data (Infrahub object format)
│   └── bootstrap/
│       ├── 00_customers.yml          # Sample customers
│       └── 01_licenses.yml           # Sample license records
│
├── scripts/                          # Automation scripts
│   ├── fetch_telemetry.py            # Fetch from R2 to TimescaleDB
│   ├── sync_to_infrahub.py           # Sync latest metrics to Infrahub
│   └── import_backfill.py            # Import airgapped exports
│
├── grafana/                          # Dashboard configurations
│   ├── provisioning/
│   │   ├── datasources/
│   │   │   ├── timescaledb.yml       # TimescaleDB datasource
│   │   │   └── infrahub.yml          # Infrahub GraphQL datasource
│   │   └── dashboards/
│   │       └── dashboards.yml        # Dashboard provisioning config
│   └── dashboards/
│       ├── customer-detail.json      # Per-customer dashboard
│       ├── portfolio-overview.json   # All customers overview
│       └── health-alerts.json        # At-risk customers
│
├── migrations/                       # TimescaleDB migrations
│   └── 001_initial_schema.sql        # Initial database schema
│
└── tests/                            # Test files
    └── test_telemetry_processing.py
```

### 1.2 Steps to Create Repository

```bash
# Step 1: Create and initialize repository
mkdir infrahub-customer-metrics
cd infrahub-customer-metrics
git init

# Step 2: Initialize uv project
uv init
uv add aioboto3 boto3-stubs[s3] polars pydantic httpx
uv add infrahub-sdk asyncpg psycopg2-binary
uv add --group dev pytest pytest-asyncio ruff mypy

# Step 3: Create directory structure
mkdir -p schemas objects/bootstrap scripts grafana/provisioning/{datasources,dashboards}
mkdir -p grafana/dashboards migrations tests

# Step 4: Create docker-compose.yml
# Step 5: Create .env.example with required variables
# Step 6: Create initial migration files
# Step 7: Create Infrahub schemas
# Step 8: Create sample object data
```

### 1.3 docker-compose.yml Services

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| `timescaledb` | `timescale/timescaledb:latest-pg16` | 5432 | Time-series metrics storage |
| `infrahub-server` | `opsmill/infrahub:latest` | 8000 | Customer metadata + latest metrics |
| `infrahub-db` | `neo4j:5.28-community` | 7687 | Infrahub graph database |
| `infrahub-message-queue` | `rabbitmq:3.13` | 5672 | Infrahub message queue |
| `infrahub-cache` | `redis:7` | 6379 | Infrahub cache |
| `grafana` | `grafana/grafana:latest` | 3000 | Dashboards |

---

## Part 2: TimescaleDB Schema

### 2.1 Database Schema Design

Based on `telemetry-schema.json`, create the following tables:

```sql
-- migrations/001_initial_schema.sql

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Main telemetry snapshots table
CREATE TABLE telemetry_snapshots (
    time                    TIMESTAMPTZ NOT NULL,
    deployment_id           UUID NOT NULL,
    customer_id             UUID,                    -- Linked from license
    payload_format          VARCHAR(8) NOT NULL,
    infrahub_version        VARCHAR(50) NOT NULL,
    infrahub_type           VARCHAR(20) NOT NULL,
    python_version          VARCHAR(20) NOT NULL,
    platform                VARCHAR(50) NOT NULL,
    execution_time          DOUBLE PRECISION,
    checksum                VARCHAR(64) NOT NULL,
    UNIQUE (time, deployment_id)
);

SELECT create_hypertable('telemetry_snapshots', 'time');

-- Worker metrics
CREATE TABLE worker_metrics (
    time                    TIMESTAMPTZ NOT NULL,
    deployment_id           UUID NOT NULL,
    total_workers           INTEGER NOT NULL,
    active_workers          INTEGER NOT NULL,
    FOREIGN KEY (time, deployment_id) REFERENCES telemetry_snapshots(time, deployment_id)
);

SELECT create_hypertable('worker_metrics', 'time');

-- Branch metrics (part of "Actions" north star)
CREATE TABLE branch_metrics (
    time                    TIMESTAMPTZ NOT NULL,
    deployment_id           UUID NOT NULL,
    total_branches          INTEGER NOT NULL,
    FOREIGN KEY (time, deployment_id) REFERENCES telemetry_snapshots(time, deployment_id)
);

SELECT create_hypertable('branch_metrics', 'time');

-- Feature counts
CREATE TABLE feature_metrics (
    time                    TIMESTAMPTZ NOT NULL,
    deployment_id           UUID NOT NULL,
    feature_name            VARCHAR(100) NOT NULL,
    count                   INTEGER NOT NULL,
    FOREIGN KEY (time, deployment_id) REFERENCES telemetry_snapshots(time, deployment_id)
);

SELECT create_hypertable('feature_metrics', 'time');

-- Database metrics (part of "Objects" north star)
CREATE TABLE database_metrics (
    time                    TIMESTAMPTZ NOT NULL,
    deployment_id           UUID NOT NULL,
    database_type           VARCHAR(50) NOT NULL,
    total_nodes             BIGINT NOT NULL,
    total_relationships     BIGINT NOT NULL,
    memory_total            BIGINT,
    memory_available        BIGINT,
    processor_available     INTEGER,
    FOREIGN KEY (time, deployment_id) REFERENCES telemetry_snapshots(time, deployment_id)
);

SELECT create_hypertable('database_metrics', 'time');

-- Node counts by label
CREATE TABLE node_count_by_label (
    time                    TIMESTAMPTZ NOT NULL,
    deployment_id           UUID NOT NULL,
    label                   VARCHAR(100) NOT NULL,
    count                   BIGINT NOT NULL,
    FOREIGN KEY (time, deployment_id) REFERENCES telemetry_snapshots(time, deployment_id)
);

SELECT create_hypertable('node_count_by_label', 'time');

-- Relationship counts by type
CREATE TABLE relationship_count_by_type (
    time                    TIMESTAMPTZ NOT NULL,
    deployment_id           UUID NOT NULL,
    rel_type                VARCHAR(100) NOT NULL,
    count                   BIGINT NOT NULL,
    FOREIGN KEY (time, deployment_id) REFERENCES telemetry_snapshots(time, deployment_id)
);

SELECT create_hypertable('relationship_count_by_type', 'time');

-- Prefect event counts
CREATE TABLE prefect_event_metrics (
    time                    TIMESTAMPTZ NOT NULL,
    deployment_id           UUID NOT NULL,
    event_name              VARCHAR(100) NOT NULL,
    count                   INTEGER NOT NULL,
    FOREIGN KEY (time, deployment_id) REFERENCES telemetry_snapshots(time, deployment_id)
);

SELECT create_hypertable('prefect_event_metrics', 'time');

-- License information (denormalized for easy querying)
CREATE TABLE license_records (
    license_id              UUID PRIMARY KEY,
    deployment_id           UUID NOT NULL UNIQUE,
    customer_name           VARCHAR(255) NOT NULL,
    product_tier            VARCHAR(20) NOT NULL,
    support_tier            VARCHAR(20) NOT NULL,
    start_date              DATE NOT NULL,
    end_date                DATE NOT NULL,
    issued_at               TIMESTAMPTZ NOT NULL,
    signature               TEXT NOT NULL,
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_license_deployment ON license_records(deployment_id);
CREATE INDEX idx_license_customer ON license_records(customer_name);

-- Continuous aggregates for daily rollups
CREATE MATERIALIZED VIEW daily_metrics
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', t.time) AS day,
    t.deployment_id,
    l.customer_name,
    l.product_tier,
    MAX(d.total_nodes) AS max_total_nodes,
    MAX(d.total_relationships) AS max_total_relationships,
    MAX(b.total_branches) AS max_branches,
    MAX(f.count) FILTER (WHERE f.feature_name = 'CoreArtifact') AS artifacts,
    MAX(f.count) FILTER (WHERE f.feature_name = 'CoreTransformation') AS transformations
FROM telemetry_snapshots t
LEFT JOIN license_records l ON t.deployment_id = l.deployment_id
LEFT JOIN database_metrics d ON t.time = d.time AND t.deployment_id = d.deployment_id
LEFT JOIN branch_metrics b ON t.time = b.time AND t.deployment_id = b.deployment_id
LEFT JOIN feature_metrics f ON t.time = f.time AND t.deployment_id = f.deployment_id
GROUP BY time_bucket('1 day', t.time), t.deployment_id, l.customer_name, l.product_tier;

-- Add refresh policy (refresh every hour, keep 30 days)
SELECT add_continuous_aggregate_policy('daily_metrics',
    start_offset => INTERVAL '30 days',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour');

-- North Star metrics view
CREATE VIEW north_star_metrics AS
SELECT
    day,
    deployment_id,
    customer_name,
    product_tier,
    -- Objects: Total Neo4j Database Objects
    (max_total_nodes + max_total_relationships) AS objects,
    -- Actions: Configs (artifacts) + Branches
    (COALESCE(artifacts, 0) + COALESCE(max_branches, 0)) AS actions
FROM daily_metrics;

-- Data retention policy (90 days raw, aggregates kept longer)
SELECT add_retention_policy('telemetry_snapshots', INTERVAL '90 days');
SELECT add_retention_policy('worker_metrics', INTERVAL '90 days');
SELECT add_retention_policy('branch_metrics', INTERVAL '90 days');
SELECT add_retention_policy('feature_metrics', INTERVAL '90 days');
SELECT add_retention_policy('database_metrics', INTERVAL '90 days');
SELECT add_retention_policy('node_count_by_label', INTERVAL '90 days');
SELECT add_retention_policy('relationship_count_by_type', INTERVAL '90 days');
SELECT add_retention_policy('prefect_event_metrics', INTERVAL '90 days');
```

---

## Part 3: Infrahub Schema for Customer Metadata

### 3.1 Schema Definition

Create `schemas/customer_metrics.yml`:

```yaml
---
version: "1.0"

nodes:
  # Customer record - linked to telemetry via deployment_id
  - name: Customer
    namespace: Metrics
    description: "A customer organization with an Infrahub license"
    label: "Customer"
    icon: "mdi:domain"
    default_filter: name__value
    display_labels:
      - name__value
    attributes:
      - name: name
        kind: Text
        label: "Customer Name"
        unique: true
      - name: deployment_id
        kind: Text
        label: "Deployment ID"
        description: "UUID of the Infrahub deployment"
        unique: true
        optional: true
      - name: product_tier
        kind: Dropdown
        label: "Product Tier"
        choices:
          - name: small
            label: "Small"
            color: "#4CAF50"
          - name: medium
            label: "Medium"
            color: "#2196F3"
          - name: large
            label: "Large"
            color: "#9C27B0"
      - name: support_tier
        kind: Dropdown
        label: "Support Tier"
        choices:
          - name: basic
            label: "Basic"
            color: "#9E9E9E"
          - name: advanced
            label: "Advanced"
            color: "#FF9800"
          - name: 24x7
            label: "24x7"
            color: "#F44336"
      - name: contract_start
        kind: DateTime
        label: "Contract Start Date"
      - name: contract_end
        kind: DateTime
        label: "Contract End Date"
      - name: notes
        kind: Text
        label: "Notes"
        optional: true
    relationships:
      - name: license
        peer: MetricsLicense
        cardinality: one
        optional: true
      - name: contacts
        peer: MetricsContact
        cardinality: many
        optional: true
      - name: latest_metrics
        peer: MetricsSnapshot
        cardinality: one
        optional: true
        description: "Most recent metrics snapshot"

  # License record
  - name: License
    namespace: Metrics
    description: "License file information"
    label: "License"
    icon: "mdi:license"
    attributes:
      - name: license_id
        kind: Text
        label: "License ID"
        unique: true
      - name: signature
        kind: Text
        label: "Signature"
        description: "Cryptographic signature"
      - name: issued_at
        kind: DateTime
        label: "Issued At"
      - name: valid
        kind: Boolean
        label: "Valid"
        description: "Whether signature validation passed"
    relationships:
      - name: customer
        peer: MetricsCustomer
        cardinality: one

  # Contact for the customer
  - name: Contact
    namespace: Metrics
    description: "Customer contact person"
    label: "Contact"
    icon: "mdi:account"
    display_labels:
      - name__value
      - email__value
    attributes:
      - name: name
        kind: Text
        label: "Name"
      - name: email
        kind: Text
        label: "Email"
      - name: role
        kind: Dropdown
        label: "Role"
        choices:
          - name: technical
            label: "Technical"
          - name: billing
            label: "Billing"
          - name: executive
            label: "Executive"
    relationships:
      - name: customer
        peer: MetricsCustomer
        cardinality: one

  # Latest metrics snapshot (denormalized from TimescaleDB)
  - name: Snapshot
    namespace: Metrics
    description: "Latest telemetry snapshot for a customer"
    label: "Metrics Snapshot"
    icon: "mdi:chart-line"
    attributes:
      - name: snapshot_time
        kind: DateTime
        label: "Snapshot Time"
      - name: infrahub_version
        kind: Text
        label: "Infrahub Version"
      - name: infrahub_type
        kind: Text
        label: "Infrahub Type"
      - name: total_nodes
        kind: Number
        label: "Total Nodes"
      - name: total_relationships
        kind: Number
        label: "Total Relationships"
      - name: total_branches
        kind: Number
        label: "Total Branches"
      - name: total_workers
        kind: Number
        label: "Total Workers"
      - name: active_workers
        kind: Number
        label: "Active Workers"
      - name: objects_metric
        kind: Number
        label: "Objects (North Star)"
        description: "Total nodes + relationships"
      - name: actions_metric
        kind: Number
        label: "Actions (North Star)"
        description: "Artifacts + branches"
      - name: health_status
        kind: Dropdown
        label: "Health Status"
        choices:
          - name: healthy
            label: "Healthy"
            color: "#4CAF50"
          - name: warning
            label: "Warning"
            color: "#FF9800"
          - name: critical
            label: "Critical"
            color: "#F44336"
          - name: unknown
            label: "Unknown"
            color: "#9E9E9E"
    relationships:
      - name: customer
        peer: MetricsCustomer
        cardinality: one
```

### 3.2 Sample Object Data

Create `objects/bootstrap/00_customers.yml`:

```yaml
---
apiVersion: infrahub.app/v1
kind: Object
spec:
  kind: MetricsCustomer
  data:
    - name: Acme Corporation
      deployment_id: "550e8400-e29b-41d4-a716-446655440001"
      product_tier: medium
      support_tier: advanced
      contract_start: "2024-01-01T00:00:00Z"
      contract_end: "2025-12-31T23:59:59Z"
      notes: "Key enterprise customer, expanding usage"

    - name: TechStart Inc
      deployment_id: "550e8400-e29b-41d4-a716-446655440002"
      product_tier: small
      support_tier: basic
      contract_start: "2024-06-15T00:00:00Z"
      contract_end: "2025-06-14T23:59:59Z"
      notes: "Startup, potential for growth"

    - name: Global Networks Ltd
      deployment_id: "550e8400-e29b-41d4-a716-446655440003"
      product_tier: large
      support_tier: 24x7
      contract_start: "2023-01-01T00:00:00Z"
      contract_end: "2026-12-31T23:59:59Z"
      notes: "Enterprise customer with multi-year contract"
```

---

## Part 4: Telemetry Fetch Script

### 4.1 Script: `scripts/fetch_telemetry.py`

This script fetches telemetry from Cloudflare R2 and inserts into TimescaleDB.

Key components:
1. Async S3 client for Cloudflare R2 (pattern from infrahub-telemetry-processor)
2. Pydantic models for validation
3. TimescaleDB insertion with proper type handling
4. Deduplication via UPSERT

```python
# scripts/fetch_telemetry.py
"""
Fetch telemetry data from Cloudflare R2 and insert into TimescaleDB.

Usage:
    uv run python scripts/fetch_telemetry.py
    uv run python scripts/fetch_telemetry.py --since 2025-01-01
"""

import asyncio
import json
import os
from datetime import datetime, date
from pathlib import Path
from typing import AsyncGenerator, Any

import aioboto3
import asyncpg
from pydantic import BaseModel, Field

# Configuration from environment
CF_R2_URL = os.getenv("CF_R2_URL")
CF_R2_BUCKET = os.getenv("CF_R2_BUCKET", "infrahub-public-telemetry")
TIMESCALE_DSN = os.getenv("TIMESCALE_DSN", "postgresql://postgres:postgres@localhost:5432/metrics")
DATA_CACHE_DIR = Path("./data")

# ... (Full implementation following infrahub-telemetry-processor patterns)
```

### 4.2 Script: `scripts/sync_to_infrahub.py`

Syncs latest metrics from TimescaleDB to Infrahub:

```python
# scripts/sync_to_infrahub.py
"""
Sync latest telemetry metrics from TimescaleDB to Infrahub customer records.

Usage:
    uv run python scripts/sync_to_infrahub.py
"""

import asyncio
import os
from datetime import datetime

import asyncpg
from infrahub_sdk import InfrahubClient

TIMESCALE_DSN = os.getenv("TIMESCALE_DSN")
INFRAHUB_URL = os.getenv("INFRAHUB_URL", "http://localhost:8000")
INFRAHUB_TOKEN = os.getenv("INFRAHUB_API_TOKEN")

async def get_latest_metrics(pool: asyncpg.Pool) -> list[dict]:
    """Get the most recent metrics for each customer."""
    query = """
    SELECT DISTINCT ON (l.customer_name)
        l.customer_name,
        l.deployment_id,
        t.time as snapshot_time,
        t.infrahub_version,
        t.infrahub_type,
        d.total_nodes,
        d.total_relationships,
        b.total_branches,
        w.total_workers,
        w.active_workers
    FROM license_records l
    JOIN telemetry_snapshots t ON l.deployment_id = t.deployment_id
    LEFT JOIN database_metrics d ON t.time = d.time AND t.deployment_id = d.deployment_id
    LEFT JOIN branch_metrics b ON t.time = b.time AND t.deployment_id = b.deployment_id
    LEFT JOIN worker_metrics w ON t.time = w.time AND t.deployment_id = w.deployment_id
    ORDER BY l.customer_name, t.time DESC
    """
    return await pool.fetch(query)

async def sync_to_infrahub(client: InfrahubClient, metrics: list[dict]) -> None:
    """Update Infrahub customer records with latest metrics."""
    for m in metrics:
        # Find or create MetricsSnapshot
        # Link to MetricsCustomer
        # ... implementation
        pass

async def main():
    pool = await asyncpg.create_pool(TIMESCALE_DSN)
    client = InfrahubClient(address=INFRAHUB_URL, api_token=INFRAHUB_TOKEN)

    metrics = await get_latest_metrics(pool)
    await sync_to_infrahub(client, metrics)

    await pool.close()

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Part 5: Infrahub Changes ✅ IMPLEMENTED

### 5.1 Create Development Branch

```bash
cd /Users/pete/src/infrahub
git checkout develop
git pull origin develop
git checkout -b feature/customer-metrics-telemetry
```

**Status:** ✅ Branch created: `feature/customer-metrics-telemetry`

### 5.2 Changes Implemented

| Change | Location | Status |
|--------|----------|--------|
| **License file loading** | `backend/infrahub/config.py` | ✅ Implemented |
| **License models** | `backend/infrahub/license/models.py` | ✅ Implemented |
| **License validation** | `backend/infrahub/license/validator.py` | ✅ Implemented |
| **License loader** | `backend/infrahub/license/loader.py` | ✅ Implemented |
| **License constants** | `backend/infrahub/license/constants.py` | ✅ Implemented |
| **Telemetry local storage** | `backend/infrahub/telemetry/storage.py` | ✅ Implemented |
| **Telemetry REST API** | `backend/infrahub/api/telemetry.py` | ✅ Implemented |
| **Config options** | `backend/infrahub/config.py` | ✅ Implemented |

### 5.3 Implementation Details

#### 5.3.1 License File Module ✅

The license module is implemented at `backend/infrahub/license/`:

```
backend/infrahub/license/
├── __init__.py           # Module exports
├── models.py             # Pydantic models (LicenseFile, LicenseStatus, LicenseTelemetryData)
├── validator.py          # Signature validation (HMAC-SHA256 for PoC)
├── loader.py             # Load and cache license from file
├── constants.py          # Public key placeholder, schema version
└── generator.py          # License generation utility (development)
```

**License Model** (`backend/infrahub/license/models.py`):

```python
from datetime import date, datetime
from enum import StrEnum
from pydantic import BaseModel, Field
from uuid import UUID

class ProductTier(StrEnum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"

class SupportTier(StrEnum):
    BASIC = "basic"
    ADVANCED = "advanced"
    TWENTYFOUR_SEVEN = "24x7"

class LicenseFile(BaseModel):
    """License file data structure."""
    license_id: UUID
    customer_name: str
    deployment_id: UUID
    product_tier: ProductTier
    support_tier: SupportTier
    start_date: date
    end_date: date
    issued_at: datetime
    signature: str = Field(description="Base64-encoded cryptographic signature")

    def is_expired(self) -> bool:
        """Check if the license has expired."""
        return datetime.now(tz=UTC).date() > self.end_date

    def is_not_yet_valid(self) -> bool:
        """Check if the license is not yet valid (start date in future)."""
        return datetime.now(tz=UTC).date() < self.start_date

    def is_within_validity_period(self) -> bool:
        """Check if current date is within the license validity period."""
        today = datetime.now(tz=UTC).date()
        return self.start_date <= today <= self.end_date

class LicenseStatus(BaseModel):
    """Validation result for a license."""
    valid: bool
    license_data: LicenseFile | None = None
    error: str | None = None
    warnings: list[str] = []

    @classmethod
    def invalid(cls, error: str) -> LicenseStatus:
        """Create an invalid license status with an error message."""
        return cls(valid=False, error=error)

    @classmethod
    def success(cls, license_data: LicenseFile, warnings: list[str] | None = None) -> LicenseStatus:
        """Create a valid license status with the parsed data."""
        return cls(valid=True, license_data=license_data, warnings=warnings or [])

class LicenseTelemetryData(BaseModel):
    """License information included in telemetry payloads."""
    license_id: str
    customer_name: str
    deployment_id: str
    product_tier: ProductTier
    support_tier: SupportTier

    @classmethod
    def from_license(cls, license_file: LicenseFile) -> LicenseTelemetryData:
        """Create telemetry data from a license file."""
        return cls(
            license_id=str(license_file.license_id),
            customer_name=license_file.customer_name,
            deployment_id=str(license_file.deployment_id),
            product_tier=license_file.product_tier,
            support_tier=license_file.support_tier,
        )
```

#### 5.3.2 Config Changes ✅

Added to `backend/infrahub/config.py`:

```python
class MainSettings(BaseSettings):
    # ... existing fields ...

    # Telemetry development mode
    telemetry_dev_interval_minutes: int | None = Field(
        default=None,
        description="Override telemetry interval for development (minutes)",
        validation_alias=AliasChoices("INFRAHUB_TELEMETRY_DEV_INTERVAL", "telemetry_dev_interval_minutes"),
    )

    # Telemetry local storage
    telemetry_storage_path: str = Field(
        default="/var/lib/infrahub/telemetry",
        description="Path for local telemetry storage",
        validation_alias=AliasChoices("INFRAHUB_TELEMETRY_STORAGE_PATH", "telemetry_storage_path"),
    )
    telemetry_storage_retention_days: int = Field(
        default=90,
        description="Number of days to retain local telemetry files",
        validation_alias=AliasChoices(
            "INFRAHUB_TELEMETRY_STORAGE_RETENTION_DAYS", "telemetry_storage_retention_days"
        ),
    )

    # License configuration
    license_file_path: str | None = Field(
        default=None,
        description="Path to the license file (JSON)",
        validation_alias=AliasChoices("INFRAHUB_LICENSE_FILE", "license_file_path"),
    )
    license_signing_key: str | None = Field(
        default=None,
        description="Secret key for license signature verification (PoC only)",
        validation_alias=AliasChoices("INFRAHUB_LICENSE_SIGNING_KEY", "license_signing_key"),
    )
    license_skip_signature_validation: bool = Field(
        default=False,
        description="Skip license signature validation (development only)",
        validation_alias=AliasChoices(
            "INFRAHUB_LICENSE_SKIP_SIGNATURE_VALIDATION", "license_skip_signature_validation"
        ),
    )
```

#### 5.3.3 Telemetry Local Storage ✅

Implemented in `backend/infrahub/telemetry/storage.py`:

**Features:**
- `save_telemetry_locally(data, deployment_id)` - Saves JSON telemetry to disk
- `cleanup_old_telemetry()` - Removes files older than retention period
- `list_local_telemetry(from_date, to_date)` - Lists available files with date filtering
- `get_local_telemetry_status()` - Returns storage status information
- `load_telemetry_file(filepath)` - Loads a telemetry file from disk

**File naming convention:** `telemetry-{deployment_id}-{YYYY-MM-DD}.json`

#### 5.3.4 Telemetry Task Integration ✅

The `backend/infrahub/telemetry/tasks.py` has been updated to:

1. **Gather license information** via `gather_license_information()` task
2. **Include license data** in telemetry payload when available
3. **Save locally first** before streaming to endpoint
4. **Clean up old files** after each telemetry push

```python
# Always save locally first (for airgapped export and audit)
deployment_id = data.deployment_id or "unknown"
try:
    await save_telemetry_locally(payload, deployment_id)
except OSError as e:
    log.warning(f"Failed to save telemetry locally: {e}")

# Clean up old telemetry files
try:
    await cleanup_old_telemetry()
except OSError as e:
    log.warning(f"Failed to cleanup old telemetry files: {e}")
```

#### 5.3.5 REST API Endpoints ✅

Implemented in `backend/infrahub/api/telemetry.py` and registered in `backend/infrahub/api/__init__.py`:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/telemetry/status` | GET | Get telemetry configuration and status |
| `/api/telemetry/list` | GET | List available local telemetry files |
| `/api/telemetry/export` | GET | Export telemetry data for airgapped transfer |

**Export endpoint parameters:**
- `from_date` (optional): Start date for export range (YYYY-MM-DD)
- `to_date` (optional): End date for export range (YYYY-MM-DD)
- `all` (optional): Export all available data regardless of date range

**Response models:**
- `TelemetryStatusResponse` - Configuration and storage status
- `TelemetryListResponse` - List of available files
- `TelemetryExportResponse` - Full export with license info and snapshots

---

## Part 6: SDK Changes (infrahubctl telemetry export) ⏳ PENDING

> **Note:** SDK changes are pending. The REST API endpoints in Part 5 are implemented and ready for the SDK to consume.

### 6.1 Create Development Branch

```bash
cd /Users/pete/src/infrahub-sdk-python
git checkout main
git pull origin main
git checkout -b feature/telemetry-export
```

### 6.2 Implementation

Create `infrahub_sdk/ctl/telemetry.py`:

```python
"""Telemetry CLI commands for Infrahub SDK."""

from datetime import datetime
from pathlib import Path
from typing import Optional
import json

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..async_typer import AsyncTyper
from .client import initialize_client
from .parameters import CONFIG_PARAM
from .utils import catch_exception

console = Console()
app = AsyncTyper()


@app.callback()
def callback() -> None:
    """Manage telemetry data export and operations."""


@app.command(name="export")
@catch_exception(console=console)
async def export_telemetry(
    output: Path = typer.Option(
        Path("telemetry-export.json"),
        "--output", "-o",
        help="Output file path for the export",
    ),
    from_date: Optional[str] = typer.Option(
        None,
        "--from",
        help="Start date for export range (YYYY-MM-DD)",
    ),
    to_date: Optional[str] = typer.Option(
        None,
        "--to",
        help="End date for export range (YYYY-MM-DD)",
    ),
    export_all: bool = typer.Option(
        False,
        "--all",
        help="Export all available telemetry data",
    ),
    branch: Optional[str] = typer.Option(
        None,
        "--branch", "-b",
        help="Branch to use for queries",
    ),
    _: str = CONFIG_PARAM,
) -> None:
    """Export telemetry data from Infrahub for airgapped transfer.

    This command exports locally stored telemetry data into a format
    suitable for manual transfer to OpsMill for airgapped environments.

    Examples:
        # Export last 30 days
        infrahubctl telemetry export --from 2025-01-01 --to 2025-01-31

        # Export all available data
        infrahubctl telemetry export --all

        # Export to specific file
        infrahubctl telemetry export --all --output my-export.json
    """
    client = initialize_client(branch=branch)

    # Query the REST API for telemetry export
    # This requires a new REST endpoint in Infrahub backend
    params = {}
    if from_date:
        params["from_date"] = from_date
    if to_date:
        params["to_date"] = to_date
    if export_all:
        params["all"] = "true"

    response = await client._get("/api/telemetry/export", params=params)

    if response.status_code != 200:
        console.print(f"[red]Error: {response.text}[/red]")
        raise typer.Exit(1)

    export_data = response.json()

    # Write to file
    with open(output, "w") as f:
        json.dump(export_data, f, indent=2, default=str)

    # Show summary
    snapshots = export_data.get("snapshots", [])
    license_info = export_data.get("license", {})

    table = Table(title="Export Summary")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Customer", license_info.get("customer_name", "Unknown"))
    table.add_row("Product Tier", license_info.get("product_tier", "Unknown"))
    table.add_row("Snapshots", str(len(snapshots)))
    if snapshots:
        table.add_row("Date Range", f"{snapshots[0]['date']} - {snapshots[-1]['date']}")
    table.add_row("Output File", str(output))

    console.print(table)
    console.print(Panel(f"[green]Export complete: {output}[/green]"))


@app.command(name="list")
@catch_exception(console=console)
async def list_telemetry(
    branch: Optional[str] = typer.Option(None, "--branch", "-b"),
    _: str = CONFIG_PARAM,
) -> None:
    """List available local telemetry files."""
    client = initialize_client(branch=branch)

    response = await client._get("/api/telemetry/list")

    if response.status_code != 200:
        console.print(f"[red]Error: {response.text}[/red]")
        raise typer.Exit(1)

    files = response.json().get("files", [])

    if not files:
        console.print("[yellow]No telemetry files found[/yellow]")
        return

    table = Table(title="Local Telemetry Files")
    table.add_column("Date", style="cyan")
    table.add_column("File", style="green")
    table.add_column("Size", style="yellow")

    for f in files:
        table.add_row(f["date"], f["filename"], f["size"])

    console.print(table)
```

Register in `infrahub_sdk/ctl/cli_commands.py`:

```python
from .telemetry import app as telemetry_app

# Add after other app.add_typer calls
app.add_typer(telemetry_app, name="telemetry")
```

### 6.3 Backend REST Endpoint ✅ IMPLEMENTED

The REST API endpoints are already implemented in `backend/infrahub/api/telemetry.py` (see Part 5.3.5).

The SDK will consume these endpoints:

- `GET /api/telemetry/status` - Get telemetry configuration status
- `GET /api/telemetry/list` - List available telemetry files
- `GET /api/telemetry/export` - Export telemetry data with optional date filters

### 6.4 Build and Test SDK

```bash
cd /Users/pete/src/infrahub-sdk-python

# Build and install locally
uv build
uv pip install dist/infrahub_sdk-*.whl --force-reinstall

# Or for development
uv sync --all-groups
uv run infrahubctl telemetry --help
```

---

## Part 7: Dashboard Setup (Grafana)

### 7.1 Recommended Tool: Grafana

Grafana is the recommended choice because:
- Native TimescaleDB/PostgreSQL support
- GraphQL datasource plugin for Infrahub queries
- Rich visualization options
- Easy container deployment
- Provisioning via config files

### 7.2 Grafana Configuration

**docker-compose.yml addition:**

```yaml
services:
  grafana:
    image: grafana/grafana:latest
    container_name: metrics-grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
      - GF_INSTALL_PLUGINS=marcusolsson-json-datasource,fifemon-graphql-datasource
    volumes:
      - grafana-data:/var/lib/grafana
      - ./grafana/provisioning:/etc/grafana/provisioning
      - ./grafana/dashboards:/var/lib/grafana/dashboards
    depends_on:
      - timescaledb
      - infrahub-server

volumes:
  grafana-data:
```

**Datasources provisioning** (`grafana/provisioning/datasources/datasources.yml`):

```yaml
apiVersion: 1

datasources:
  - name: TimescaleDB
    type: postgres
    url: timescaledb:5432
    database: metrics
    user: postgres
    secureJsonData:
      password: postgres
    jsonData:
      sslmode: disable
      maxOpenConns: 10
      maxIdleConns: 10
      connMaxLifetime: 14400
      postgresVersion: 1600
      timescaledb: true

  - name: Infrahub
    type: fifemon-graphql-datasource
    url: http://infrahub-server:8000/graphql
    jsonData:
      httpHeaderName1: "Authorization"
    secureJsonData:
      httpHeaderValue1: "Bearer ${INFRAHUB_API_TOKEN}"
```

**Dashboard provisioning** (`grafana/provisioning/dashboards/dashboards.yml`):

```yaml
apiVersion: 1

providers:
  - name: 'Customer Metrics'
    orgId: 1
    folder: 'Customer Metrics'
    folderUid: customer-metrics
    type: file
    disableDeletion: false
    updateIntervalSeconds: 30
    options:
      path: /var/lib/grafana/dashboards
```

### 7.3 Dashboard Definitions

#### Customer Detail Dashboard (`grafana/dashboards/customer-detail.json`)

Variables:
- `customer` - Dropdown populated from `SELECT DISTINCT customer_name FROM license_records`

Panels:
1. **North Star Metrics** - Stat panels for Objects and Actions
2. **Objects Over Time** - Time series of total nodes + relationships
3. **Actions Over Time** - Time series of artifacts + branches
4. **Tier Utilization** - Gauge showing % of tier limits used
5. **Instance Health** - Status indicators (workers, version, etc.)
6. **Feature Usage** - Bar chart of feature counts
7. **Event Activity** - Heatmap of Prefect events

#### Portfolio Overview Dashboard (`grafana/dashboards/portfolio-overview.json`)

Panels:
1. **Customer Summary** - Table of all customers with key metrics
2. **Objects Distribution** - Pie chart by tier
3. **Growth Trends** - Multi-line chart of growth rates
4. **Version Distribution** - Bar chart of Infrahub versions
5. **Health Overview** - Traffic light status for all customers

#### Health & Alerts Dashboard (`grafana/dashboards/health-alerts.json`)

Panels:
1. **At-Risk Customers** - Table filtered by health criteria
2. **License Expiring Soon** - List of contracts ending within 30 days
3. **Tier Limit Approaching** - Customers near 80% of limits
4. **Missing Telemetry** - Customers with no data in 48+ hours

---

## Part 8: Complete Step-by-Step Implementation Plan

### Phase 1: Repository Setup (Day 1) ⏳ PENDING

| Step | Task | Command/Action | Status |
|------|------|----------------|--------|
| 1.1 | Create new repository | `mkdir infrahub-customer-metrics && cd $_` | ⏳ |
| 1.2 | Initialize git | `git init` | ⏳ |
| 1.3 | Initialize uv project | `uv init` | ⏳ |
| 1.4 | Add Python dependencies | `uv add aioboto3 polars pydantic httpx asyncpg infrahub-sdk` | ⏳ |
| 1.5 | Create directory structure | `mkdir -p schemas objects/bootstrap scripts grafana/...` | ⏳ |
| 1.6 | Create docker-compose.yml | Write file with all services | ⏳ |
| 1.7 | Create .env.example | Document required environment variables | ⏳ |
| 1.8 | Write TimescaleDB migrations | Create `migrations/001_initial_schema.sql` | ⏳ |
| 1.9 | Write Infrahub schema | Create `schemas/customer_metrics.yml` | ⏳ |
| 1.10 | Write sample data | Create `objects/bootstrap/00_customers.yml` | ⏳ |

### Phase 2: Infrahub Development Branch (Day 2) ✅ COMPLETED

| Step | Task | Location | Status |
|------|------|----------|--------|
| 2.1 | Create feature branch | `git checkout -b feature/customer-metrics-telemetry` | ✅ |
| 2.2 | Create license module | `backend/infrahub/license/` | ✅ |
| 2.3 | Add license models | `backend/infrahub/license/models.py` | ✅ |
| 2.4 | Add license validator | `backend/infrahub/license/validator.py` | ✅ |
| 2.5 | Add license loader | `backend/infrahub/license/loader.py` | ✅ |
| 2.6 | Update config | `backend/infrahub/config.py` | ✅ |
| 2.7 | Create telemetry storage | `backend/infrahub/telemetry/storage.py` | ✅ |
| 2.8 | Update telemetry task | `backend/infrahub/telemetry/tasks.py` | ✅ |
| 2.9 | Update workflow schedule | `backend/infrahub/workflows/catalogue.py` | ⏳ |
| 2.10 | Add REST API endpoints | `backend/infrahub/api/telemetry.py` | ✅ |
| 2.11 | Write unit tests | `backend/tests/unit/telemetry/` | ⏳ |
| 2.12 | Run linters | `uv run invoke lint format` | ⏳ |

### Phase 3: SDK Development Branch (Day 3) ⏳ PENDING

| Step | Task | Location | Status |
|------|------|----------|--------|
| 3.1 | Create feature branch | `git checkout -b feature/telemetry-export` | ⏳ |
| 3.2 | Create telemetry CLI module | `infrahub_sdk/ctl/telemetry.py` | ⏳ |
| 3.3 | Register in cli_commands | `infrahub_sdk/ctl/cli_commands.py` | ⏳ |
| 3.4 | Write unit tests | `tests/unit/ctl/test_telemetry.py` | ⏳ |
| 3.5 | Build and install locally | `uv build && uv pip install dist/*.whl` | ⏳ |
| 3.6 | Test commands | `infrahubctl telemetry --help` | ⏳ |

### Phase 4: Scripts and Integration (Day 4) ⏳ PENDING

| Step | Task | Location | Status |
|------|------|----------|--------|
| 4.1 | Write fetch_telemetry.py | `scripts/fetch_telemetry.py` | ⏳ |
| 4.2 | Write sync_to_infrahub.py | `scripts/sync_to_infrahub.py` | ⏳ |
| 4.3 | Write import_backfill.py | `scripts/import_backfill.py` | ⏳ |
| 4.4 | Test R2 connectivity | Run fetch script with test credentials | ⏳ |
| 4.5 | Test TimescaleDB inserts | Verify data in database | ⏳ |
| 4.6 | Test Infrahub sync | Verify customer records updated | ⏳ |

### Phase 5: Grafana Dashboards (Day 5) ⏳ PENDING

| Step | Task | Location | Status |
|------|------|----------|--------|
| 5.1 | Configure datasources | `grafana/provisioning/datasources/` | ⏳ |
| 5.2 | Create customer-detail dashboard | `grafana/dashboards/customer-detail.json` | ⏳ |
| 5.3 | Create portfolio-overview dashboard | `grafana/dashboards/portfolio-overview.json` | ⏳ |
| 5.4 | Create health-alerts dashboard | `grafana/dashboards/health-alerts.json` | ⏳ |
| 5.5 | Test dashboard variable | Verify customer dropdown works | ⏳ |
| 5.6 | Test all panels | Verify data displays correctly | ⏳ |

### Phase 6: End-to-End Testing (Day 6) ⏳ PENDING

| Step | Task | Description | Status |
|------|------|-------------|--------|
| 6.1 | Start all containers | `docker-compose up -d` | ⏳ |
| 6.2 | Run migrations | Apply TimescaleDB schema | ⏳ |
| 6.3 | Load Infrahub schema | `infrahubctl schema load` | ⏳ |
| 6.4 | Load sample data | `infrahubctl object load` | ⏳ |
| 6.5 | Start test Infrahub | With 5-minute telemetry interval | ⏳ |
| 6.6 | Wait for telemetry | Verify local files created | ⏳ |
| 6.7 | Test export command | `infrahubctl telemetry export` | ⏳ |
| 6.8 | Test backfill import | `uv run python scripts/import_backfill.py` | ⏳ |
| 6.9 | Verify dashboards | Check Grafana shows data | ⏳ |

---

## Part 9: Environment Variables

### Required for PoC Repository

```bash
# .env.example

# Cloudflare R2 (S3-compatible)
CF_R2_URL=https://<account-id>.r2.cloudflarestorage.com
CF_R2_BUCKET=infrahub-public-telemetry
AWS_ACCESS_KEY_ID=<cloudflare-access-key>
AWS_SECRET_ACCESS_KEY=<cloudflare-secret-key>

# TimescaleDB
TIMESCALE_DSN=postgresql://postgres:postgres@localhost:5432/metrics

# Infrahub (for sync script and Grafana)
INFRAHUB_URL=http://localhost:8000
INFRAHUB_API_TOKEN=<your-token>

# Grafana
GF_SECURITY_ADMIN_PASSWORD=admin
```

### Required for Infrahub Test Instance ✅

```bash
# Enable 5-minute telemetry for testing
INFRAHUB_TELEMETRY_DEV_INTERVAL=5

# License file path
INFRAHUB_LICENSE_FILE=/path/to/license.json

# Local telemetry storage
INFRAHUB_TELEMETRY_STORAGE_PATH=/var/lib/infrahub/telemetry
INFRAHUB_TELEMETRY_STORAGE_RETENTION_DAYS=90

# License signature validation (PoC only - for development)
INFRAHUB_LICENSE_SIGNING_KEY=your-secret-key
INFRAHUB_LICENSE_SKIP_SIGNATURE_VALIDATION=true  # Set to true during development
```

---

## Part 10: Testing Checklist

### Unit Tests

- [ ] License file parsing
- [ ] License signature validation (mock)
- [ ] Telemetry local storage
- [ ] Telemetry export endpoint
- [ ] SDK telemetry export command
- [ ] TimescaleDB schema migrations

### Integration Tests

- [ ] License loaded on Infrahub startup
- [ ] Telemetry includes license info when present
- [ ] Telemetry saved locally on each push
- [ ] 5-minute interval works in dev mode
- [ ] Export command retrieves local files
- [ ] Fetch script connects to R2
- [ ] Sync script updates Infrahub
- [ ] Grafana connects to both datasources

### End-to-End Tests

- [ ] Full flow: Infrahub → Local → R2 → TimescaleDB → Infrahub → Grafana
- [ ] Airgapped flow: Local → Export → Import → TimescaleDB
- [ ] Dashboard variable filtering
- [ ] North star metrics calculation

---

## Summary

This plan covers:

| Component | Description | Status |
|-----------|-------------|--------|
| **New PoC Repository** | Complete structure with docker-compose, schemas, scripts, and Grafana configs | ⏳ Pending |
| **TimescaleDB Schema** | Hypertables, continuous aggregates, and retention policies | ⏳ Pending |
| **Infrahub Schema** | Customer metadata model for the metrics platform | ⏳ Pending |
| **Infrahub Changes** | License module, local storage, dev mode, REST API | ✅ Implemented |
| **SDK Changes** | `infrahubctl telemetry export` command | ⏳ Pending |
| **Dashboard Setup** | Grafana with three dashboard types | ⏳ Pending |
| **Step-by-Step Plan** | Day-by-day implementation guide | 📋 Documented |

The plan enables both streaming telemetry and airgapped export/import workflows while tracking the two north star metrics (Actions and Objects) for license compliance.

---

## Implementation Progress

### Completed ✅

The following components have been implemented in the `feature/customer-metrics-telemetry` branch:

**License Module** (`backend/infrahub/license/`):

- `models.py` - `LicenseFile`, `LicenseStatus`, `LicenseTelemetryData`, `ProductTier`, `SupportTier`
- `loader.py` - License loading and caching (`get_current_license`, `load_license_from_file`, `reload_license`)
- `validator.py` - Signature validation with HMAC-SHA256 (PoC), date range validation
- `constants.py` - Public key placeholder, schema version

**Telemetry Storage** (`backend/infrahub/telemetry/storage.py`):

- `save_telemetry_locally()` - Saves JSON telemetry to configured path
- `cleanup_old_telemetry()` - Removes files older than retention period
- `list_local_telemetry()` - Lists files with optional date filtering
- `get_local_telemetry_status()` - Returns storage status information
- `load_telemetry_file()` - Loads telemetry data from disk

**REST API** (`backend/infrahub/api/telemetry.py`):

- `GET /api/telemetry/status` - Configuration and storage status
- `GET /api/telemetry/list` - List available telemetry files
- `GET /api/telemetry/export` - Export data for airgapped transfer

**Configuration** (`backend/infrahub/config.py`):

- `INFRAHUB_TELEMETRY_DEV_INTERVAL` - Override telemetry interval for testing
- `INFRAHUB_TELEMETRY_STORAGE_PATH` - Local storage path (default: `/var/lib/infrahub/telemetry`)
- `INFRAHUB_TELEMETRY_STORAGE_RETENTION_DAYS` - Retention period (default: 90 days)
- `INFRAHUB_LICENSE_FILE` - Path to license JSON file
- `INFRAHUB_LICENSE_SIGNING_KEY` - Secret key for PoC signature validation
- `INFRAHUB_LICENSE_SKIP_SIGNATURE_VALIDATION` - Skip validation in development

**Telemetry Task Integration** (`backend/infrahub/telemetry/tasks.py`):

- License information gathering task
- Local storage before streaming to endpoint
- Automatic cleanup of old telemetry files

### Remaining Work ⏳

1. **Unit tests** for license module and telemetry storage
2. **Workflow schedule update** for dev interval mode
3. **SDK CLI commands** for telemetry export
4. **PoC repository** with TimescaleDB, Infrahub schema, and Grafana dashboards
5. **Integration testing** end-to-end
