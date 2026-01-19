# Customer Metrics Tracking System

## Title

Enable OpsMill to track paid customer instance metrics, usage growth, and license compliance through a centralized telemetry platform.

## Status

**Implementation Status:** ✅ Implemented

| Component | Status | Location |
|-----------|--------|----------|
| License Module | ✅ Implemented | `backend/infrahub/license/` |
| Telemetry Storage | ✅ Implemented | `backend/infrahub/telemetry/storage.py` |
| REST API Endpoints | ✅ Implemented | `backend/infrahub/api/telemetry.py` |
| Configuration Options | ✅ Implemented | `backend/infrahub/config.py` |
| SDK CLI Commands | ✅ Implemented | `python_sdk/` |
| Metrics Platform | ✅ Implemented | Separate repository |

## Summary (2–3 sentences)

OpsMill needs a system to collect, store, and analyze telemetry data from paid Infrahub enterprise customers. This enables visibility into customer instance size, usage patterns, growth over time, and license compliance against two north star metrics (Actions and Objects). The system must support both streaming telemetry and manual backfill for airgapped environments.

## Use Cases

### Use Case 1: Customer Success - Instance Health Monitoring

- **Customer / Team**: OpsMill Customer Success team
- **Use Case [situation]**: When monitoring the health and engagement of paid customers, the team needs to see current instance metrics (node counts, user activity, API usage) and detect early warning signs of churn (activity drops, errors). Inputs: telemetry data from customer instances. Outputs: health dashboards, alerts for at-risk customers.
- **Current (how today works)**: Anonymous telemetry is collected but not linked to customer identity. No way to see which customer owns which deployment or track their specific growth trajectory.
- **Problem / Pain**: Cannot proactively identify struggling customers. No visibility into whether customers are getting value from the product. License compliance requires manual audits.
- **Alternative solutions considered**: Manual customer check-ins; relying on support tickets as health signals. Neither scales as customer base grows.
- **Customer Requirements [needs]**:
  - [Must] Link telemetry data to customer identity via license file
  - [Must] Track north star metrics: Actions (configs + branches) and Objects (Neo4j nodes + relationships)
  - [Must] Daily collection of instance metrics
  - [Must] Internal dashboards showing customer health
  - [Nice] Automated alerts for churn risk indicators
  - [Nice] Week-over-week and month-over-month trend comparisons
- **Urgency / Importance**: High importance for scaling customer success operations. No hard timeline but needed before customer base grows significantly.

### Use Case 2: License Compliance Auditing

- **Customer / Team**: OpsMill Sales/Finance team
- **Use Case [situation]**: When auditing customer license compliance, the team needs to compare actual usage against licensed tier thresholds (small/medium/large). Inputs: telemetry metrics, license file data. Outputs: compliance reports, expansion opportunity identification.
- **Current (how today works)**: No automated way to verify customers are within license limits. Requires manual inspection or customer self-reporting.
- **Problem / Pain**: Cannot identify customers exceeding tier limits. Missed upsell opportunities when customers outgrow their tier. Risk of revenue leakage.
- **Alternative solutions considered**: Honor system with periodic manual audits. Does not scale and creates awkward customer conversations.
- **Customer Requirements [needs]**:
  - [Must] License file containing customer name, product tier, support tier, start/end dates
  - [Must] Cryptographic signature on license to prevent tampering
  - [Must] Track Objects metric (total Neo4j database objects) against tier limits
  - [Must] Track Actions metric (configs generated + branches created) against tier limits
  - [Nice] Automated alerts when approaching 80% of tier limits
  - [Nice] Historical usage reports for renewal discussions
- **Urgency / Importance**: Critical for revenue protection and expansion sales. Needed before next major sales push.

### Use Case 3: Airgapped Customer Support

- **Customer / Team**: Enterprise customers in regulated/secure environments (finance, government, defense)
- **Use Case [situation]**: When a customer cannot stream telemetry due to network isolation, they need a way to export telemetry data for manual transfer to OpsMill for support and compliance purposes. Inputs: locally stored telemetry. Outputs: export file that can be emailed or transferred via secure channel.
- **Current (how today works)**: Telemetry either streams to OpsMill endpoint or is lost. No local storage. Airgapped customers have no visibility into their own metrics.
- **Problem / Pain**: Cannot support airgapped customers with usage data. Cannot verify license compliance for airgapped deployments. Customers cannot review what telemetry would be sent.
- **Alternative solutions considered**: Skip telemetry for airgapped customers entirely. Unacceptable for license compliance requirements.
- **Customer Requirements [needs]**:
  - [Must] Store telemetry locally on Infrahub instance (always, regardless of streaming)
  - [Must] CLI command to export telemetry data for a date range
  - [Must] Export includes license information for identity verification
  - [Must] Server-side import API to ingest backfilled data
  - [Nice] Configurable local retention period (default 90 days)
  - [Nice] Customer can review local telemetry files for transparency
- **Urgency / Importance**: Blocker for some enterprise sales. Several prospects in regulated industries require this capability.

## Proposed Solution

### License File System ✅ Implemented

- Introduce a signed license file that binds customer identity to deployment UUID
- License contains: `license_id`, `customer_name`, `deployment_id`, `product_tier` (small/medium/large), `support_tier` (basic/advanced/24x7), `start_date`, `end_date`, `issued_at`, cryptographic `signature`
- Signature validated using HMAC-SHA256 (PoC) or RSA (production)
- Invalid/expired license logs warnings but does not block Infrahub operation

