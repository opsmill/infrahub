# Research: Configuration Wizard with Marketplace Schema Browser

**Feature**: atg-01-config-wizard | **Date**: 2026-02-26

## R1: Detecting User-Defined Schemas

**Decision**: Use the existing `RESTRICTED_NAMESPACES` constant and `user_editable` flag on namespaces to detect whether user-defined schemas exist.

**Rationale**: Infrahub already categorizes schemas by namespace. The `RESTRICTED_NAMESPACES` list in `backend/infrahub/core/constants/__init__.py` contains all built-in namespaces (`Core`, `Internal`, `Builtin`, `Account`, `Branch`, `Deprecated`, `Diff`, `Infrahub`, `Lineage`, `Schema`, `Profile`, `Template`). The `SchemaBranch.get_namespaces()` method returns each namespace with a `user_editable` boolean flag. The frontend already stores namespaces in the `namespacesAtom` Jotai atom with the `user_editable` field available.

**Detection approach (frontend)**:
```typescript
const namespaces = useAtomValue(namespacesAtom);
const nodeSchemas = useAtomValue(nodeSchemasAtom);
const genericSchemas = useAtomValue(genericSchemasAtom);
const userEditableNamespaces = namespaces.filter(ns => ns.user_editable);
const userDefinedSchemas = [...nodeSchemas, ...genericSchemas].filter(
  schema => userEditableNamespaces.some(ns => ns.name === schema.namespace)
);
const hasUserDefinedSchemas = userDefinedSchemas.length > 0;
```

**Alternatives considered**:
- Counting total schemas minus a known core count: fragile, breaks when core schemas change.
- Backend-only detection via a dedicated endpoint: adds unnecessary API surface; the data is already available on the frontend.

## R2: Marketplace API Integration Architecture

**Decision**: Create a backend proxy endpoint that forwards requests to the marketplace GraphQL API. The frontend calls the Infrahub backend, which uses the existing `HttpxAdapter` to call `https://marketplace.infrahub.app/graphql`.

**Rationale**:
- Avoids CORS issues (marketplace may not allow cross-origin requests from arbitrary Infrahub instances).
- Leverages existing `HttpxAdapter` with TLS management, timeout handling, and error normalization.
- Allows future enhancements: caching, rate limiting, schema compatibility filtering.
- Follows the established pattern used for OIDC/OAuth2 external calls in `backend/infrahub/api/oidc.py`.
- The frontend Apollo Client is tightly coupled to the Infrahub backend GraphQL endpoint (auth middleware, branch/date context). Creating a separate Apollo client for the marketplace would be complex and duplicative.

**Alternatives considered**:
- Direct frontend fetch to marketplace: CORS dependency on marketplace server, no centralized error handling, TLS issues in enterprise environments with custom CA bundles.
- Separate Apollo Client instance in frontend: over-engineered for what is essentially a few read-only queries.

## R3: Marketplace API Schema

**Decision**: Use the following marketplace GraphQL queries for the wizard:

**Schemas query** (browse catalog):
```graphql
query MarketplaceSchemas {
  schemas {
    totalCount
    edges {
      node {
        id, name, namespace, displayName, description
        downloadCount, upvoteCount, forkCount
        visibility
        tags { id, name }
        versions { id, semver, status, downloadCount }
      }
    }
  }
}
```

**Schema version content** (download for installation):
```graphql
query SchemaVersionContent($id: ID!) {
  schemaVersion(id: $id) {
    id, semver, content, downloadUrl
    dependencies { id, name, namespace }
  }
}
```

**Collections** (browse collections):
```graphql
query MarketplaceCollections {
  collections {
    totalCount
    edges {
      node {
        id, name, displayName, description
        schemaCount, downloadCount, upvoteCount
        items { id, name, displayName }
      }
    }
  }
}
```

**Tags** (for filtering):
```graphql
query MarketplaceTags {
  tags { id, name }
  tagCounts { tag { id, name }, count }
}
```

**Rationale**: These queries cover the full wizard flow: browsing schemas with metadata, fetching content for installation, browsing collections, and filtering by tags. The `schemaVersion` query provides `content` (inline schema definition) and `downloadUrl` as alternative download mechanisms. The `dependencies` field enables automatic dependency resolution (FR-015).

