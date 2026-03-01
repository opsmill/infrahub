# Tasks: Configuration Wizard with Marketplace Schema Browser

**Input**: Design documents from `/specs/atg-01-config-wizard/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Test tasks are included. Tests should be written first within each story phase.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create directory structures and package initialization files for both backend and frontend

- [x] T001 [P] Create backend marketplace package with `backend/infrahub/marketplace/__init__.py`
- [x] T002 [P] Create backend test directory with `backend/tests/unit/marketplace/__init__.py`
- [x] T003 [P] Create frontend marketplace entity directory structure at `frontend/app/src/entities/marketplace/api/`, `frontend/app/src/entities/marketplace/ui/`, and `frontend/app/src/entities/marketplace/types.ts`
- [x] T004 [P] Create frontend config-wizard entity directory structure at `frontend/app/src/entities/config-wizard/ui/`, `frontend/app/src/entities/config-wizard/hooks/`, and `frontend/app/src/entities/config-wizard/types.ts`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Backend marketplace client and Pydantic models shared by US2 and US3; frontend shared types

**CRITICAL**: No user story work can begin until this phase is complete

- [x] T005 Create Pydantic response models (MarketplaceSchemaResponse, MarketplaceTag, MarketplaceVersionSummary, MarketplaceVersionContent, MarketplaceDependency, MarketplaceCollectionResponse, MarketplaceCollectionItem, MarketplaceInstallRequest, MarketplaceInstallModel) in `backend/infrahub/marketplace/models.py` — follow data-model.md, use frozen BaseModel, transform camelCase→snake_case via field aliases
- [x] T006 Create marketplace GraphQL client class using HttpxAdapter to query `https://marketplace.infrahub.app/graphql` in `backend/infrahub/marketplace/client.py` — methods: `get_schemas()`, `get_collections()`, `get_tags()`, `get_schema_version_content(version_id)` — follow the HttpxAdapter pattern from `backend/infrahub/services/adapters/http/httpx.py` and OIDC external call pattern in `backend/infrahub/api/oidc.py`
- [x] T007 [P] Write unit tests for Pydantic model validation (camelCase alias parsing, field constraints, optional fields) in `backend/tests/unit/marketplace/test_models.py`
- [x] T008 [P] Write unit tests for marketplace client (mock HttpxAdapter, verify GraphQL query construction, error handling for 502/timeout) in `backend/tests/unit/marketplace/test_client.py`
- [x] T009 [P] Define frontend TypeScript types (MarketplaceSchema, MarketplaceCollection, MarketplaceTag, WizardStep, WizardState) in `frontend/app/src/entities/marketplace/types.ts` and `frontend/app/src/entities/config-wizard/types.ts` — follow data-model.md TypeScript types section

**Checkpoint**: Foundation ready — marketplace client can fetch data from marketplace API, models validate responses, types are defined for frontend

---

## Phase 3: User Story 1 — First-Time Setup Wizard Trigger (Priority: P1) MVP

**Goal**: When no user-defined schemas exist, display a configuration wizard that guides users through creating credentials and connecting a Git repository

**Independent Test**: Deploy a fresh Infrahub instance with no user-defined schemas, log in, verify the wizard appears. Create credentials and repository through the wizard. Verify the wizard does not appear when user-defined schemas exist.

### Tests for User Story 1

- [ ] T010 [P] [US1] Write unit test for `useHasUserSchemas` hook in `frontend/app/src/entities/config-wizard/hooks/use-has-user-schemas.test.ts` — test that it returns `false` when only restricted-namespace schemas exist, `true` when user-editable namespace schemas exist, using mock Jotai atoms for `namespacesAtom`, `nodeSchemasAtom`, `genericSchemasAtom`
- [ ] T011 [P] [US1] Write unit test for config-wizard component in `frontend/app/src/entities/config-wizard/ui/config-wizard.test.tsx` — test step navigation (welcome→credentials→repository), skip/dismiss behavior, step indicator rendering

