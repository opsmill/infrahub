---
Title: Documentation Reorganization — Execution Plan
Spec: dev/specs/2026-04-docs-reorganization.md
Author: Baptiste
Status: draft
---

# Documentation Reorganization — Execution Plan

Companion to `dev/specs/2026-04-docs-reorganization.md`.
This document is the step-by-step playbook for an AI agent executing the reorganization.
Each phase maps to one PR. Phases are independent and can be executed in any order once the bootstrap is done.

---

## Prerequisites

```bash
# Confirm you are on stable and it is clean
git checkout stable && git pull origin stable
# Verify docs build is clean before touching anything
uv run invoke docs.build
```

---

## Phase 0 — Bootstrap Feature Branch

**Branch:** `docs/doc-reorg` (targets `stable`)
**Goal:** Create the long-lived feature branch and establish the new top-level skeleton in `sidebars.ts` without removing any existing nodes. All section PRs target this branch.

### Steps

```bash
git checkout stable
git checkout -b docs/doc-reorg
```

Edit `docs/sidebars.ts`:

1. **Rename** the top-level `Overview` category label to `Get Started` (keep all existing items for now — they are migrated in Phase 1).
2. **Rename** the top-level `Academy` category label to `Learn` (keep all existing items for now).
3. **Insert** an empty `Features` category after `Learn`:

```ts
{
  type: 'category',
  label: 'Features',
  collapsed: false,
  collapsible: false,
  link: { type: 'generated-index', slug: 'features' },
  items: [],
},
```

4. **Insert** an empty `Operate & Extend` category after `Features`:

```ts
{
  type: 'category',
  label: 'Operate & Extend',
  collapsed: false,
  collapsible: false,
  link: { type: 'generated-index', slug: 'operate' },
  items: [],
},
```

5. Leave `Reference`, `Contributing`, `Release Notes`, and `faq/faq` exactly as-is.

### Verify & ship

```bash
uv run invoke docs.build          # must be clean
```

```bash
gh pr create \
  --base stable \
  --title "docs(reorg): bootstrap feature branch with new nav skeleton" \
  --body "Adds empty Features and Operate & Extend categories to sidebars.ts. No pages moved. All section PRs target this branch."
```

---

## Phase 1 — Get Started

**Branch:** `docs/reorg-get-started` (targets `docs/doc-reorg`)
**Spec section:** PR 1

### Steps

In `docs/sidebars.ts`, update the `Get Started` category:

```ts
{
  type: 'category',
  label: 'Get Started',
  collapsed: false,
  collapsible: false,
  link: { type: 'doc', id: 'overview/overview' },
  items: [
    {
      type: 'category',
      label: 'Introduction',
      link: { type: 'generated-index' },
      items: [
        'overview/concepts',
        'topics/architecture',
        'topics/community-vs-enterprise',
      ],
    },
    {
      type: 'category',
      label: 'Getting Started',
      link: { type: 'generated-index' },
      items: [
        'overview/quickstart',
        'overview/explore',
        'overview/next-steps',
      ],
    },
    'faq/faq',
  ],
},
```

Remove from `Topics → Overview`:
- `topics/architecture`
- `topics/community-vs-enterprise`

Remove the standalone `faq/faq` entry at the bottom of the sidebar array.

### Verify & ship

```bash
uv run invoke docs.build
```

```bash
gh pr create \
  --base docs/doc-reorg \
  --title "docs(reorg): Get Started — move Architecture, Community vs Enterprise, FAQ" \
  --body "Moves architecture and community-vs-enterprise from Topics > Overview into Get Started > Introduction. Moves FAQ from sidebar bottom into Get Started."
```

---

## Phase 2 — Learn

**Branch:** `docs/reorg-learn` (targets `docs/doc-reorg`)
**Spec section:** PR 2

### Steps

In `sidebars.ts`, update the `Learn` category:

