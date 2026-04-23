# Feature Specification: Schema Marketplace Integration — Dedicated Page + Backend Proxy

**Feature Branch**: `infp-528-schema-marketplace-page`
**Created**: 2026-04-23
**Status**: Draft
**Input**: Replace the existing first-run schema wizard/popup with a dedicated Schema Marketplace page inside Infrahub, add a tile on the home page that links to it (with an onboarding emphasis when no user schemas are loaded), repoint existing "schema library" links on the home page to the new Marketplace page, and route all Marketplace interactions (browse, fetch, install) through an Infrahub backend proxy so the frontend never calls `marketplace.infrahub.app` directly.

**Prior art**: the `atg-01-config-wizard` branch delivered a first pass (backend proxy scaffolding plus a modal wizard). This feature retains the backend proxy direction but replaces the modal with a dedicated page, re-validates against the current Marketplace API (which has changed), and supports post-setup installs.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Install initial schemas from a dedicated page (Priority: P1)

A new Infrahub user logs into a freshly installed instance and lands on an empty home page. Instead of being interrupted by a modal wizard, they see a tile on the home page labeled "Schema Marketplace" with an onboarding call-to-action indicating no schemas are loaded yet. They click the tile, browse the Marketplace listing, pick a schema, choose a target Git repository, and confirm installation. The backend fetches the schema files from the Marketplace and commits them to that repository on the user's behalf.

**Why this priority**: This is the primary replacement for the existing wizard. Without it, the reported "wizard reappears on every refresh" bug persists and new users cannot load schemas at all.

**Independent Test**: Start from a blank Infrahub instance. Confirm no modal appears. Confirm the Schema Marketplace tile appears on the home page with an onboarding call-to-action. Click the tile to navigate to the Schema Marketplace page, install one schema, and verify the chosen Git repository now contains a commit with the expected schema files.

**Acceptance Scenarios**:

1. **Given** a freshly installed Infrahub instance with no user-defined schemas, **When** the user visits the home page, **Then** they see a Schema Marketplace tile with an onboarding call-to-action and no modal or popup blocks the view.
4. **Given** any existing "schema library" or equivalent home-page link from prior releases, **When** the user clicks it, **Then** they land on the new Schema Marketplace page (no stale destinations remain).
2. **Given** the user is on the Schema Marketplace page and selects a schema plus a configured Git repository, **When** they confirm installation, **Then** the backend fetches the schema from the Marketplace and commits it to that repository, and the UI reports success with a link to the commit.
3. **Given** the user refreshes the browser or navigates away and back, **When** they return to any page, **Then** no modal or wizard reappears.

---

### User Story 2 - Install additional schemas after initial setup (Priority: P1)

An operator running an established Infrahub instance wants to extend it with another schema from the Marketplace (for example, adding DCIM on top of an existing IPAM deployment). They open the Schema Marketplace page from the main navigation, browse, select, and install — without any setup/first-run gating.

**Why this priority**: Equally critical: the old wizard was a one-shot flow and blocked this entire use case. Production environments require adding schemas over time.

**Independent Test**: Starting from an instance with at least one schema already loaded, open the Schema Marketplace page, install a different schema, and verify the new commit lands without disturbing existing schemas or data.

**Acceptance Scenarios**:

1. **Given** an instance with one or more schemas already loaded, **When** the user navigates to the Schema Marketplace page, **Then** the page is reachable directly with no "first-time setup" gate.
2. **Given** the user installs a new schema into an existing repository, **When** the install completes, **Then** the new schema files are added as a single additional commit and no existing files are modified or removed.
3. **Given** a schema is already installed, **When** the user views it in the Marketplace listing, **Then** the UI marks it as installed and blocks or warns against duplicate installation.

---

### User Story 3 - Browse and compare schemas before installing (Priority: P2)

A user wants to compare several Marketplace schemas before picking one. The Schema Marketplace page lists schemas with names, descriptions, versions, and categories/tags sourced from `marketplace.infrahub.app`. Opening a detail view reveals the full description and the list of files that will be committed on install.

**Why this priority**: Improves discovery and informed selection; MVP could ship with a basic list, but the richer detail view is important for confidence.

**Independent Test**: Open the Schema Marketplace page, verify listings render with name/description/version/category, open an item's detail view, and confirm the file list matches what `marketplace.infrahub.app` publishes for that item.

