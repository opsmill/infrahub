# Feature Specification: Local Telemetry Storage

**Feature Branch**: `fac-001-local-telemetry-storage`
**Created**: 2026-02-16
**Status**: Draft
**Input**: User description: "Store daily telemetry JSON files in the database regardless of telemetry opt-out settings, so air-gapped and opted-out customers retain usage data for support, auditing, and license compliance. Include data in backups, tech support exports, and a manual CLI export command."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Automatic Daily Telemetry Persistence (Priority: P1)

As an Infrahub deployment, the system automatically collects and stores a daily usage snapshot locally, regardless of whether remote telemetry reporting is enabled or disabled. This ensures that usage data is never lost, even in air-gapped or opted-out environments.

**Why this priority**: This is the foundational capability. Without local persistence, all other stories (export, backup inclusion, support) have no data to work with. This directly addresses the core problem: telemetry data is currently discarded for opted-out and air-gapped customers.

**Independent Test**: Can be fully tested by configuring telemetry opt-out, waiting for the daily collection cycle (or triggering it manually), and verifying that a telemetry snapshot record exists in the system. Delivers the core value of data retention.

**Acceptance Scenarios**:

1. **Given** an Infrahub instance with telemetry opt-out enabled, **When** the daily telemetry collection runs, **Then** a usage snapshot is stored locally in the database with the full telemetry payload.
2. **Given** an Infrahub instance with telemetry opt-out disabled, **When** the daily telemetry collection runs, **Then** a usage snapshot is stored locally AND sent to the remote telemetry endpoint.
3. **Given** an air-gapped Infrahub instance with no external network access, **When** the daily telemetry collection runs, **Then** a usage snapshot is stored locally and the system does not error due to unreachable remote endpoints.
4. **Given** a telemetry snapshot has been stored, **When** queried, **Then** it contains: deployment identifier, product version, feature usage counts, database statistics, worker status, schema information, and a collection timestamp.

---

### User Story 2 - Manual Telemetry Export via CLI (Priority: P2)

As a customer administrator or OpsMill support engineer, I can export stored telemetry snapshots to a file using a CLI command. This allows air-gapped customers to share usage data with OpsMill for support, auditing, or license compliance without requiring network connectivity.

**Why this priority**: This is the primary mechanism for getting telemetry data out of air-gapped environments. It enables the "right to audit" clause in the MSA and supports customer success workflows.

**Independent Test**: Can be fully tested by running the CLI export command against an instance with stored telemetry snapshots and verifying the output file contains the expected data in a portable format.

**Acceptance Scenarios**:

1. **Given** an Infrahub instance with stored telemetry snapshots, **When** the administrator runs the telemetry export command, **Then** a file is produced containing all snapshots within the requested date range.
2. **Given** an Infrahub instance with 2 years of telemetry data, **When** the administrator runs the export command with a date range filter (e.g., last 90 days), **Then** only snapshots within that range are included in the export.
3. **Given** an Infrahub instance with no stored telemetry data, **When** the administrator runs the export command, **Then** the system clearly indicates that no data is available.

---

### User Story 3 - Telemetry Included in Database Backups (Priority: P3)

As an infrastructure operator, when I perform a database backup, the stored telemetry snapshots are automatically included without any additional configuration or steps. This ensures telemetry data survives disaster recovery scenarios and can be requested during audits.

**Why this priority**: Backup inclusion should be a natural consequence of storing data in the database. It ensures long-term data durability and simplifies operational procedures.

**Independent Test**: Can be fully tested by performing a database backup, restoring it to a fresh instance, and verifying that telemetry snapshots are present in the restored system.

**Acceptance Scenarios**:

1. **Given** an Infrahub instance with stored telemetry snapshots, **When** a standard database backup is performed and restored, **Then** all telemetry snapshots are present in the restored instance.

---

### Edge Cases