```ts
{
  type: 'category',
  label: 'Learn',
  collapsed: false,
  collapsible: false,
  link: { type: 'doc', id: 'academy/academy' },
  items: [
    {
      type: 'category',
      label: 'Getting Started',
      link: { type: 'generated-index' },
      items: [
        'academy/getting-started/infrahub-introduction',
        'academy/getting-started/deploy-first-configuration',
      ],
    },
    {
      type: 'category',
      label: 'Tutorials',
      link: { type: 'generated-index' },
      items: [
        { type: 'doc', id: 'guides/groups', label: 'Organize objects with groups' },
      ],
    },
  ],
},
```

Remove `guides/groups` from `Guides → Data Management`.

### Verify & ship

```bash
uv run invoke docs.build
```

```bash
gh pr create \
  --base docs/doc-reorg \
  --title "docs(reorg): Learn — add Tutorials subsection, move groups guide" \
  --body "Adds Tutorials subsection under Learn. Moves guides/groups (Organize objects with groups) as the first tutorial entry."
```

---

## Phase 3 — Schema & Data Modeling _(first Features cluster)_

**Branch:** `docs/reorg-schema` (targets `docs/doc-reorg`)
**Spec section:** PR 3

### Steps

In `sidebars.ts`, add the `Schema & Data Modeling` cluster inside `Features → items`:

```ts
{
  type: 'category',
  label: 'Schema & Data Modeling',
  link: { type: 'generated-index' },
  items: [
    'topics/schema',
    'guides/create-schema',
    'guides/import-schema',
    'topics/schema-extensions',
    'topics/schema-display',
    'topics/computed-attributes',
    'guides/computed-attributes',
    'topics/order-weight',
    'guides/customize-field-ordering',
    'topics/labels',
  ],
},
```

Remove from `Topics → Core Concepts → Schema`:
- `topics/schema`, `topics/order-weight`, `topics/schema-display`, `topics/computed-attributes`, `topics/schema-extensions`, `topics/labels`

Remove from `Guides → Schema & Data Modeling`:
- `guides/create-schema`, `guides/import-schema`, `guides/computed-attributes`, `guides/customize-field-ordering`

Do **not** remove `guides/menu` — it moves in Phase 11.
Do **not** remove `topics/schema-attr-kind-number-pool` — it moves in Phase 13.

If `Topics → Core Concepts → Schema` is now empty, remove that category node.

### Verify & ship

```bash
uv run invoke docs.build
```

```bash
gh pr create \
  --base docs/doc-reorg \
  --title "docs(reorg): Features — Schema & Data Modeling cluster" \
  --body "Creates the Schema & Data Modeling capability cluster under Features. Consolidates topics/schema* and guides/schema pages. No content changes."
```

---

## Phase 4 — Version Control & Branching

**Branch:** `docs/reorg-version-control` (targets `docs/doc-reorg`)
**Spec section:** PR 4

### Steps

Add to `Features → items`:

```ts
{
  type: 'category',
  label: 'Version Control & Branching',
  link: { type: 'generated-index' },
  items: [
    'topics/version-control',
    'topics/branching',
    'topics/proposed-change',
    'guides/change-approval-workflow',
    'guides/selective-branch-sync',
  ],
},
```

Remove from `Topics → Core Concepts → Version Control & Branching`:
- `topics/version-control`, `topics/branching`, `topics/proposed-change`

Remove from `Guides → User Management & Authentication`:
- `guides/change-approval-workflow`

Remove from `Guides → Installation & Setup`:
- `guides/selective-branch-sync`

If either source category is now empty, remove it.

### Verify & ship

```bash
uv run invoke docs.build
```

```bash
gh pr create \
  --base docs/doc-reorg \
  --title "docs(reorg): Features — Version Control & Branching cluster" \
  --body "Consolidates version-control topics with change-approval-workflow (from User Management) and selective-branch-sync (from Installation & Setup). No content changes."
```

---

## Phase 5 — Data Management

