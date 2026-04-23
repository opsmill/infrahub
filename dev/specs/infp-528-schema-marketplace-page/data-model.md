# Phase 1 Data Model — Schema Marketplace Integration

**Feature**: infp-528-schema-marketplace-page
**Date**: 2026-04-23

This document defines the Pydantic models (backend), TypeScript types (frontend), and state transitions for the Schema Marketplace feature. Field names match the live Marketplace upstream (snake_case). Infrahub-side additions use Infrahub's standard conventions.

No new Infrahub schema **nodes** are introduced. Feature data flows through: (1) the Marketplace upstream, (2) Pydantic models owned by `infrahub_sdk.marketplace` (shared between SDK CLI and Infrahub backend), (3) generated TS types, (4) transient Prefect workflow state, and (5) Git commits on an existing `CoreRepository` node.

**Important**: The Marketplace Pydantic models listed in §1.1–§1.11 are **owned by the SDK** (`infrahub_sdk.marketplace` module, surfaced by PR #952 and a small follow-up refactor to expose them publicly). The Infrahub backend imports them:

```python
from infrahub_sdk.marketplace import (
    MarketplaceSchemaSummary,
    MarketplaceSchemaDetail,
    MarketplaceCollectionSummary,
    MarketplaceCollectionDetail,
    MarketplaceVersionContent,
    MarketplaceSchemasListResponse,
    MarketplaceCollectionsListResponse,
    MarketplaceTagCount,
    MarketplaceClient,
)
```

Infrahub-internal models (`MarketplaceInstallRequest`, `MarketplaceInstallResponse`, `MarketplaceInstallItem`, `MarketplaceInstallPayload` in §1.12–§1.13) remain in `backend/infrahub/marketplace/` because they describe the Infrahub install contract, not the upstream Marketplace.

---

## 1. Shared Marketplace models (from `infrahub_sdk.marketplace`)

All models are `pydantic.BaseModel` with `model_config = ConfigDict(frozen=True)` unless noted. Field names and types match the live Marketplace upstream; the SDK owns these as the single source of truth.

### 1.1 `MarketplaceTag`
| Field | Type | Notes |
|-------|------|-------|
| `id` | `str` | UUID from upstream |
| `name` | `str` | Lowercased tag slug |

### 1.2 `MarketplaceTagCount`
| Field | Type | Notes |
|-------|------|-------|
| `id` | `str` | |
| `name` | `str` | |
| `count` | `int` | Number of schemas carrying this tag |

### 1.3 `MarketplaceAuthor`
| Field | Type | Notes |
|-------|------|-------|
| `id` | `str` | |
| `username` | `str` | |
| `avatar_url` | `str \| None` | May be null |

### 1.4 `MarketplaceVersionSummary`
| Field | Type | Notes |
|-------|------|-------|
| `id` | `str` | Version UUID |
| `semver` | `str` | e.g., `"1.0.0"` |
| `status` | `Literal["published", "draft", "deprecated"]` | Upstream enum |
| `changelog` | `str \| None` | |
| `download_count` | `int` | |
| `download_url` | `str` | Relative path: `/api/v1/schemas/...` |
| `created_at` | `datetime` | UTC |

### 1.5 `MarketplaceSchemaSummary` (list item)
| Field | Type | Notes |
|-------|------|-------|
| `id` | `str` | |
| `namespace` | `str` | e.g., `"infrahub"` |
| `name` | `str` | e.g., `"vlan-translation"` |
| `display_name` | `str \| None` | |
| `description` | `str \| None` | |
| `visibility` | `Literal["public", "private"]` | |
| `download_count` | `int` | |
| `upvote_count` | `int` | |
| `fork_count` | `int` | |
| `viewer_has_upvoted` | `bool` | Always `false` for anonymous proxy |
| `created_at` | `datetime` | |
| `updated_at` | `datetime` | |
| `author` | `MarketplaceAuthor` | |
| `tags` | `list[MarketplaceTag]` | |
| `latest_version` | `MarketplaceVersionSummary \| None` | Null only for drafts |

### 1.6 `MarketplaceSchemaDetail` (detail endpoint)
Extends `MarketplaceSchemaSummary` with:
| Field | Type | Notes |
|-------|------|-------|
| `versions` | `list[MarketplaceVersionSummary]` | All published versions, newest first |
| `readme` | `str \| None` | Markdown |

### 1.7 `MarketplaceVersionContent`
| Field | Type | Notes |
|-------|------|-------|
| `version_id` | `str` | |
| `semver` | `str` | |
| `content` | `str` | Raw YAML body of the schema |
| `content_type` | `Literal["schema"]` | Extensible for collections |
| `sha256` | `str` | Integrity hash, if upstream provides |

### 1.8 `MarketplaceCollectionItem`
| Field | Type | Notes |
|-------|------|-------|
| `namespace` | `str` | Member schema ref |
| `name` | `str` | |
| `semver` | `str` | Pinned version |
| `order` | `int` | Install order within the collection |

### 1.9 `MarketplaceCollectionSummary`
| Field | Type | Notes |
|-------|------|-------|
| `id` | `str` | |
| `namespace` | `str` | |
| `name` | `str` | |
| `display_name` | `str \| None` | |
| `description` | `str \| None` | |
| `schema_count` | `int` | |
| `download_count` | `int` | |
| `author` | `MarketplaceAuthor` | |
| `tags` | `list[MarketplaceTag]` | |

### 1.10 `MarketplaceCollectionDetail`
Extends `MarketplaceCollectionSummary` with:
| Field | Type | Notes |
|-------|------|-------|
| `items` | `list[MarketplaceCollectionItem]` | Ordered member schemas |
| `readme` | `str \| None` | |

### 1.11 `PageInfo` + list responses
```python
class PageInfo(BaseModel):
    has_next_page: bool
    end_cursor: str | None

class MarketplaceSchemasListResponse(BaseModel):
    items: list[MarketplaceSchemaSummary]
    page_info: PageInfo
    total_count: int

class MarketplaceCollectionsListResponse(BaseModel):
    items: list[MarketplaceCollectionSummary]
    page_info: PageInfo
    total_count: int
```

---

## 1b. Infrahub-side install models (`backend/infrahub/marketplace/`)

These describe the Infrahub install contract and workflow payload. They live in Infrahub (not the SDK) because they reference Infrahub-only concepts (`repository_id`, `branch_name`, Prefect `task_id`).

### 1.12 Install request + response (Infrahub-side)
```python
class MarketplaceInstallItem(BaseModel):
    model_config = ConfigDict(frozen=True)
    kind: Literal["schema", "collection"]
    namespace: str
    name: str
    semver: str                         # pinned; e.g., "1.0.0"

class MarketplaceInstallRequest(BaseModel):
    model_config = ConfigDict(frozen=True)
    repository_id: str                  # CoreRepository.id (MUST be writable kind)
    branch_name: str                    # target branch on the repo
    items: list[MarketplaceInstallItem] # one or more schemas / collections

class MarketplaceInstallResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    task_id: str                        # Prefect flow run id, poll via task GraphQL
    message: str                        # human-readable status hint
```

### 1.13 Workflow parameter model (`backend/infrahub/marketplace/install_payload.py`)
```python
class MarketplaceInstallPayload(BaseModel):
    model_config = ConfigDict(frozen=True)
    marketplace_url: str                # snapshot of config.SETTINGS.marketplace.url
    initiator_username: str             # for commit authorship
    initiator_user_id: str
    repository_id: str
    branch_name: str
    items: list[MarketplaceInstallItem]
```
Pydantic-serializable so Prefect can persist the flow-run parameters.

**Validation rules**:

- `MarketplaceInstallRequest.repository_id` MUST resolve to a node whose kind is `CoreRepository` (not `CoreReadOnlyRepository`). Server-side enforcement (FR-027).
- `MarketplaceInstallRequest.items` MUST be non-empty and total length ≤ 50 (guardrail).
- `MarketplaceInstallItem.semver` MUST match semver regex (upstream validates; we add a `@field_validator`).
- `MarketplaceInstallRequest.branch_name` MUST exist on the target repository (resolved at task start).

---

## 2. Generated TypeScript types (frontend)

Types are generated from the backend Pydantic models via `pnpm codegen` (writes to `frontend/app/src/shared/api/rest/types.generated.ts`). No hand-edited mirrors.

New hand-written types in `frontend/app/src/entities/schema-marketplace/types.ts`:

```ts
import type { components } from "@/shared/api/rest/types.generated";

export type MarketplaceSchemaSummary = components["schemas"]["MarketplaceSchemaSummary"];
export type MarketplaceSchemaDetail  = components["schemas"]["MarketplaceSchemaDetail"];
export type MarketplaceCollectionSummary = components["schemas"]["MarketplaceCollectionSummary"];
export type MarketplaceCollectionDetail  = components["schemas"]["MarketplaceCollectionDetail"];
export type MarketplaceInstallItem    = components["schemas"]["MarketplaceInstallItem"];
export type MarketplaceInstallRequest = components["schemas"]["MarketplaceInstallRequest"];
export type MarketplaceInstallResponse = components["schemas"]["MarketplaceInstallResponse"];

// UI-only view model for the install drawer state machine
export type InstallDrawerState =
  | { phase: "idle" }
  | { phase: "selecting"; selection: MarketplaceInstallItem[] }
  | { phase: "submitting" }
  | { phase: "pending"; taskId: string }
  | { phase: "running"; taskId: string }
  | { phase: "completed"; taskId: string }
  | { phase: "failed"; taskId: string; error: string };

// CLI alternative rendering
export type CliAlternative = {
  downloads: Array<{ namespace: string; name: string; semver: string; url: string; filename: string }>;
  loadCommand: string; // "infrahubctl schema load ... --branch ..."
};
```

---

## 3. State transitions

### 3.1 Install workflow (Prefect flow run)

```text
 ┌──────────┐   client-side submit        ┌──────────┐   fetch+commit ok     ┌───────────┐
 │  IDLE    │ ─────────────────────────► │ PENDING  │ ────────────────────► │ COMPLETED │
 └──────────┘                             └────┬─────┘                       └───────────┘
                                               │ start                                 ▲
                                               ▼                                       │
                                          ┌──────────┐    any step fails   ┌──────────┐│
                                          │ RUNNING  │ ─────────────────► │  FAILED  ├┘ (repo unchanged)
                                          └──────────┘                     └──────────┘
```

States are Prefect's canonical states (`PENDING`, `RUNNING`, `COMPLETED`, `FAILED`). Task phases within `RUNNING` (fetching → committing → pushing) are internal; MVP does not surface them separately (see plan.md scope risk #3).

Rollback invariant (FR-020, SC-005): failure at any point before `git push` completes MUST leave the target repository untouched remotely. Locally, the worktree is ephemeral (cleaned up by the task).

### 3.2 Tile CTA state

Derived, not persisted:
- If `use-has-user-schemas()` returns `false` → tile renders in **onboarding CTA** state ("Get started — install your first schema").
- Otherwise → tile renders in **default** state ("Browse the Schema Marketplace").

### 3.3 Marketplace page prerequisite state

Derived, not persisted:
- `writableRepos.length === 0 && allRepos.length === 0` → **no-repos** prerequisite state (link to repo creation + CLI alternative).
- `writableRepos.length === 0 && allRepos.length > 0` → **read-only-only** prerequisite state (distinct copy + CLI alternative).
- `writableRepos.length > 0` → **install-enabled** state.

---

## 4. Related Infrahub node kinds (existing, not modified)

- `CoreRepository` — writable Git repository; valid install target.
- `CoreReadOnlyRepository` — read-only; NEVER a valid install target (FR-025).
- `CoreGenericRepository` — generic parent; used only as a base protocol.
- `CoreCredential` — holds Git authentication used by `InfrahubRepository` to clone/push.
- `Account` — the initiating user, referenced in commit author metadata and the workflow audit entry.

None of these receive new fields.

---

## 5. Branch-safety notes (Principle II)

- The proxy `GET` endpoints are branch-agnostic (Marketplace upstream has no notion of Infrahub branches).
- The install endpoint accepts a `branch_name` that is resolved server-side against the target repository; the Prefect task performs all Git operations on that branch.
- The resulting commit is then consumed by Infrahub's existing branch-aware repo-sync pipeline; no cross-branch side effects are introduced by this feature.
- The marketplace tile's "no user schemas" check is branch-scoped (checks the active branch's user-defined schemas), so a schema applied on one branch does not suppress the onboarding CTA on another.

---

## 6. Audit trail (FR-022)

Every `POST /api/marketplace/install` records an entry (persisted as a Prefect flow-run artifact + the resulting Git commit metadata):
- `initiator_user_id`, `initiator_username`
- `repository_id`, `branch_name`
- `items` (full install payload)
- `started_at`, `completed_at` or `failed_at`
- `outcome` (`completed` / `failed`) and `error` message if any
- `commit_sha` when successful

Retrieval: standard Infrahub task-history query plus the target repo's Git log.