### Implementation for User Story 1

- [x] T012 [US1] Implement `useHasUserSchemas` hook in `frontend/app/src/entities/config-wizard/hooks/use-has-user-schemas.ts` — read `namespacesAtom`, `nodeSchemasAtom`, `genericSchemasAtom` via `useAtomValue`, filter schemas by user-editable namespaces, return boolean. Follow research.md R1 detection approach
- [x] T013 [P] [US1] Create wizard welcome step component in `frontend/app/src/entities/config-wizard/ui/wizard-step-welcome.tsx` — display welcome message explaining the setup process, "Get Started" button to advance, "Skip" button to dismiss. Use existing `Button` component variants from `frontend/app/src/shared/components/ui/button.tsx`
- [x] T014 [P] [US1] Create wizard credentials step component in `frontend/app/src/entities/config-wizard/ui/wizard-step-credentials.tsx` — form with name, username, password fields for CorePasswordCredential creation. Use existing `Form`, `FormField`, `FormLabel`, `FormInput`, `FormMessage`, `FormSubmit` components from `frontend/app/src/shared/components/ui/form.tsx`. Use GraphQL mutation for CorePasswordCredentialCreate. On success, store credential ID in wizard state and advance to next step
- [x] T015 [P] [US1] Create wizard repository step component in `frontend/app/src/entities/config-wizard/ui/wizard-step-repository.tsx` — form with name, location (URL), default_branch fields, linked credential from previous step. Use GraphQL mutation for CoreRepositoryCreate. Follow patterns from existing `frontend/app/src/entities/repository/ui/repository-form.tsx`. Include connectivity validation following `frontend/app/src/entities/repository/ui/check-connectivity-modal.tsx` pattern. On success, store repository ID in wizard state and advance
- [x] T016 [US1] Create main wizard shell component in `frontend/app/src/entities/config-wizard/ui/config-wizard.tsx` — full-page modal overlay using existing `Modal` component from `frontend/app/src/shared/components/aria/modal.tsx`. Manage WizardState with React useState (currentStep, credentialId, repositoryId, selectedSchemaVersionIds). Render step indicator showing progress. Render current step component. Handle skip/dismiss. Steps: welcome → credentials → repository → schemas → confirm (schemas and confirm steps will be placeholders until US2/US3)
- [x] T017 [US1] Wire wizard trigger into app layout in `frontend/app/src/pages/app-layout.tsx` — import `useHasUserSchemas` hook, conditionally render `ConfigWizard` component when `hasUserSchemas` is `false`. Wizard should overlay the existing layout, not replace it. Pass `onDismiss` callback that closes the wizard for the current session

**Checkpoint**: At this point, User Story 1 should be fully functional — wizard appears on fresh instance, user can create credentials and repository, wizard can be dismissed. Schema browsing step is a placeholder.

---

## Phase 4: User Story 2 — Marketplace Schema Browsing and Selection (Priority: P2)

**Goal**: Display a visual catalog of marketplace schemas as cards with search/filter, allowing multi-select of schemas and collections

**Independent Test**: Navigate to the schema selection step in the wizard (or render marketplace browser in isolation). Verify schemas load from marketplace proxy API, cards display correct metadata, search filters results, tag filter works, multi-select with visual highlighting works, collections are browsable.

### Tests for User Story 2

- [ ] T018 [P] [US2] Write unit test for marketplace schema card component in `frontend/app/src/entities/marketplace/ui/marketplace-schema-card.test.tsx` — test rendering of display name, description, download count, tags, upvote count, selected/unselected visual states, click handler
- [ ] T019 [P] [US2] Write unit test for marketplace browser component in `frontend/app/src/entities/marketplace/ui/marketplace-browser.test.tsx` — test grid rendering, search filtering, tag filtering, multi-select state management, empty state, loading state, error state with retry

### Implementation for User Story 2