**Branch:** `docs/reorg-data-management` (targets `docs/doc-reorg`)
**Spec section:** PR 5

### Steps

Add to `Features → items`:

```ts
{
  type: 'category',
  label: 'Data Management',
  link: { type: 'generated-index' },
  items: [
    'topics/graphql',
    'guides/graphql-fragment',
    'guides/object-load',
    'topics/resource-manager',
    'guides/resource-manager',
    'topics/profiles',
    'guides/profiles',
    'topics/object-template',
    'guides/object-template',
    'topics/object-conversion',
    'guides/object-conversion',
    'topics/metadata',
    'topics/file-object',
    'topics/check',
    'guides/check',
  ],
},
```

Remove from `Topics → Core Concepts → Data Management`:
- `topics/graphql`, `topics/resource-manager`, `topics/profiles`, `topics/object-template`, `topics/object-conversion`, `topics/metadata`, `topics/check`

Remove from `Topics → Core Concepts → File Storage`:
- `topics/file-object`

Remove from `Guides → Data Management`:
- `guides/object-load`, `guides/resource-manager`, `guides/profiles`, `guides/object-template`, `guides/object-conversion`, `guides/check`

Remove from `Guides → Artifact & Transform`:
- `guides/graphql-fragment`

Do **not** move `topics/groups` or `guides/groups` — Groups is Phase 2 (content consolidation needed, out of scope for this sprint).

### Verify & ship

```bash
uv run invoke docs.build
```

```bash
gh pr create \
  --base docs/doc-reorg \
  --title "docs(reorg): Features — Data Management cluster" \
  --body "Consolidates graphql, resource-manager, profiles, templates, object-conversion, metadata, file-object, and checks under Data Management. Moves graphql-fragment from Artifact & Transform. No content changes."
```

---

## Phase 6 — IPAM

**Branch:** `docs/reorg-ipam` (targets `docs/doc-reorg`)
**Spec section:** PR 6

### Steps

Add to `Features → items`:

```ts
{
  type: 'category',
  label: 'IPAM',
  link: { type: 'generated-index' },
  items: [
    'topics/ipam',
  ],
},
```

Remove from `Topics → Core Concepts → IPAM`. If that category is now empty, remove the category node.

### Verify & ship

```bash
uv run invoke docs.build
```

```bash
gh pr create \
  --base docs/doc-reorg \
  --title "docs(reorg): Features — IPAM cluster (rename from IPAM & Resource Management)" \
  --body "Moves IPAM topic into Features. Section renamed to IPAM — Resource Manager is now in Data Management."
```

---

## Phase 7 — Transforms & Artifacts

**Branch:** `docs/reorg-transforms` (targets `docs/doc-reorg`)
**Spec section:** PR 7

### Steps

Add to `Features → items`:

```ts
{
  type: 'category',
  label: 'Transforms & Artifacts',
  link: { type: 'generated-index' },
  items: [
    'topics/transformation',
    'guides/jinja2-transform',
    'guides/python-transform',
    'topics/artifact',
    'guides/artifact',
    'guides/artifact-content-composition',
    'topics/object-storage',
    'guides/object-storage',
    {
      type: 'ref',
      id: 'topics/developer-guide',
      label: 'Developer Guide',
    },
    {
      type: 'ref',
      id: 'topics/resources-testing-framework',
      label: 'Testing Framework',
    },
  ],
},
```

Remove from `Topics → Core Concepts → Transforms & Artifacts`:
- `topics/transformation`, `topics/artifact`

Remove from `Topics → Core Concepts → File Storage`:
- `topics/object-storage`

Remove from `Guides → Artifact & Transform`:
- `guides/jinja2-transform`, `guides/python-transform`, `guides/artifact`, `guides/artifact-content-composition`, `guides/object-storage`

After removing `topics/file-object` (Phase 5) and `topics/object-storage` (this phase), `Topics → Core Concepts → File Storage` should be empty — remove the category node.

