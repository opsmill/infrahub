# infp-528 — as-shipped delta vs the original spec

The original `spec.md`, `plan.md`, `data-model.md`, and `contracts/` describe
the feature at `/speckit.plan` time. This file captures what actually shipped
in the commits leading up to merge. Use `delta.md` as the authoritative source
when the two disagree; when the feature stabilizes, fold these into the spec
itself.

## Added: direct install target

The spec describes a single install path (commit to a writable Git
repository). The shipped feature exposes **two** paths:

- `target="repository"` (default) — unchanged from the spec.
- `target="direct"` — fetches the schema YAML from the Marketplace and applies
  it via the schema-load API (`POST /api/schema/load`) against the target
  Infrahub branch. No Git repo required.

### Surface area

- `MarketplaceInstallRequest` gains a `target: Literal["repository", "direct"]`
  field, defaulting to `"repository"` for back-compat.
- `repository_id` is now optional; the model-level validator requires it only
  when `target == "repository"`.
- New Prefect flow `marketplace-schema-install-direct` (registered in
  `backend/infrahub/workflows/catalogue.py` as
  `MARKETPLACE_SCHEMA_INSTALL_DIRECT`).
- Frontend install drawer grows an "Install method" toggle (`To repository` /
  `Direct`) with per-mode helper copy.

### FR deltas

- FR-017: now reads "trigger an install by selecting a Marketplace item **and,
  for the repository path, a target Git repository**."
- FR-020 rollback invariant applies to both paths. For `direct`, the
  `schema-load` endpoint is itself transactional per request — either the
  whole batch applies or none of it does.

## Added: sync_with_git gate on the repository target

The spec treats the writable-Git-repo prerequisite as binary. The shipped UI
additionally gates the repository target on the **Infrahub branch** having
`sync_with_git=true`:

- Repository installs assume the target Git branch maps back to an Infrahub
  branch. That's only clean when the Infrahub branch was created with Git
  sync enabled. Otherwise the install would create a Git branch that no
  Infrahub branch tracks — an orphan.
- When the current top-bar branch is not git-synced, the "To repository"
  toggle is disabled with a yellow warning; the "Direct" toggle is primary.
- On backend side, `_commit_and_push` defensively calls
  `InfrahubRepository.create_branch_in_git(push_origin=True)` before opening
  a worktree. Idempotent — no-op when the branch exists, creates from
  `default_branch` when not.

## Added: server-side permission enforcement

The original spec said "server-side re-verification of write permission"
(FR-025/FR-027). The shipped enforcement uses Infrahub's existing
`PermissionManager`:

- All install paths require `MANAGE_SCHEMA` (both flows ultimately mutate the
  schema).
- `target="repository"` additionally requires `MANAGE_REPOSITORIES` (the flow
  performs a `git push` against a `CoreRepository` node).
- Installing into `main` / the global branch additionally requires
  `EDIT_DEFAULT_BRANCH` — mirrors `/api/schema/load`'s own gate.

Helper: `_raise_for_install_permissions` in `backend/infrahub/api/marketplace.py`.
Unit tests: `backend/tests/unit/marketplace/test_api_permissions.py`.

## Dropped: `already_installed` field

The spec's `MarketplaceSchemaSummary` / `MarketplaceCollectionSummary`
included an `already_installed: bool` field (FR-009 / FR-025). Detecting
this accurately requires reading the file tree of every configured
`CoreRepository`, which would be expensive for list endpoints and brittle
when users commit schemas by hand. Rather than ship a stub that always
returns `false`, the field is dropped from both Pydantic models and TS types
until we have a performant detection mechanism.

## Dropped: home-page tile

The spec's FR-002/FR-003 called for a Schema Marketplace widget on the home
page (with a "Get started" CTA on empty instances). The tile shipped
initially but was removed before merge — the sidebar entry and the
Marketplace page are sufficient, and keeping a home-page widget meant
maintaining an additional "does this instance have any user schemas?"
signal that duplicated what the Marketplace page already expresses. The
`Getting started` card on the home page still deep-links to
`/schema-marketplace`.

## Other small deltas

- Install flow names:
  - `install_marketplace_schemas` → `marketplace-schema-install`
  - `install_marketplace_schemas_direct` → `marketplace-schema-install-direct`
- `MarketplaceInstallPayload` passed to the workflow is the full request
  serialized with `model_dump(mode="json")`.
- The UI's "Branch" field tracks the top-bar Infrahub branch by default.
  Override is available only when the install method is `direct` — the
  repository target's toggle gate already keeps the branch list pinned to
  git-synced Infrahub branches, so freeform override there would re-open
  the orphaned-Git-branch foot-gun.
- Backend config: `INFRAHUB_MARKETPLACE_URL` is on a dedicated
  `MarketplaceSettings` subsection rather than mixed into `MainSettings` —
  the env var name matches what the SDK's `infrahubctl marketplace download`
  reads, so a single export reconfigures both (see
  `opsmill/infrahub-sdk-python#952`).
- Cross-field validation for `target == "repository"` → `repository_id
  required` lives in `MarketplaceInstallRequest.model_validator` (Pydantic).
  The router also checks explicitly so the HTTP surface returns a 400, not a
  422.

## Open items tracked for follow-up

- **SDK PR #952 unmerged**: the `python_sdk` submodule is not yet bumped to
  `knotty-dibble`, so `infrahubctl marketplace download` is not a real
  command on the pinned SDK HEAD. The `/cli-snippet` endpoint emits commands
  that users cannot run until the SDK lands.
- **No progress polling** on the install drawer. It shows "Queued as task
  <id>" and leaves users to check the Tasks page. Planned follow-up.
- **Playwright and functional tests** for the full install flow are listed in
  `tasks.md` as deferred. Unit coverage now includes the permission helper
  and the Pydantic install-request validators, but the end-to-end path still
  lacks automated regression coverage.
- **`fetch_collection_bundle` has no size limit** — planned to address
  through an upstream paginated schemas API rather than a client-side cap.
