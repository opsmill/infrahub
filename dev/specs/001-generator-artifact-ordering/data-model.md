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

## Workflow Message Models (No Changes)

### RequestProposedChangeRunGenerators

**File**: `backend/infrahub/proposed_change/models.py:27`

```
proposed_change: str
source_branch: str
source_branch_sync_with_git: bool
destination_branch: str
branch_diff: ProposedChangeBranchDiff
refresh_artifacts: bool          # Controls whether to dispatch artifact refresh
do_repository_checks: bool       # Controls whether to dispatch repo checks
```

No fields are added or modified. The `refresh_artifacts` and `do_repository_checks` flags continue to control whether downstream work is dispatched — the change is only in *when* that dispatch happens (after generators complete vs. immediately).

### RequestGeneratorDefinitionCheck

**File**: `backend/infrahub/proposed_change/models.py:81`

No changes. This model is passed to `execute_workflow` instead of `submit_workflow`.

## State Transitions (Unchanged)

```
Pipeline Start
  └─ run_generators()
       ├─ Generator Definition Checks (parallel, now awaited)
       │    └─ Per-instance: PENDING → READY/ERROR
       │         └─ GeneratorValidator: QUEUED → IN_PROGRESS → COMPLETED
       │
       ├─ [WAIT: all generator validators COMPLETED]  ← NEW BEHAVIOR
       │
       ├─ Artifact Refresh (fire-and-forget)
       │    └─ Per-artifact: PENDING → READY/ERROR
       │         └─ ArtifactValidator: QUEUED → IN_PROGRESS → COMPLETED
       │
       └─ Repository Checks (fire-and-forget)
```

The state machine for individual generators and artifacts is unchanged. Only the orchestration timing between the two phases changes.
