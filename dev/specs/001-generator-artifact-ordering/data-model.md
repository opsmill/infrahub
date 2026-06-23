# Data Model: Generator-Before-Artifact Ordering

## Overview

This change does **not** modify any database schemas, node definitions, or relationship structures. The fix is purely in the workflow orchestration layer — changing how existing workflows are dispatched.

## Entities Involved (Read-Only Context)

These entities are relevant to understanding the flow but are not modified by this change.

### CoreGeneratorDefinition

**Schema**: `backend/infrahub/core/schema/definitions/core/generator.py:15`
**Branch support**: AWARE

| Attribute | Type | Relevance |
|-----------|------|-----------|
| `name` | Text (unique) | Used to name the validator |
| `execute_in_proposed_change` | Boolean | Controls whether generator runs in proposed change pipeline |
| `execute_after_merge` | Boolean | Controls post-merge execution (not affected) |
| `query` | Relationship → GraphQLQuery | Determines which data models the generator touches |
| `targets` | Relationship → Group | Determines which objects the generator runs against |
| `repository` | Relationship → GenericRepository | Source of generator code |

### CoreGeneratorInstance

**Schema**: `backend/infrahub/core/schema/definitions/core/generator.py:86`
**Branch support**: LOCAL

| Attribute | Type | Relevance |
|-----------|------|-----------|
| `status` | Enum (Pending, Processing, Ready, Error) | Tracks individual generator execution state |
| `object` | Relationship → Node | The target object being generated for |
| `definition` | Relationship → GeneratorDefinition | Parent definition |

### CoreArtifactDefinition

**Schema**: `backend/infrahub/core/schema/definitions/core/artifact.py:99`

Artifacts are generated after generators complete. Their definitions determine which data to query and which transforms to apply.

### CoreArtifact

**Schema**: `backend/infrahub/core/schema/definitions/core/artifact.py:37`

Individual artifact instances. Their `status` transitions through Pending → Processing → Ready/Error during generation.

## Workflow Message Models (Updated)

### RequestProposedChangeRunGenerators

**File**: `backend/infrahub/proposed_change/models.py:27`

```
proposed_change: str
source_branch: str
source_branch_sync_with_git: bool
destination_branch: str
branch_diff: ProposedChangeBranchDiff
```

The `refresh_artifacts` and `do_repository_checks` fields have been **removed** from this model. Downstream dispatch of artifact refresh and repository checks is now handled directly by `run_proposed_change_pipeline()` after generators complete, rather than being controlled by flags passed to `run_generators()`.

### RequestGeneratorDefinitionCheck

**File**: `backend/infrahub/proposed_change/models.py:81`

No changes. This model is passed to `execute_workflow` instead of `submit_workflow`.

## State Transitions (Unchanged)

```
Pipeline Start (CheckType.ALL)
  ├─ Phase 2: Independent checks (fire-and-forget, concurrent with generators)
  │    └─ User Tests
  │    (Note: for CheckType.ALL, Data Integrity and Schema Integrity are NOT dispatched here;
  │     they run only in Phase 4 on the post-generator diff)
  │
  ├─ Phase 3: run_generators() — BLOCKING
  │    └─ Generator Definition Checks (parallel, awaited via asyncio.gather)
  │         └─ Per-instance: PENDING → READY/ERROR
  │              └─ GeneratorValidator: QUEUED → IN_PROGRESS → COMPLETED
  │
  ├─ Phase 3.5: Diff Recomputation  ← NEW BEHAVIOR
  │    └─ DiffCoordinator.update_branch_diff() — reflects generator-created objects
  │
  └─ Phase 4: Generator-dependent checks (fire-and-forget, post-generator diff)  ← NEW BEHAVIOR
       ├─ Artifact Refresh
       │    └─ Per-artifact: PENDING → READY/ERROR
       │         └─ ArtifactValidator: QUEUED → IN_PROGRESS → COMPLETED
       ├─ Repository Checks
       ├─ Data Integrity Check (post-generator diff — includes generator-created objects)
       └─ Schema Integrity Check (post-generator diff)
```

For `CheckType.DATA` or `CheckType.SCHEMA` (standalone, no generators), the respective check runs in Phase 2 only and generators are never invoked.

The state machine for individual generators and artifacts is unchanged. The orchestration now dispatches data/schema integrity checks ONLY in Phase 4 for `CheckType.ALL`, so they always observe objects created by generators.