### Verify & ship

```bash
uv run invoke docs.build
```

```bash
gh pr create \
  --base docs/doc-reorg \
  --title "docs(reorg): Features — Transforms & Artifacts cluster" \
  --body "Consolidates transformation topics and guides. Moves object-storage topic from File Storage (pairing it with its guide). Adds cross-links to Developer Guide and Testing Framework. No content changes."
```

---

## Phase 8 — Generators

**Branch:** `docs/reorg-generators` (targets `docs/doc-reorg`)
**Spec section:** PR 8

### Steps

Add to `Features → items`:

```ts
{
  type: 'category',
  label: 'Generators',
  link: { type: 'generated-index' },
  items: [
    'topics/generator',
    'guides/generator',
    'guides/chaining-generators',
    'topics/modular-generators',
    'guides/modular-generator-best-practices',
    {
      type: 'ref',
      id: 'topics/developer-guide',
      label: 'Developer Guide',
    },
    {
      type: 'ref',
      id: 'topics/resources-testing-framework',
      label: 'Testing Framework',
    },
  ],
},
```

Remove from `Topics → Core Concepts → Generators`:
- `topics/generator`, `topics/modular-generators`

Remove from `Guides → Generators`:
- `guides/generator`, `guides/chaining-generators`, `guides/modular-generator-best-practices`

If either source category is now empty, remove the category node.

### Verify & ship

```bash
uv run invoke docs.build
```

```bash
gh pr create \
  --base docs/doc-reorg \
  --title "docs(reorg): Features — Generators cluster" \
  --body "Consolidates generator topics and guides. Cross-links to Developer Guide and Testing Framework. No content changes."
```

---

## Phase 9 — Git Integration

**Branch:** `docs/reorg-git` (targets `docs/doc-reorg`)
**Spec section:** PR 9

### Steps

Add to `Features → items`:

```ts
{
  type: 'category',
  label: 'Git Integration',
  link: { type: 'generated-index' },
  items: [
    'topics/repository',
    'guides/repository',
    'topics/infrahub-yml',
    'topics/branch-synchronization',
  ],
},
```

Remove from `Topics → Core Concepts → Git Integration`:
- `topics/infrahub-yml`, `topics/repository`, `topics/branch-synchronization`

Remove from `Guides → Installation & Setup`:
- `guides/repository`

If `Topics → Core Concepts → Git Integration` is now empty, remove the category node.

### Verify & ship

```bash
uv run invoke docs.build
```

```bash
gh pr create \
  --base docs/doc-reorg \
  --title "docs(reorg): Features — Git Integration cluster" \
  --body "Consolidates repository topic and guide (guide was orphaned under Installation & Setup). No content changes."
```

---

## Phase 10 — Events & Integrations

**Branch:** `docs/reorg-events` (targets `docs/doc-reorg`)
**Spec section:** PR 10

### Steps

Add to `Features → items`:

```ts
{
  type: 'category',
  label: 'Events & Integrations',
  link: { type: 'generated-index' },
  items: [
    'topics/events',
    'topics/event-actions',
    'guides/events-rules-actions',
    'topics/webhooks',
    'guides/webhooks',
    'topics/activity-log',
    'topics/log-forwarding',
    'guides/log-forwarding',
  ],
},
```

Remove from `Topics → Platform Capabilities → Event Management & Logging`:
- `topics/activity-log`, `topics/events`, `topics/event-actions`, `topics/webhooks`, `topics/log-forwarding`

Remove from `Guides → Integration & Events`:
- `guides/events-rules-actions`, `guides/webhooks`, `guides/log-forwarding`

Note: `topics/tasks` is **not** moved here — it moves to Operate & Extend in Phase 12.

### Verify & ship

```bash
uv run invoke docs.build
```

```bash
gh pr create \
  --base docs/doc-reorg \
  --title "docs(reorg): Features — Events & Integrations cluster" \
  --body "Consolidates events, webhooks, activity-log, and log-forwarding. No content changes."
```