- [x] T020 [P] [US2] Create marketplace proxy REST endpoints in `backend/infrahub/api/marketplace.py` — implement `GET /api/marketplace/schemas` (with optional `search` and `tags` query params), `GET /api/marketplace/collections`, `GET /api/marketplace/tags`, `GET /api/marketplace/schemas/{schema_id}/versions/{version_id}`. Use marketplace client from T006. Transform camelCase responses to snake_case via Pydantic models. Return 502 on marketplace unreachable. Follow FastAPI router pattern from `backend/infrahub/api/schema.py`. Require authentication via `get_current_user` dependency
- [x] T021 [US2] Register marketplace router in `backend/infrahub/api/main.py` — add `from infrahub.api.marketplace import router as marketplace_router` and include router with prefix `/api/marketplace`
- [x] T022 [P] [US2] Create marketplace API query functions in `frontend/app/src/entities/marketplace/api/marketplace.queries.ts` — functions to call proxy endpoints: `fetchMarketplaceSchemas(search?, tags?)`, `fetchMarketplaceCollections()`, `fetchMarketplaceTags()`, `fetchSchemaVersionContent(schemaId, versionId)`. Use existing `fetchUrl` from `frontend/app/src/shared/api/rest/fetch.ts` or React Query `useQuery` hooks
- [x] T023 [P] [US2] Create marketplace schema card component in `frontend/app/src/entities/marketplace/ui/marketplace-schema-card.tsx` — card displaying: displayName as title, description (truncated), download count with icon, upvote count with icon, tags as badges, selected state with visual border highlight. Use existing `Card` from `frontend/app/src/shared/components/ui/card.tsx` and `Badge` from `frontend/app/src/shared/components/ui/badge.tsx`. Accept `onSelect`/`onDeselect` callbacks and `isSelected` prop
- [x] T024 [US2] Create marketplace browser component in `frontend/app/src/entities/marketplace/ui/marketplace-browser.tsx` — grid of MarketplaceSchemaCard components. Include search input for name filtering, tag filter dropdown (fetch tags from API), selected schemas summary panel. Manage selection state as `Set<string>` of version IDs. Support toggling between "Schemas" and "Collections" tabs. Handle loading state (skeleton cards), error state (retry button), empty state. Use React Query for data fetching with appropriate loading/error handling
- [x] T025 [US2] Create wizard schemas step component in `frontend/app/src/entities/config-wizard/ui/wizard-step-schemas.tsx` — embed `MarketplaceBrowser` component from T024. Pass selected version IDs from wizard state. On selection changes, update wizard state. Include "Next" button (enabled when at least 1 schema selected) and "Back" button to return to repository step
- [x] T026 [US2] Wire schemas step into wizard shell — update `frontend/app/src/entities/config-wizard/ui/config-wizard.tsx` to render `WizardStepSchemas` when `currentStep === "schemas"`. Replace placeholder from US1. After repository step completes, advance to schemas step

**Checkpoint**: At this point, User Stories 1 AND 2 should both work — wizard triggers, user creates credentials/repo, then browses and selects marketplace schemas. Confirm step is still placeholder.

---

## Phase 5: User Story 3 — Schema Installation via Background Job (Priority: P3)

**Goal**: Confirm selected schemas and trigger a Prefect background job that downloads schema content, commits files to the repository, and pushes to remote. User sees progress via existing task monitoring.

**Independent Test**: With a pre-configured repository and pre-selected schema versions, trigger the install endpoint via API. Verify the Prefect workflow runs, downloads schema content, writes YAML files to the repo, commits, and pushes. Verify the frontend confirm step triggers the install and dismisses the wizard.

### Tests for User Story 3

- [ ] T027 [P] [US3] Write unit test for marketplace install Prefect workflow in `backend/tests/unit/marketplace/test_tasks.py` — mock HttpxAdapter and InfrahubRepository, verify workflow fetches schema content for each version ID, writes files to correct paths, stages, commits with descriptive message, and pushes. Test dependency resolution: when a schema has dependencies, verify dependent schemas are also fetched and written. Test error handling: marketplace unreachable, git push failure