**Acceptance Scenarios**:

1. **Given** the Schema Marketplace page is open, **When** Marketplace data loads, **Then** each item shows name, description, version, and one or more categories/tags.
2. **Given** the user opens a detail view for an item, **When** the detail renders, **Then** it shows the full description and the list of schema files that would be committed if installed.

---

### User Story 4 - Blocked UI install when no writable repository, with CLI alternative (Priority: P1)

A user arrives at the Schema Marketplace page on an instance where no Git repository is configured, or where only read-only repositories exist. In-UI installation is disabled with a clear explanation of why, but the page does not dead-end the user: for any selected schema(s), it presents an alternative path using the `infrahubctl` command line — copy-pasteable commands that download the selected schemas and apply them directly, without requiring a writable Git repository inside Infrahub. Once a writable repository is added, UI install controls become available.

**Why this priority**: A home-page tile that leads users to a page where they can't complete their task is worse than no tile at all. Without this story, the feature produces dead-end flows. Offering the CLI alternative preserves progress for users whose environment can't (or won't) host a writable Infrahub repo — a common case for evaluation, air-gapped experimentation, and CI-driven schema management — while still gating the UI commit path on proper prerequisites.

**Independent Test**: On an instance with no repositories, open the Schema Marketplace page, select one or more schemas, confirm UI install controls are disabled with a prerequisite message, and confirm a clearly labeled "Install via `infrahubctl`" alternative is shown with copy-pasteable commands for the selected schema(s). Run the displayed CLI command against a test Infrahub instance and verify the schema is applied. Add a read-only repository and confirm the same alternative is still presented. Add a writable repository and confirm UI install controls become enabled; the CLI alternative may remain available as a secondary option but is no longer the only path.

**Acceptance Scenarios**:

1. **Given** no Git repositories are configured, **When** the user opens the Schema Marketplace page, **Then** UI install controls are disabled, a prerequisite message explains a writable repository is required (with a link to repository creation), and an "Install via `infrahubctl`" alternative is shown.
2. **Given** only read-only repositories are configured, **When** the user opens the Schema Marketplace page, **Then** UI install controls are disabled, the message distinguishes this from the "no repos" case, and the `infrahubctl` alternative is shown.
3. **Given** the user has selected one or more schemas in the no-writable-repo state, **When** they view the CLI alternative, **Then** it displays copy-pasteable `infrahubctl` command(s) that reference the exact selected schemas and include a one-click copy action.
4. **Given** at least one writable repository is configured, **When** the user opens the Schema Marketplace page, **Then** UI install controls are enabled and only writable repositories the user has write permission to appear in the target repository selector.
5. **Given** the user has selected a writable repository, **When** they lose write permission before confirming install, **Then** the backend rejects the install with a permission error and the repository is unchanged.

---

### User Story 5 - Clear feedback on Marketplace and Git failures (Priority: P2)

When the backend cannot reach `marketplace.infrahub.app` (air-gapped environment, outage) or when committing to the target Git repository fails (permissions, network, merge conflict), the user receives a clear, actionable error instead of a spinner or a half-finished install.

**Why this priority**: Enterprise Infrahub deployments commonly run in restricted networks. Without graceful error paths, real customers will file install-hangs bugs.

**Independent Test**: Block egress to `marketplace.infrahub.app` and open the Schema Marketplace page — expect a clear error, not an infinite loader. Separately, provide an invalid or unwritable target repository and attempt install — expect a clear error and no partial commit in the repo.

**Acceptance Scenarios**:

1. **Given** the backend cannot reach the Marketplace, **When** the user opens the Schema Marketplace page, **Then** a clear connectivity error is shown within a short timeout and no indefinite spinner is displayed.
2. **Given** an installation fails mid-flight (e.g., Git push rejected), **When** the user is notified, **Then** the message identifies the failing step and the target repository is left in its pre-install state.

---

### Edge Cases

- User has no Git repository configured yet — UI install controls are disabled, the page shows a prerequisite state that links to repository creation, and the `infrahubctl` CLI alternative is offered for the selected schema(s).
- User has only read-only repositories configured — same blocked state as above: UI install controls are disabled, explanation distinguishes read-only-only from no-repos, and the CLI alternative is offered.
- User loses write access to the selected repository between selecting it and confirming install — the install attempt must fail cleanly with a permission-specific error.
- `marketplace.infrahub.app` is unreachable (air-gapped/offline) — page must surface this without hanging.
- User attempts to install the same schema twice — UI warns and blocks duplicate install.
- Two users install different schemas into the same repository concurrently — one should succeed, the other should fail cleanly with a clear retry message; no corrupted repo state.
- Marketplace publishes a newer version of an already-installed schema — update flow is out of scope for MVP; UI may surface that an update exists but does not apply it.
- Schema declares dependencies on another schema not yet installed — MVP behavior is to warn and list missing dependencies; automated dependency install is out of scope.
- User cancels an in-flight installation — backend must either finish cleanly or leave the repo unchanged; never partial.
- Target repository's default branch is not `main` or is behind remote — install must respect the configured branch and fail clearly if out of sync.

## Requirements *(mandatory)*

### Functional Requirements

**Dedicated page and navigation**

- **FR-001**: System MUST provide a Schema Marketplace page accessible from the main navigation on every page of the application.
- **FR-002**: System MUST NOT display any modal, popup, or wizard overlay on page load, regardless of whether schemas are loaded.
- **FR-003**: System MUST render a Schema Marketplace tile on the home page that links to the Schema Marketplace page and is present regardless of whether any user-defined schemas are loaded (the tile is a persistent discoverability affordance).
- **FR-004**: When no user-defined schemas are loaded, the Schema Marketplace tile MUST surface an onboarding call-to-action state (distinct visual treatment or label such as "Get started — install your first schema") to guide new users to the page.
- **FR-005**: System MUST update any existing home-page links previously labeled "Schema Library" (or equivalent from prior wizard/library work) to point to the new Schema Marketplace page; no stale destinations may remain on the home page.
- **FR-006**: Users MUST be able to open the Schema Marketplace page at any time after initial setup without any "first-time-user" gating.

**Marketplace browsing**

- **FR-007**: System MUST display Marketplace items on the Schema Marketplace page with at minimum: name, description, version, and one or more categories/tags.
- **FR-008**: Users MUST be able to open a detail view for any Marketplace item that shows the full description and the list of files that would be committed on install.
- **FR-009**: System MUST indicate, on both list and detail views, when a given Marketplace schema is already installed in one of the user's configured Git repositories.

**Backend proxy**

- **FR-010**: All Marketplace API interactions MUST route through the Infrahub backend; the frontend MUST NOT make direct calls to the Marketplace.
- **FR-011**: Backend MUST expose Infrahub-internal endpoints to list Marketplace items, retrieve item details, and initiate installs; these endpoints proxy to the configured Marketplace URL.
- **FR-012**: Backend MUST apply reasonable caching or rate-limiting to Marketplace requests to avoid overloading the Marketplace.
- **FR-013**: Backend MUST surface Marketplace connectivity and protocol errors to the frontend in a structured, user-actionable form (no opaque 500s).
- **FR-014**: The Marketplace base URL MUST be configurable at the backend via an environment variable, defaulting to `https://marketplace.infrahub.app`, so operators can point Infrahub at an internal mirror, a staging marketplace, or a test fixture without code changes.
- **FR-015**: The configured Marketplace URL MUST be validated at backend startup (well-formed URL, scheme `http`/`https`); a misconfiguration MUST surface in backend logs with a clear message, and the Schema Marketplace page MUST display a configuration-error state if the backend reports the Marketplace is not properly configured.
- **FR-016**: The Marketplace URL MUST NOT be exposed to or selectable by end users from the frontend; it is operator-only configuration.

**Install flow**

- **FR-017**: Users MUST be able to trigger a schema installation by selecting a Marketplace item and a target Git repository (and branch, if applicable).
- **FR-018**: Backend MUST fetch the selected schema's files from the Marketplace and commit them to the chosen Git repository as a single commit.
- **FR-019**: System MUST present installation progress (queued, fetching, committing, done/failed) and a final success or failure state to the user.
- **FR-020**: System MUST leave the target Git repository unchanged if any step of the installation fails before the commit lands — no partial commits, no orphaned files.
- **FR-021**: The Git commit created by an installation MUST attribute authorship to the Infrahub user who triggered it (at minimum in the commit message or commit metadata).
- **FR-022**: System MUST record an auditable entry for each install attempt (who, what, when, target repo, outcome) retrievable by an administrator.

**Prerequisites and precedence**

- **FR-023**: The Schema Marketplace page MUST detect whether at least one writable (read-write) Git repository is configured in Infrahub and expose this state to the UI.
- **FR-024**: When no writable Git repository is configured, the Schema Marketplace page MUST disable all UI install controls (install buttons, schema-select actions intended to trigger install) and render a prerequisite state that:
    - explains that a writable Git repository is required,
    - distinguishes this case from "read-only repos only exist" versus "no repos at all," and
    - links the user to the repository creation flow.
- **FR-025**: Read-only repositories MUST NOT be selectable as install targets in any picker or selector; they may be displayed with a clear "read-only — cannot install" indicator, but MUST NOT be selectable.
- **FR-026**: The repository selector on the Schema Marketplace page MUST list only repositories the current user has write permission to; repositories the user cannot write to MUST be hidden or displayed as disabled with a reason.
- **FR-027**: The backend install endpoint MUST re-verify repository writability and user write permission server-side before attempting the commit; client-side gating is not sufficient.
- **FR-028**: System MUST NOT create or modify any Git repository other than the one the user explicitly selects as the install target.
- **FR-029**: System MUST NOT auto-create a Git repository on behalf of the user; repository creation remains an explicit, separate user action.

**CLI alternative when no writable repository exists**

- **FR-030**: When the Schema Marketplace page is in the no-writable-repository state (no repos configured, or only read-only repos), it MUST present a clearly labeled alternative path that uses the `infrahubctl` command line to download and apply the user's selected schema(s) without requiring a writable Infrahub-hosted Git repository.
- **FR-031**: The CLI alternative MUST generate copy-pasteable `infrahubctl` command(s) that reference the specific schema(s) the user has selected (not a generic placeholder), and MUST include a one-click copy action for each command.
- **FR-032**: The CLI alternative MUST remain functional and accurate regardless of whether the backend currently has Marketplace connectivity — the commands themselves rely on the `infrahubctl` client's own network access to the Marketplace, not on the Infrahub backend proxy.
- **FR-033**: The CLI alternative MUST include a brief inline explanation that the commands run against the user's Infrahub instance (using their existing `infrahubctl` authentication) and do not commit to a Git repository; this distinction MUST be obvious so users understand why the CLI path bypasses the writable-repo requirement.
- **FR-034**: The CLI alternative MAY also be surfaced as a secondary action when a writable repository is available, but MUST NOT be the default path in that case — the UI install remains primary.

**Permissions**

- **FR-035**: Installing a schema MUST be gated by the same permission model Infrahub uses to manage Git repositories; a user who cannot write to a repository cannot install a schema into it.

### Key Entities

- **Marketplace Schema Item**: A schema published on the configured Marketplace (default `https://marketplace.infrahub.app`). Attributes: name, description, version, categories/tags, list of schema files, and a way to retrieve each file's content.
- **Installation Request**: A user-initiated action pairing a Marketplace Schema Item with a target Git repository and branch. Tracks status (queued, fetching, committing, success, failed) and failure reason.
- **Marketplace Proxy Endpoint (conceptual)**: Infrahub-internal surface the frontend calls to list items, get item details, and initiate installs.
- **Schema Marketplace Home Tile**: Persistent tile on the home page linking to the Schema Marketplace page; displays an onboarding call-to-action state when no user-defined schemas are loaded.
- **Schema Marketplace Page**: Dedicated in-app page that lists and lets users install Marketplace schemas; persistent navigation entry.

## Assumptions

- Replacing the wizard means the modal wizard entry point is removed entirely from page-load flows. Backend scaffolding from `atg-01-config-wizard` (Marketplace client, models, proxy endpoint) is retained where still valid and revalidated against the current Marketplace API.
- "No user-defined schemas loaded" means no user-authored schema nodes exist — only Infrahub's built-in/core schema is present.
- Installing a schema means committing its files to a Git repository; Infrahub's existing repository-sync pipeline then loads and applies the schema. The Schema Marketplace page does not directly call schema-load or schema-apply APIs.
- At least one writable (read-write) Git repository must be configured in Infrahub before a user can install a schema *via the UI commit path*. Read-only repositories are explicitly not valid install targets. The Schema Marketplace page defers repository creation to the existing repository management page but actively blocks UI install actions until the prerequisite is met, and offers the `infrahubctl` CLI alternative as an escape hatch.
- The `infrahubctl` CLI alternative assumes the user has `infrahubctl` installed locally and configured to authenticate with their Infrahub instance; the page presents commands, not a runtime — the spec does not require the web UI to execute the CLI on the user's behalf.
- The Marketplace API shape on `marketplace.infrahub.app` has changed since the prior wizard branch; the exact contract must be reconfirmed during planning (`/speckit.plan`).
- Default Marketplace URL is `https://marketplace.infrahub.app`; operators can override via backend environment variable (exact variable name decided during planning). Any mirror must honor the same API contract.
- Schema updates/migrations for already-installed schemas are out of scope; the feature only adds new schemas.
- Dependency resolution between Marketplace schemas is surfaced (warn the user) but not automated in MVP.

## Dependencies

- The configured Marketplace (default `https://marketplace.infrahub.app`) being reachable from the Infrahub backend (or an explicit, graceful failure path when it is not).
- Existing Infrahub repository management: configured Git repositories with commit and push capability.
- Existing Infrahub authentication and authorization model for write permissions on repositories.
- Existing Infrahub repository-sync pipeline picking up newly committed schema files.

## Out of Scope

- Updating or re-applying schemas that are already installed (version migration).
- Publishing user-authored schemas back to the Marketplace.
- Previewing the effect of a schema on existing data before installation.
- Offline/bundled Marketplace content for air-gapped deployments (feature must fail gracefully, but no offline bundle is shipped).
- Automated dependency resolution across Marketplace items.
- Executing `infrahubctl` commands from the web UI on the user's behalf — the CLI alternative presents copy-pasteable commands, it does not run them for the user.
- Changes to the `infrahubctl` CLI itself beyond whatever is required for existing schema-load commands to target Marketplace items (verified during planning; if new CLI flags are needed, that becomes a separate work item).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user with no schemas loaded can reach the Schema Marketplace page and complete installation of their first schema in under 3 minutes, with zero modal overlays interrupting navigation.
- **SC-002**: Across the full UI, navigating or refreshing any page never triggers a schema wizard modal — verified by end-to-end regression on the primary pages.
- **SC-003**: A user on an existing instance can install an additional Marketplace schema in under 2 minutes without encountering any first-run or setup flow.
- **SC-004**: In 100% of Marketplace connectivity-failure scenarios, the Schema Marketplace page surfaces a descriptive error within 10 seconds rather than an indefinite loading state.
- **SC-005**: 100% of failed installations leave the target Git repository in its pre-install state (no partial commits, no residual files).
- **SC-006**: Within one release of launch, support tickets referencing "wizard reappears on every refresh" drop to zero.
- **SC-007**: The Schema Marketplace page is reachable from a single click on the Schema Marketplace home-page tile and from a persistent navigation element on every page.
- **SC-008**: Every completed installation produces a Git commit on the target repository attributed to the initiating Infrahub user, verifiable via the repository's commit history.
- **SC-009**: On an instance with no writable repositories, zero UI-triggered schema installs can occur — install controls are disabled 100% of the time and the prerequisite state is shown.
- **SC-010**: In any state where the UI would allow install (writable repo present, controls enabled), the backend install endpoint independently verifies writability and write permission before committing — demonstrated by a server-side rejection when client-side state is stale.
- **SC-011**: Operators can redirect Infrahub to a non-default Marketplace (e.g., an internal mirror or test fixture) by changing a single backend environment variable and restarting the backend — no code changes required, verified end-to-end by the Schema Marketplace page listing items from the overridden source.
- **SC-012**: On an instance with no writable repositories, a user who selects one or more schemas can complete installation via the displayed `infrahubctl` command(s) on their own machine in under 2 minutes, with zero additional inputs beyond copy-paste — verified end-to-end against a test instance.
- **SC-013**: 100% of `infrahubctl` commands shown on the Schema Marketplace page reference the specific schemas the user has selected (no generic placeholders) and include a copy action per command.