---

## Phase 11 — User Management & Security

**Branch:** `docs/reorg-user-management` (targets `docs/doc-reorg`)
**Spec section:** PR 11

### Steps

Add to `Features → items`:

```ts
{
  type: 'category',
  label: 'User Management & Security',
  link: { type: 'generated-index' },
  items: [
    'topics/authentication',
    'guides/sso',
    'topics/permissions-roles',
    'guides/accounts-permissions',
    'guides/managing-api-tokens',
    'guides/menu',
  ],
},
```

Remove from `Topics → Platform Capabilities → User Management & Authentication`:
- `topics/authentication`, `topics/permissions-roles`

Remove from `Guides → User Management & Authentication`:
- `guides/sso`, `guides/managing-api-tokens`, `guides/accounts-permissions`

Remove `guides/menu` from `Guides → Schema & Data Modeling`.

If `Guides → User Management & Authentication` is now empty, remove the category node.
If `Topics → Platform Capabilities → User Management & Authentication` is now empty, remove it.
If `Topics → Platform Capabilities` is now empty, remove the top-level category.

### Verify & ship

```bash
uv run invoke docs.build
```

```bash
gh pr create \
  --base docs/doc-reorg \
  --title "docs(reorg): Features — User Management & Security cluster" \
  --body "Consolidates authentication, permissions, SSO, API tokens. Moves menu customization from Schema & Data Modeling. No content changes."
```

---

## Phase 12 — Operate & Extend

**Branch:** `docs/reorg-operate` (targets `docs/doc-reorg`)
**Spec section:** PR 12

### Steps

In `sidebars.ts`, replace the empty `Operate & Extend` skeleton with:

```ts
{
  type: 'category',
  label: 'Operate & Extend',
  collapsed: false,
  collapsible: false,
  link: { type: 'generated-index', slug: 'operate' },
  items: [
    {
      type: 'category',
      label: 'Deploying & Managing Infrahub',
      link: { type: 'generated-index' },
      items: [
        'guides/installation',
        'guides/production-deployment',
        'topics/hardware-requirements',
        { type: 'ref', id: 'reference/configuration', label: 'Configuration' },
        'guides/configuration-changes',
        'topics/database-backup',
        'guides/database-backup',
        'guides/upgrade',
        'topics/tasks',
        { type: 'ref', id: 'reference/task-worker', label: 'Task Worker' },
        'guides/telemetry',
      ],
    },
    {
      type: 'category',
      label: 'Development Resources',
      link: { type: 'generated-index' },
      items: [
        'topics/developer-guide',
        'topics/local-demo-environment',
        'topics/resources-testing-framework',
      ],
    },
  ],
},
```

Remove from `Guides → Installation & Setup`:
- `guides/installation`, `guides/production-deployment`, `guides/configuration-changes`, `guides/database-backup`, `guides/upgrade`, `guides/telemetry`

Remove from `Topics → Platform Capabilities → System Administration`:
- `topics/hardware-requirements`, `topics/database-backup`

Remove from `Topics → Platform Capabilities → Event Management & Logging`:
- `topics/tasks`

Remove from `Topics → Development Resources`:
- `topics/developer-guide`, `topics/local-demo-environment`, `topics/resources-testing-framework`

After all removals:
- If `Guides → Installation & Setup` is now empty, remove it.
- If `Topics → Platform Capabilities → System Administration` is now empty, remove it.
- If `Topics → Platform Capabilities → Event Management & Logging` is now empty, remove it.
- If `Topics → Platform Capabilities` is now empty, remove it.
- If `Topics → Development Resources` is now empty, remove it.
- If `Topics → Core Concepts` is now empty, remove it.
- If the top-level `Topics` category is now empty, remove it.
- If `Guides → Artifact & Transform` is now empty (after phases 5 and 7), remove it.
- If `Guides → Generators` is now empty, remove it.
- If `Guides → Integration & Events` is now empty, remove it.
- If `Guides → Schema & Data Modeling` is now empty, remove it.
- If `Guides → Data Management` is now empty, remove it.
- If `Guides → Installation & Setup` is now empty, remove it.
- If the top-level `Guides` category is now empty, remove it.