## R4: Background Job Architecture

**Decision**: Create a new Prefect workflow `MARKETPLACE_SCHEMA_INSTALL` that downloads schema content from the marketplace, writes files to the repository, commits, and pushes.

**Rationale**: Infrahub uses Prefect for all background operations. The existing `GIT_REPOSITORY_ADD` workflow in `backend/infrahub/workflows/catalogue.py` demonstrates the pattern. Git operations are handled through `InfrahubRepository` with worktree-based file writing, staging, commit, and push.

**Workflow steps**:
1. Fetch schema version content from marketplace (via `HttpxAdapter`)
2. Get `InfrahubRepository` instance for the user's configured repo
3. Get worktree for the default branch
4. Write each schema as a YAML file under a schemas directory (e.g., `schemas/<namespace>/<name>.yml`)
5. Stage files via `git_repo.index.add()`
6. Commit via `git_repo.index.commit()` with descriptive message
7. Push via `await repo.push(branch_name)`
8. Trigger schema reload from repository (reuse existing import mechanism)

**Alternatives considered**:
- Loading schemas directly via the schema API (bypassing repository): Would not persist schemas in the Git repository, breaking the GitOps workflow model.
- Using a Celery task instead of Prefect: The entire codebase uses Prefect; introducing Celery would violate Principle VII (Simplicity).

## R5: Wizard UI Architecture

**Decision**: Implement the wizard as a full-page overlay/modal that appears when no user-defined schemas are detected, with a multi-step flow.

**Rationale**:
- The existing `Modal` component (`frontend/app/src/shared/components/aria/modal.tsx`) supports large, centered overlays with backdrop.
- The `Content` layout component provides consistent page structure.
- No existing wizard/stepper component exists, but the codebase has clear patterns for multi-step forms (e.g., `ProposedChangeCreateForm`).
- Form infrastructure uses `react-hook-form` with compound components (`Form`, `FormField`, `FormLabel`, `FormInput`, `FormMessage`, `FormSubmit`).
- Wizard state can be managed locally with React state (no need for Jotai atoms since it's ephemeral and session-scoped).

**Step structure**:
1. Welcome/Introduction (skip option)
2. Create Credentials (`CorePasswordCredential`)
3. Configure Repository (`CoreRepository` with credential link)
4. Browse & Select Marketplace Schemas (card grid with search/filter)
5. Confirm & Install (triggers background job)

**Alternatives considered**:
- Slide-over panel: Too small (400px width) for a card-based schema browser.
- New dedicated route: Would require additional routing logic and doesn't feel like an "onboarding overlay."
- Homepage widget: Too small and not prominent enough for first-time user guidance.

## R6: Repository and Credential Creation

**Decision**: Reuse existing GraphQL mutations for credential and repository creation from within the wizard.

**Rationale**: The backend already has `InfrahubRepositoryMutation.mutate_create()` which handles repository creation, connectivity validation, and workflow submission. Credentials are created via standard `InfrahubMutationMixin` auto-generated mutations for `CorePasswordCredential`. The frontend repository form (`frontend/app/src/entities/repository/ui/repository-form.tsx`) shows the expected fields and validation patterns. The connectivity check modal (`check-connectivity-modal.tsx`) provides the pattern for validating repository access before proceeding.

**Key patterns to follow**:
- Repository creation triggers `RepositoryFinalizer.post_create()` which validates connectivity via `GitRepositoryConnectivity` RPC message
- Repository form uses `FormGroup` cards with `DynamicField` and `RelationshipField` components
- Connectivity check follows state machine: initial → pending → success/error → retry

## R7: Frontend Task Monitoring

**Decision**: After triggering the installation workflow, redirect the user to the normal dashboard and show installation progress via the existing task status infrastructure.

**Rationale**: The existing `TaskDisplay` component polls task status every 5 seconds, and the `TaskStatus` component in the header shows a pulse indicator when tasks are running. This provides consistent UX without building custom progress UI. The task system already supports filtering by related node ID and branch, enabling the user to find the installation task.

**Alternatives considered**:
- Custom WebSocket-based progress: Over-engineered, no WebSocket infrastructure exists in the codebase.
- Wizard-embedded progress bar: Would require keeping the wizard open, preventing the user from using the application.
