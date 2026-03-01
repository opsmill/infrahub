# Data Model: Configuration Wizard with Marketplace Schema Browser

**Feature**: atg-01-config-wizard | **Date**: 2026-02-26

## Existing Entities (No Changes Required)

### CorePasswordCredential

Already defined in Infrahub schema. Used as-is for Git credential creation in the wizard.

| Field | Type | Constraints |
|-------|------|-------------|
| name | Text | Required, Unique |
| label | Text | Optional |
| description | Text | Optional |
| username | Text | Required |
| password | Password | Required |

### CoreRepository

Already defined in Infrahub schema. Used as-is for Git repository creation in the wizard.

| Field | Type | Constraints |
|-------|------|-------------|
| name | Text | Required, Unique |
| description | Text | Optional |
| location | Text | Required (Git URL) |
| default_branch | Text | Required, Default: "main" |
| credential | Relationship | Optional, → CoreCredential, Cardinality: ONE |
| internal_status | Dropdown | STAGING / ACTIVE / INACTIVE |
| operational_status | Dropdown | UNKNOWN / ONLINE / ERROR_* |

## New Entities

### MarketplaceSchemaResponse (Backend Pydantic Model)

Represents a schema from the marketplace API response. Read-only, not persisted.

| Field | Type | Constraints |
|-------|------|-------------|
| id | str | Required (UUID from marketplace) |
| name | str | Required |
| namespace | str | Required |
| display_name | str | Required |
| description | str | Required |
| download_count | int | Required, >= 0 |
| upvote_count | int | Required, >= 0 |
| fork_count | int | Required, >= 0 |
| visibility | str | Required (e.g., "public") |
| tags | list[MarketplaceTag] | Required |
| versions | list[MarketplaceVersionSummary] | Required |

### MarketplaceTag (Backend Pydantic Model)

| Field | Type | Constraints |
|-------|------|-------------|
| id | str | Required |
| name | str | Required |

### MarketplaceVersionSummary (Backend Pydantic Model)

| Field | Type | Constraints |
|-------|------|-------------|
| id | str | Required |
| semver | str | Required |
| status | str | Required |
| download_count | int | Required, >= 0 |

### MarketplaceVersionContent (Backend Pydantic Model)

Represents the full content of a specific schema version, used for installation.

| Field | Type | Constraints |
|-------|------|-------------|
| id | str | Required |
| semver | str | Required |
| content | str | Required (YAML/JSON schema definition) |
| download_url | str | Required |
| dependencies | list[MarketplaceDependency] | Required |

### MarketplaceDependency (Backend Pydantic Model)

| Field | Type | Constraints |
|-------|------|-------------|
| id | str | Required |
| name | str | Required |
| namespace | str | Required |

### MarketplaceCollectionResponse (Backend Pydantic Model)

| Field | Type | Constraints |
|-------|------|-------------|
| id | str | Required |
| name | str | Required |
| display_name | str | Optional |
| description | str | Required |
| schema_count | int | Required, >= 0 |
| download_count | int | Required, >= 0 |
| upvote_count | int | Required, >= 0 |
| items | list[MarketplaceCollectionItem] | Required |

### MarketplaceCollectionItem (Backend Pydantic Model)

| Field | Type | Constraints |
|-------|------|-------------|
| id | str | Required |
| name | str | Required |
| display_name | str | Optional |

### MarketplaceInstallRequest (Backend Pydantic Model)

Request payload for triggering schema installation.

| Field | Type | Constraints |
|-------|------|-------------|
| repository_id | str | Required (Infrahub repository UUID) |
| schema_version_ids | list[str] | Required, non-empty (marketplace version UUIDs) |
| branch_name | str | Required |

### MarketplaceInstallModel (Workflow Model)

Parameters passed to the Prefect workflow.

| Field | Type | Constraints |
|-------|------|-------------|
| repository_id | str | Required |
| schema_version_ids | list[str] | Required |
| branch_name | str | Required |
| marketplace_url | str | Required, default: "https://marketplace.infrahub.app" |

## Entity Relationships

```text
CorePasswordCredential ──(credential)──► CoreRepository
                                             │
                                             ▼
MarketplaceInstallRequest ──(repository_id)──┘
        │
        ▼
MarketplaceVersionContent ──(dependencies)──► MarketplaceDependency
        │
        ▼
   Schema files written to CoreRepository
```

## State Transitions

### Wizard Flow State

```text
NO_SCHEMAS_DETECTED → WELCOME → CREDENTIALS → REPOSITORY → SCHEMA_BROWSE → CONFIRM → INSTALLING → COMPLETE
                        │                                       │                         │
                        ▼                                       ▼                         ▼
                      SKIPPED                              BACK (any step)            FAILED → RETRY
```

### Installation Job State

```text
SUBMITTED → DOWNLOADING → WRITING_FILES → COMMITTING → PUSHING → IMPORTING → COMPLETED
                │              │              │            │          │
                ▼              ▼              ▼            ▼          ▼
             FAILED         FAILED         FAILED       FAILED    FAILED
```

## TypeScript Types (Frontend)

```typescript
interface MarketplaceSchema {
  id: string;
  name: string;
  namespace: string;
  displayName: string;
  description: string;
  downloadCount: number;
  upvoteCount: number;
  forkCount: number;
  visibility: string;
  tags: Array<{ id: string; name: string }>;
  versions: Array<{ id: string; semver: string; status: string }>;
}

interface MarketplaceCollection {
  id: string;
  name: string;
  displayName: string | null;
  description: string;
  schemaCount: number;
  downloadCount: number;
  upvoteCount: number;
  items: Array<{ id: string; name: string; displayName: string | null }>;
}

type WizardStep = "welcome" | "credentials" | "repository" | "schemas" | "confirm";

interface WizardState {
  currentStep: WizardStep;
  credentialId: string | null;
  repositoryId: string | null;
  selectedSchemaVersionIds: string[];
}
```