**Implementation:**

- `backend/infrahub/license/models.py` - Pydantic models: `LicenseFile`, `LicenseStatus`, `LicenseTelemetryData`
- `backend/infrahub/license/loader.py` - License loading with caching: `get_current_license()`, `load_license_from_file()`
- `backend/infrahub/license/validator.py` - Signature and date validation
- Configuration: `INFRAHUB_LICENSE_FILE`, `INFRAHUB_LICENSE_SIGNING_KEY`, `INFRAHUB_LICENSE_SKIP_SIGNATURE_VALIDATION`

### Extended Telemetry ✅ Implemented

- Extend existing `backend/infrahub/telemetry/` module to include license data in payload
- Add new metrics for Actions and Objects north star tracking
- Telemetry payload includes license info when present, enabling customer identification server-side

**Implementation:**

- `backend/infrahub/license/models.py` - `LicenseTelemetryData` model for telemetry payloads
- `backend/infrahub/telemetry/tasks.py` - `gather_license_information()` task integrated into telemetry flow

### Local Storage + Streaming ✅ Implemented

- Always save telemetry to local Infrahub instance
- Additionally stream to OpsMill endpoint when network allows
- JSON format, one file per day, configurable retention

**Implementation:**

- `backend/infrahub/telemetry/storage.py` - Local storage functions
- File format: `telemetry-{deployment_id}-{YYYY-MM-DD}.json`
- Configuration: `INFRAHUB_TELEMETRY_STORAGE_PATH` (default: `/var/lib/infrahub/telemetry`)
- Configuration: `INFRAHUB_TELEMETRY_STORAGE_RETENTION_DAYS` (default: 90 days)

### Backfill/Export Mechanism 🔄 Partially Implemented

- REST API endpoints for telemetry export ✅
- `infrahubctl telemetry export` command ⏳ Pending (SDK)
- Export format includes license info + array of daily snapshots ✅
- OpsMill-side import tool ⏳ Pending

**Implementation:**

- `backend/infrahub/api/telemetry.py` - REST API endpoints:
  - `GET /api/telemetry/status` - Configuration and storage status
  - `GET /api/telemetry/list` - List available telemetry files
  - `GET /api/telemetry/export` - Export data with optional date filters (`from_date`, `to_date`, `all`)

### Metrics Platform (Separate Service) ⏳ Pending

- Standalone service receiving telemetry from customer instances
- DB for time-series metrics, another DB (Infrahub?) for customer metadata
- REST API for dashboards: customer health, portfolio overview, at-risk customers
- Internal alerting for churn risk, license limits, instance health

**Planned:** See [customer-metrics-poc-plan.md](../plans/customer-metrics-poc-plan.md) for the PoC repository design.

## Open Questions

### Resolved ✅

- **Cryptographic algorithm for license signatures:** PoC uses HMAC-SHA256 with shared secret. Production will use RSA-2048 with OpsMill public key embedded in Infrahub.
- **License binding:** License is bound to `deployment_id` at generation time. The license file contains the `deployment_id` field.
- **Telemetry export authentication:** Export endpoints require authentication via `get_current_user` dependency (same as other API endpoints).

### Still Open ⏳

- TBD: What happens when a customer's deployment_id changes (e.g., database restore)? Re-issue license?
- TBD: Exact thresholds for tier limits (Objects and Actions)
- TBD: How to handle license renewal - new file, or update existing?

## Assumptions

- Infrahub enterprise edition is a separate package (`infrahub-enterprise`) already detected by telemetry
- Existing `deployment_id` (Root node UUID) is stable and can be used for license binding
- Customers accept that telemetry collection is required for enterprise licenses (opt-out disables some features)
- Daily telemetry collection frequency is sufficient for all use cases
- No real-time streaming requirement - batch daily is acceptable

## Links / Evidence

### Existing Telemetry Infrastructure

- [backend/infrahub/telemetry/](../../backend/infrahub/telemetry/) - Telemetry module
- [backend/infrahub/telemetry/models.py](../../backend/infrahub/telemetry/models.py) - Telemetry data models
- [backend/infrahub/telemetry/tasks.py](../../backend/infrahub/telemetry/tasks.py) - Telemetry collection and sending logic
- [backend/infrahub/config.py](../../backend/infrahub/config.py) - Configuration settings
- [telemetry-schema.json](../../telemetry-schema.json) - JSON Schema for telemetry payload structure

### New Implementation (feature/customer-metrics-telemetry branch)

- [backend/infrahub/license/](../../backend/infrahub/license/) - License module
- [backend/infrahub/license/models.py](../../backend/infrahub/license/models.py) - License data models (`LicenseFile`, `LicenseStatus`, `LicenseTelemetryData`)
- [backend/infrahub/license/loader.py](../../backend/infrahub/license/loader.py) - License loading and caching
- [backend/infrahub/license/validator.py](../../backend/infrahub/license/validator.py) - Signature and date validation
- [backend/infrahub/telemetry/storage.py](../../backend/infrahub/telemetry/storage.py) - Local telemetry storage
- [backend/infrahub/api/telemetry.py](../../backend/infrahub/api/telemetry.py) - REST API endpoints for telemetry export

### Planning Documents

- [customer-metrics-poc-plan.md](../plans/customer-metrics-poc-plan.md) - Detailed PoC implementation plan