### Implementation for User Story 3

- [x] T028 [US3] Implement Prefect workflow for marketplace schema installation in `backend/infrahub/marketplace/tasks.py` — create `@flow` decorated `install_marketplace_schemas(model: MarketplaceInstallModel)` function. Steps: (1) create marketplace client via HttpxAdapter, (2) fetch content for each schema_version_id, (3) resolve dependencies recursively (fetch dependent version content), (4) get InfrahubRepository by repository_id, (5) get worktree for branch_name, (6) write each schema as YAML file at `schemas/<namespace>/<name>.yml` in worktree directory, (7) stage all new files via `git_repo.index.add()`, (8) commit with message "Add marketplace schemas: <comma-separated names>", (9) push via `await repo.push(branch_name)`. Follow patterns from `backend/infrahub/git/tasks.py` (especially `add_git_repository` workflow). Handle errors at each step with descriptive messages
- [x] T029 [US3] Register MARKETPLACE_SCHEMA_INSTALL workflow in `backend/infrahub/workflows/catalogue.py` — add `WorkflowDefinition(name="marketplace-schema-install", type=WorkflowType.USER, module="infrahub.marketplace.tasks", function="install_marketplace_schemas")` and add to WORKFLOWS list
- [x] T030 [US3] Create install trigger endpoint `POST /api/marketplace/install` in `backend/infrahub/api/marketplace.py` — validate MarketplaceInstallRequest body, verify repository exists via database lookup, submit MARKETPLACE_SCHEMA_INSTALL workflow via `service.workflow.submit_workflow()`, return 202 with task_id. Follow pattern from `backend/infrahub/repositories/create_repository.py` for workflow submission
- [x] T031 [P] [US3] Create wizard confirm step component in `frontend/app/src/entities/config-wizard/ui/wizard-step-confirm.tsx` — display summary of selected schemas (names, count), repository name, and "Install" button. On install click: call `POST /api/marketplace/install` with repository_id, selected schema_version_ids, and branch_name from wizard state. Show loading state during API call. On success (202): display success message with task ID reference, then dismiss wizard after short delay. On failure: display error message with retry option. Include "Back" button to return to schema selection
- [x] T032 [US3] Wire confirm step into wizard shell — update `frontend/app/src/entities/config-wizard/ui/config-wizard.tsx` to render `WizardStepConfirm` when `currentStep === "confirm"`. Replace placeholder from US2. After schemas step, advance to confirm step. On successful install, close wizard modal

**Checkpoint**: All user stories should now be independently functional — full wizard flow from trigger to schema installation works end-to-end

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: E2E tests, edge case handling, and documentation

- [ ] T033 [P] Write Playwright E2E test for full wizard flow in `frontend/app/tests/e2e/config-wizard.spec.ts` — test: (1) wizard appears on fresh instance, (2) credential creation step, (3) repository creation step with connectivity check, (4) marketplace schema browsing with search/filter, (5) schema selection and confirm, (6) install trigger and wizard dismiss. Mock marketplace proxy responses. Verify wizard does not appear after schemas are loaded
- [ ] T034 [P] Add error handling for marketplace API unavailability — in `frontend/app/src/entities/marketplace/ui/marketplace-browser.tsx` add error state with "Marketplace is currently unavailable" message, retry button, and option to skip marketplace step. In `frontend/app/src/entities/config-wizard/ui/wizard-step-schemas.tsx` add "Skip" button that allows advancing without selecting schemas
- [ ] T035 [P] Add edge case handling for empty marketplace catalog — in `frontend/app/src/entities/marketplace/ui/marketplace-browser.tsx` display empty state with message "No schemas available in the marketplace" and guidance text when schemas list is empty
- [x] T036 [P] Add Towncrier changelog fragment for configuration wizard feature in `changelog/+config-wizard.added.md`
- [x] T037 Run formatters and linters — `uv run invoke format` and `uv run invoke lint` for backend, `cd frontend/app && npm run biome:fix` for frontend. Fix any issues found

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup (T001-T004) — BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational (T005-T009) — Can start after foundational
- **User Story 2 (Phase 4)**: Depends on Foundational (T005-T009) — Can start in parallel with US1 (backend tasks), but frontend schema step depends on US1 wizard shell (T016)
- **User Story 3 (Phase 5)**: Depends on Foundational (T005-T009) — Can start backend tasks in parallel with US1/US2, but frontend confirm step depends on US2 schema step (T025-T026)
- **Polish (Phase 6)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational — No dependencies on other stories. Creates the wizard shell that US2 and US3 plug into
- **User Story 2 (P2)**: Backend proxy endpoints (T020-T021) can start after Foundational. Frontend schema browser (T023-T024) can start after Foundational. Wizard schemas step (T025-T026) depends on US1 wizard shell (T016)
- **User Story 3 (P3)**: Backend workflow (T028-T030) can start after Foundational. Frontend confirm step (T031-T032) depends on US2 schema step completion (T026)

