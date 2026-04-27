# Research: Branch Freeze (MERGED Status)

**Feature**: IFC-2184 | **Date**: 2026-04-24

## Decision Log

### D-001: Where to enforce the read-only constraint

**Decision**: Enforce at the GraphQL middleware layer as the primary gate, with secondary per-mutation guards for REST-path operations.

**Rationale**: The existing `NEED_REBASE` middleware already intercepts mutations by checking the branch context on every incoming request. Extending this pattern costs almost no new infrastructure and guarantees consistent enforcement regardless of which mutation is called. Per-mutation guards (BranchMerge, ProposedChangeCreate) are added as defense-in-depth for paths that need richer error messages or that are not covered by the middleware (e.g., REST endpoints).

**Alternatives considered**:
- A new FastAPI dependency/middleware: Rejected — duplicates the GraphQL middleware and would require two separate enforcement points.
- Only per-mutation guards: Rejected — too easy to miss new mutations added in the future; middleware provides a catch-all.

---

### D-002: BranchStatusChecker as a unified class

**Decision**: Create `backend/infrahub/branch/status_checker.py` with a `BranchStatusChecker` class containing `check_merge_status()`, `check_needs_rebase_status()`, and `check()` (both).

**Rationale**: Both `NEED_REBASE` and `MERGED` blocking logic needed to coexist in the middleware and in REST endpoint guards. A single class with named methods makes it explicit which checks are applied where, and avoids scattering the logic across multiple standalone functions. The `check()` composite method handles the common case (block all problematic states) while individual methods support selective enforcement (e.g., middleware allows certain mutations for NEED_REBASE but not MERGED).

**Alternatives considered**:
- Two standalone module-level functions (`check_merged_status`, `check_needs_rebase_status`): Rejected — no grouping or reuse benefit; callers must import two symbols.
- Checking status inline at each call site: Rejected — duplication and inconsistency risk.

---

### D-003: Branch delete allowance mechanism

**Decision**: Allow `BranchDelete` on MERGED branches via the `ALLOWED_MUTATIONS_ON_MERGED_BRANCH` middleware allowlist, not via a permission system exception.

**Rationale**: The middleware is the primary enforcement point. Adding an allowlist entry (same pattern as `ALLOWED_MUTATIONS_ON_NEED_REBASE_BRANCH`) is the lowest-friction solution that keeps the delete path consistent with how other allowed-on-restricted-branch mutations are handled. The permission system returning DENY for branch delete on MERGED would confuse the frontend and block a legitimate operation.

**Alternatives considered**:
- Permission system carve-out for `InfrahubKind.BRANCH` delete on MERGED: Rejected — adds complexity to the permission report and requires the frontend to reason about a permission exception on top of a status exception.

---

### D-004: When to set MERGED status in the merge flow

**Decision**: Set `BranchStatus.MERGED` as the absolute last step of `merge_branch()`, after all other merge operations succeed.

**Rationale**: The merge flow (`backend/infrahub/core/branch/tasks.py`) performs several operations: locking, conflict validation, graph merge, repository merge, schema updates, migrations, diff tracking. Any failure before the status update leaves the branch in `OPEN` so it can be retried or corrected. Setting MERGED early would silently lock a branch that is in an inconsistent intermediate state.

**Alternatives considered**:
- Set MERGED after `merge_graph()`: Rejected — repository merge and schema migrations could still fail, leaving a locked but incompletely merged branch.
- Wrap entire merge in a transaction that sets MERGED atomically: Rejected — the merge flow is not a single DB transaction and involves cross-service operations (git, Prefect workflows).

---

### D-005: Handling open proposed changes at merge time

**Decision**: Reuse the existing `cancel_proposed_changes_branch()` workflow, already triggered on branch delete, by also calling it at the end of `merge_branch()`.

**Rationale**: The workflow already exists and handles the cancellation logic correctly. Reusing it avoids duplication and ensures consistent PC cancellation behavior whether a branch is deleted or merged.

**Alternatives considered**:
- Inline PC cancellation in merge_branch(): Rejected — duplicates existing workflow logic.
- Lazy cancellation (cancel when user tries to merge a PC after its source is MERGED): Rejected — leaves open PCs in a stale state that can confuse users.

---

### D-006: Backfill migration for pre-existing merged branches

**Decision**: No migration. Branches merged before this feature ships remain in `OPEN` status.

**Rationale**: There is no reliable way to determine which `OPEN` branches were already merged (no audit trail in the graph). A migration that sets all non-default `OPEN` branches to `MERGED` would be too aggressive and could lock branches that users intend to keep active. Users can manually delete such branches if cleanup is desired.

**Alternatives considered**:
- Set all non-default OPEN branches to MERGED: Rejected — too broad; would lock branches that are genuinely open.
- Derive merged status from diff tracking records: Considered — not reliably determined from existing data; not worth the risk.

---

### D-007: Git repository sync conflict

**Decision**: Accept as a known limitation. If git syncs new commits to an already-MERGED Infrahub branch, the sync fails gracefully without affecting other branches.

**Rationale**: Infrahub's graph merge and git merge are not a single atomic transaction. There is no good mechanism to surface a git-merge failure as an Infrahub error that would prevent setting the MERGED status. This gap exists in the current architecture and is not specific to this feature.

**Future work**: When a better error propagation mechanism exists between git and the Infrahub graph, the MERGED status set should be conditional on the git merge outcome.
