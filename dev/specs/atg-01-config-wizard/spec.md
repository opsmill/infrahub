# Feature Specification: Configuration Wizard with Marketplace Schema Browser

**Feature Branch**: `atg-01-config-wizard`
**Created**: 2026-02-26
**Status**: Draft
**Input**: User description: "Configuration wizard that prompts users with no user-defined schema to add a repository (credentials + read/write repo) and select schemas from the Infrahub marketplace to commit and push via background job"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - First-Time Setup Wizard Trigger (Priority: P1)

A new Infrahub user logs in for the first time. The system has no user-defined schemas (only built-in core schemas). The user sees a configuration wizard that guides them through setting up their first repository and selecting schemas from the marketplace. This is the primary onboarding flow that reduces time-to-value for new users.

**Why this priority**: Without the wizard trigger and the repository setup step, users have no guided path to get started. This is the foundational flow that everything else builds on.

**Independent Test**: Can be fully tested by deploying a fresh Infrahub instance with no user-defined schemas, logging in, and verifying the wizard appears with the repository setup step.

**Acceptance Scenarios**:

1. **Given** a fresh Infrahub instance with no user-defined schemas, **When** a user navigates to the application, **Then** the configuration wizard is displayed prompting them to get started.
2. **Given** the wizard is displayed, **When** the user begins the setup flow, **Then** they are guided to create credentials (username/password) for their Git repository.
3. **Given** the user has created credentials, **When** they proceed to the next step, **Then** they can configure a read/write repository (name, URL, branch) linked to those credentials.
4. **Given** the user has previously completed the wizard (user-defined schemas exist), **When** they return to the application, **Then** the wizard does not appear and the normal dashboard is shown.
5. **Given** the wizard is displayed, **When** the user dismisses or skips the wizard, **Then** they land on the normal dashboard and the wizard does not reappear unless schemas are removed.

---

### User Story 2 - Marketplace Schema Browsing and Selection (Priority: P2)

After setting up a repository, the user is presented with a visual catalog of schemas available in the Infrahub Marketplace. Schemas are displayed as cards showing name, description, download count, and tags. The user can browse, search/filter, and select one or more schemas to install.

**Why this priority**: The marketplace browsing experience is the core value proposition—users need a visual, intuitive way to discover and pick the right schemas for their use case.

**Independent Test**: Can be tested by rendering the marketplace browser step in isolation, verifying it fetches and displays schemas from the marketplace API, and confirming selection state management works correctly.

**Acceptance Scenarios**:

1. **Given** the user has completed the repository setup step, **When** they advance to the schema selection step, **Then** they see a grid of cards representing available marketplace schemas.
2. **Given** the marketplace browser is displayed, **When** the user views a schema card, **Then** they can see the schema's display name, description, download count, tags, and popularity indicators.
3. **Given** the marketplace browser is displayed, **When** the user selects one or more schema cards, **Then** the selected cards are visually highlighted and a summary of selected schemas is shown.
4. **Given** the user has selected schemas, **When** they deselect a schema, **Then** it is removed from the selection and the summary updates.
5. **Given** the marketplace browser is displayed, **When** the user searches or filters by tag, **Then** only matching schemas are shown.
6. **Given** collections exist in the marketplace, **When** the user browses schemas, **Then** they can also view and select entire collections (groups of related schemas) as a unit.

---

### User Story 3 - Schema Installation via Background Job (Priority: P3)

After selecting schemas, the user confirms their selection. The system downloads the selected schema content from the marketplace, commits the schema files to the user's repository, and pushes them to the remote—all as a background job. The user sees progress feedback and can continue using the application while the job runs.

**Why this priority**: This is the final delivery step that makes the selected schemas available in the user's Infrahub instance. It depends on the repository and schema selection steps being complete.

**Independent Test**: Can be tested by triggering the installation action with pre-selected schemas and a pre-configured repository, verifying the background job creates correct schema files, commits, and pushes them.

**Acceptance Scenarios**:

1. **Given** the user has selected schemas and confirmed their selection, **When** the installation begins, **Then** the wizard view transitions away and the user sees a progress indicator for the background job.
2. **Given** the background job is running, **When** the schema files are being downloaded and committed, **Then** the user can continue using other parts of the application.
3. **Given** the background job completes successfully, **When** the user checks the task status, **Then** they see a success indicator and the new schemas are available in the schema browser.
4. **Given** the background job fails (e.g., network error, push failure), **When** the user checks the task status, **Then** they see a clear error message with guidance on how to retry or troubleshoot.
5. **Given** schemas with dependencies exist (marketplace schemas that depend on other schemas), **When** the user selects a schema with dependencies, **Then** the system automatically includes the required dependent schemas in the installation.

---

### Edge Cases