### Within Each User Story

- Tests written first, verify they fail
- Models/types before services/hooks
- Backend before frontend (for API endpoints)
- Core components before integration
- Story complete before moving to next priority

### Parallel Opportunities

**Phase 1** (all parallel):
- T001, T002, T003, T004 — different directories, no conflicts

**Phase 2** (partial parallel):
- T005 and T006 are sequential (client uses models)
- T007, T008, T009 — all parallel (different files, depend only on T005/T006)

**Phase 3 (US1)** — within story:
- T010, T011 — parallel (different test files)
- T013, T014, T015 — parallel (different step components)
- T016 depends on T012-T015 (wizard shell uses steps)
- T017 depends on T016 (wiring into app-layout)

**Phase 4 (US2)** — within story:
- T018, T019 — parallel (different test files)
- T020 and T022, T023 — backend and frontend can run in parallel
- T024 depends on T022, T023 (browser uses cards and API queries)

**Phase 5 (US3)** — within story:
- T027 — can run parallel with US2 frontend tasks
- T028-T029 (backend) can run parallel with US2 frontend tasks
- T031 depends on T030 (confirm step calls install endpoint)

**Cross-story parallelism**:
- US1 frontend (T012-T017) and US2 backend (T020-T021) can run in parallel
- US3 backend (T028-T030) can run in parallel with US2 frontend (T023-T026)

---

## Parallel Example: User Story 2

```bash
# Launch backend and frontend in parallel:
Agent 1: "Create marketplace proxy REST endpoints in backend/infrahub/api/marketplace.py" (T020)
Agent 2: "Create marketplace schema card component in frontend/app/src/entities/marketplace/ui/marketplace-schema-card.tsx" (T023)

# After both complete, launch browser (depends on card + API):
Agent 1: "Create marketplace browser component in frontend/app/src/entities/marketplace/ui/marketplace-browser.tsx" (T024)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T004)
2. Complete Phase 2: Foundational (T005-T009)
3. Complete Phase 3: User Story 1 (T010-T017)
4. **STOP and VALIDATE**: Test wizard trigger, credential creation, repository setup
5. Deploy/demo — wizard appears and guides through repo setup

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy/Demo (MVP!)
3. Add User Story 2 → Test independently → Deploy/Demo (marketplace browsing works)
4. Add User Story 3 → Test independently → Deploy/Demo (full install flow)
5. Polish → E2E tests, edge cases, changelog

### Suggested MVP Scope

User Story 1 (P1) is the minimum viable product: wizard trigger + credential creation + repository setup. This alone provides value by guiding new users through the initial repository connection. Schema browsing and installation (US2 + US3) can be added incrementally.

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Existing GraphQL mutations for CorePasswordCredential and CoreRepository creation are reused — no new backend mutations needed for US1
- Marketplace proxy endpoints serve both US2 (browsing) and US3 (content download)
- The install workflow (US3) follows the exact same pattern as existing `add_git_repository` in `backend/infrahub/git/tasks.py`