### Verify & ship

```bash
uv run invoke docs.build
```

```bash
gh pr create \
  --base docs/doc-reorg \
  --title "docs(reorg): Operate & Extend — deploy/manage and dev resources clusters" \
  --body "Consolidates installation, deployment, database, tasks, and development-resource pages. Removes now-empty legacy Topics and Guides categories. No content changes."
```

---

## Phase 13 — Reference Reorganization

**Branch:** `docs/reorg-reference` (targets `docs/doc-reorg`)
**Spec section:** PR 13

### Steps

Replace the entire `Reference` category in `sidebars.ts`:

```ts
{
  type: 'category',
  label: 'Reference',
  collapsed: false,
  collapsible: false,
  link: { type: 'generated-index', slug: 'reference' },
  items: [
    {
      type: 'category',
      label: 'API',
      link: { type: 'generated-index' },
      items: [
        'reference/api-server',
        'reference/message-bus-events',
      ],
    },
    {
      type: 'category',
      label: 'CLI',
      link: { type: 'generated-index', slug: 'reference/cli' },
      items: [
        'reference/infrahub-cli/infrahub-db',
        'reference/infrahub-cli/infrahub-server',
        'reference/infrahub-cli/infrahub-dev',
        'reference/infrahub-cli/infrahub-upgrade',
      ],
    },
    {
      type: 'category',
      label: 'Configuration Files',
      link: { type: 'generated-index' },
      items: [
        'reference/configuration',
        'reference/dotinfrahub',
        'reference/menu',
        'reference/infrahub-tests',
      ],
    },
    {
      type: 'category',
      label: 'Schema Specification',
      link: { type: 'generated-index', slug: 'reference/schema' },
      items: [
        'reference/schema/node',
        'reference/schema/node-extension',
        'reference/schema/attribute',
        'reference/schema/groups',
        'reference/schema/relationship',
        'reference/schema/generic',
        'reference/schema/validator-migration',
        'topics/schema-attr-kind-number-pool',
        'reference/schema-validation',
      ],
    },
    {
      type: 'category',
      label: 'Events',
      link: { type: 'generated-index' },
      items: [
        'reference/infrahub-events',
      ],
    },
    {
      type: 'category',
      label: 'Permissions',
      link: { type: 'generated-index' },
      items: [
        'reference/permissions',
      ],
    },
    {
      type: 'category',
      label: 'Authentication',
      link: { type: 'generated-index' },
      items: [
        'reference/sso',
      ],
    },
    'reference/task-worker',
  ],
},
```

Note: `reference/task-worker` is kept in Reference as its canonical location (it is cross-linked from Operate & Extend via `type: 'ref'`). Same for `reference/configuration`.

Remove `topics/schema-attr-kind-number-pool` from the `Topics → Core Concepts → Schema` cluster (it was left there in Phase 3 — remove it now and add to Schema Specification here).

### Verify & ship

```bash
uv run invoke docs.build
```

```bash
gh pr create \
  --base docs/doc-reorg \
  --title "docs(reorg): Reference — reorganize into 7 named subgroups" \
  --body "Reorganizes Reference into API, CLI, Configuration Files, Schema Specification, Events, Permissions, Authentication subgroups. Moves topics/schema-attr-kind-number-pool to Schema Specification. No content changes."
```

---

## Phase 14 — Redirects & Final Cleanup

**Branch:** `docs/reorg-redirects` (targets `docs/doc-reorg`)
**Spec section:** PR 14

### Steps