- What happens when the marketplace API is unreachable or returns an error? The wizard should display a clear error state with a retry option, and optionally allow the user to skip the marketplace step and proceed with manual schema setup.
- What happens when the user's Git credentials are invalid or the repository URL is unreachable? The connectivity check should provide a clear error message before proceeding, consistent with the existing repository connectivity check flow.
- What happens when a selected schema version has content that is incompatible with the current Infrahub version? The system should validate schema compatibility before committing and surface any validation errors to the user.
- What happens when the user navigates away from the wizard mid-flow? The wizard state should be preserved so the user can resume from where they left off within the same session.
- What happens when multiple users on the same instance trigger the wizard simultaneously? The first completed setup should prevent the wizard from appearing for subsequent users.
- What happens when the marketplace returns no schemas (empty catalog)? The wizard should display an appropriate empty state with guidance.
- What happens when the background push fails due to remote repository permissions? The error should clearly indicate it is a remote permission issue and suggest verifying credentials.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST detect whether user-defined schemas exist and display the configuration wizard when none are present.
- **FR-002**: System MUST provide a guided multi-step wizard flow with clear step indicators (credentials → repository → schema selection → confirmation).
- **FR-003**: System MUST allow users to create Git credentials (username and password) as the first step of the wizard.
- **FR-004**: System MUST allow users to configure a read/write Git repository with name, URL, default branch, and linked credentials as the second step.
- **FR-005**: System MUST validate repository connectivity before allowing the user to proceed past the repository step.
- **FR-006**: System MUST fetch and display available schemas from the Infrahub Marketplace (https://marketplace.infrahub.app/graphql) as browsable cards.
- **FR-007**: System MUST display schema metadata on each card: display name, description, download count, tags, and upvote count.
- **FR-008**: System MUST allow users to select multiple schemas from the marketplace catalog.
- **FR-009**: System MUST allow users to search schemas by name and filter schemas by tag.
- **FR-010**: System MUST support browsing and selecting collections (curated groups of schemas) in addition to individual schemas.
- **FR-011**: System MUST download the content of selected schemas from the marketplace using the schema version's content/download endpoint.
- **FR-012**: System MUST commit downloaded schema files to the user's configured repository and push to the remote as a background job.
- **FR-013**: System MUST provide visual feedback on background job progress, success, and failure states.
- **FR-014**: System MUST allow users to dismiss/skip the wizard without completing it, and not show it again unless the trigger condition (no user-defined schemas) recurs.
- **FR-015**: System MUST resolve and include schema dependencies automatically when a selected schema has dependencies.

### Key Entities

- **Marketplace Schema**: A schema definition published to the Infrahub Marketplace. Key attributes: name, namespace, display name, description, tags, download count, upvote count, visibility, versions (each with semver, content, download URL, and dependencies).
- **Marketplace Collection**: A curated group of related marketplace schemas. Key attributes: name, display name, description, schema count, items.
- **Credential**: Authentication information for accessing a Git repository. Key attributes: name, username, password. Maps to existing `CorePasswordCredential` in Infrahub.
- **Repository**: A Git repository where schema files are stored and synced. Key attributes: name, location (URL), default branch, credential reference. Maps to existing `CoreRepository` in Infrahub.
- **Wizard State**: Tracks the user's progress through the multi-step wizard. Key attributes: current step, completed steps, created credential reference, created repository reference, selected schemas.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users with no prior Infrahub experience can go from first login to having schemas loaded in under 5 minutes using the wizard.
- **SC-002**: 90% of users who start the wizard complete it successfully on their first attempt.
- **SC-003**: The marketplace schema catalog displays within 3 seconds of reaching the schema selection step.
- **SC-004**: Schema installation background job completes (download, commit, push) within 60 seconds for up to 10 selected schemas.
- **SC-005**: Users can clearly determine the current status of the schema installation at any point (in progress, success, or failure with actionable error message).

## Assumptions

- The Infrahub Marketplace GraphQL API at `https://marketplace.infrahub.app/graphql` is publicly accessible without authentication for reading schemas, collections, and schema version content.
- The detection of "no user-defined schemas" is based on whether any non-core schemas (schemas outside the built-in `Core`, `Internal`, `Builtin`, and `Profile` namespaces) are loaded in the system.
- The wizard is displayed as a full-page or prominent modal experience, not a side panel, to give it appropriate visibility for first-time users.
- The schema content retrieved from the marketplace is in a format compatible with Infrahub's schema loading (YAML or JSON schema definitions).
- The background job for committing and pushing schemas to the repository uses the existing Prefect-based workflow infrastructure.
- Only admin-level users can trigger the configuration wizard (or all users can see it, but only admins can complete the repository/credential creation steps, following existing permission models).