- What happens when the database is unavailable during the daily telemetry collection? The system should log a warning and retry on the next cycle; the remote send (if enabled) should not be blocked by a local storage failure.
- What happens when telemetry collection fails midway through data gathering (e.g., a subsystem is down)? The system should store whatever partial data was successfully gathered, noting incomplete sections.
- What happens when two telemetry collection cycles overlap (e.g., if the previous one was delayed)? The system should handle concurrent writes gracefully, storing both snapshots independently.
- What happens when the exported file is very large (e.g., 5 years of daily snapshots)? The export should complete successfully; the file size (~10-25 MB for 5 years) is manageable for any system.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST collect and store a daily telemetry snapshot locally, regardless of the telemetry opt-out setting.
- **FR-002**: System MUST continue to send telemetry to the remote endpoint when telemetry opt-out is NOT enabled (preserving existing behavior).
- **FR-003**: Each stored telemetry snapshot MUST contain: deployment identifier, product version, product type (community/enterprise), feature usage counts, database statistics, worker/branch counts, schema metadata, collection timestamp, and a data integrity checksum.
- **FR-004**: Each stored snapshot MUST record whether it was successfully sent to the remote telemetry endpoint.
- **FR-005**: System MUST provide a CLI command to export stored telemetry snapshots as a JSON file (single file containing an array of snapshot objects), with optional date-range filtering.
- **FR-006**: System MUST provide a CLI command to list stored telemetry snapshots with summary information.
- **FR-007**: Stored telemetry data MUST be automatically included in standard database backups without additional configuration.
- **FR-008**: System MUST be compatible with container orchestration environments (no dependency on persistent local directories for telemetry storage).
- **FR-009**: System MUST provide a programmatic interface for retrieving stored telemetry data, enabling integration with future tech support bundle tools.
- **FR-010**: Access to telemetry export and retrieval MUST require a "telemetry:read" permission, assignable to any role through the existing permission system.

### Key Entities

- **Telemetry Snapshot**: A single daily usage data capture. Key attributes: unique identifier, collection timestamp, telemetry kind identifier, format version, deployment identifier, product version, full usage data payload, data integrity checksum, and remote-send status.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of Infrahub deployments (including air-gapped and opted-out) retain daily usage snapshots after this feature is deployed.
- **SC-002**: OpsMill support engineers can obtain telemetry data from any customer within one business day of request (via CLI export for air-gapped, via remote telemetry for connected).
- **SC-003**: Telemetry data survives disaster recovery: after a standard backup and restore, 100% of stored snapshots are recoverable.
- **SC-004**: The daily telemetry collection and storage process completes within 60 seconds and does not degrade system performance.
- **SC-005**: Administrators can export up to 5 years of telemetry data in a single CLI command, completing within 2 minutes.
- **SC-006**: Storage overhead for telemetry data remains under 50 MB for 5 years of daily snapshots.

## Clarifications

### Session 2026-02-16

- Q: Should this feature include automatic data retention cleanup (auto-delete old snapshots)? → A: Deferred — retention cleanup is excluded from this feature and will be tracked as a separate future enhancement.
- Q: What authentication model should govern access to telemetry data? → A: Permission-based — introduce a specific "telemetry:read" permission assignable to any role.
- Q: What file format should the CLI export produce? → A: JSON — a single file containing an array of snapshot objects.

## Assumptions

- The daily telemetry payload is small (~3-5 KB per snapshot), making long-term storage feasible within the existing database without significant overhead.
- The existing database backup infrastructure captures all persistent data; no separate backup mechanism is needed for telemetry.
- Air-gapped customers can transfer exported files to OpsMill via secure out-of-band channels (USB, secure file transfer, etc.).
- The telemetry opt-out setting controls only remote transmission; local storage is not affected by opt-out (this is a deliberate policy change).
- Access to telemetry data (CLI export and programmatic interface) requires a "telemetry:read" permission, assignable to any role via the existing permission system.

## Out of Scope

- Automatic data retention cleanup (auto-deleting snapshots older than a threshold). To be addressed as a separate future enhancement.
- Telemetry status dashboard or listing CLI commands (operational convenience, not core data retention).

## Dependencies

- Existing daily telemetry collection workflow (currently discards data when opted out; must be modified to always store locally).
- Existing database backup tooling (must naturally include new stored data without modification).
- Existing CLI framework (new commands must follow established patterns). Use infrahubctl.