1. **Audit URL changes.** Since this reorganization moves pages only in `sidebars.ts` (not in the filesystem), almost no URLs change — Docusaurus URL slugs follow file paths, not sidebar structure. Verify this by diffing the built `build/` sitemap against the pre-migration sitemap.

2. **Check for physical file moves.** The one candidate is `topics/schema-attr-kind-number-pool` — if it was added to the Schema Specification sidebar node by reference (no file move), no redirect is needed. Confirm by checking the built URL; it should still resolve to `/topics/schema-attr-kind-number-pool`.

3. **If any redirects are needed**, add them in `docs/docusaurus.config.ts` using the `@docusaurus/plugin-client-redirects` plugin:

```ts
[
  '@docusaurus/plugin-client-redirects',
  {
    redirects: [
      // Example — only add entries for URLs that actually changed:
      // { from: '/topics/schema-attr-kind-number-pool', to: '/reference/schema/number-pool' },
    ],
  },
],
```

4. **Run full build and verify zero broken links:**

```bash
uv run invoke docs.build
# additionally, run a link check across the built output if tooling is available:
# npx broken-link-checker http://localhost:3000 --recursive
uv run invoke docs.serve   # manual spot-check of each new nav section
```

5. **Spot-check the nav** by serving locally and confirming:
   - Get Started → Introduction shows Architecture and Community vs Enterprise
   - Get Started → FAQ is reachable
   - Features → all 9 clusters are present and populated
   - Operate & Extend → Deploying & Managing and Development Resources are present
   - Reference → 7 subgroups are present
   - Old `Topics` and `Guides` top-level categories are gone

### Verify & ship

```bash
gh pr create \
  --base docs/doc-reorg \
  --title "docs(reorg): redirects pass and final build verification" \
  --body "Adds any required Docusaurus redirects for moved pages. Confirms zero broken links across the full build. Last PR before merging doc-reorg into stable."
```

---

## Phase 15 — Merge to Stable

```bash
gh pr create \
  --base stable \
  --head docs/doc-reorg \
  --title "docs: capability-cluster navigation reorganization" \
  --body "$(cat <<'EOF'
Implements the navigation reorganization described in dev/specs/2026-04-docs-reorganization.md.

## What changed
- New top-level structure: Get Started / Learn / Features / Operate & Extend / Reference / Project
- Features section groups explanation and how-to content per capability (Schema, Version Control, Data Management, IPAM, Transforms & Artifacts, Generators, Git Integration, Events & Integrations, User Management & Security)
- Operate & Extend consolidates deployment, operations, and development resources
- Reference reorganized into 7 named lookup subgroups
- Zero content changes — navigation structure only

## Reviewed
All 14 section PRs reviewed and merged into docs/doc-reorg.
EOF
)"
```

After merge, cut a new documentation version from `stable`.

---

## Parallel Execution Notes

Phases 1–13 are independent of each other once Phase 0 is merged. They can be run concurrently by separate agents as long as each agent:
- Rebases its branch on the latest `docs/doc-reorg` before opening a PR
- Does not touch any sidebar node outside its designated section (to avoid merge conflicts)

The only hard ordering constraint:
- Phase 0 must be complete before any section PR is opened
- Phase 14 must wait for all section PRs to be merged into `docs/doc-reorg`
- Phase 15 must wait for Phase 14

---

## Merge Conflict Protocol

Because all PRs target `docs/doc-reorg` and all touch `sidebars.ts`, merge conflicts between section PRs are possible. Resolution rule:

> Keep both sections' changes. A conflict in `sidebars.ts` is always an "add both sides" resolution — one side adds a cluster, the other adds a different cluster. Never discard either side's additions.

After resolving, re-run `uv run invoke docs.build` to confirm.

---

## Rollback

If any section PR introduces a build failure that cannot be quickly fixed:
1. Close the PR without merging.
2. The `docs/doc-reorg` branch is unaffected.
3. Fix the issue in a new branch targeting `docs/doc-reorg`.
