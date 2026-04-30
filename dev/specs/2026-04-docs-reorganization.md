---
Title: Documentation Reorganization — Capability-Cluster Navigation
Author:
  - Baptiste
Status: draft
---

# Documentation Reorganization — Capability-Cluster Navigation

## Summary

Reorganize the Infrahub documentation navigation from a folder-per-Diataxis-mode structure (`Topics/`, `Guides/`) into a capability-cluster structure where explanation and how-to content for the same feature live together under one nav node.

No existing content is rewritten or deleted in this phase. Every change is a navigation move: updating `sidebars.ts` entries and adding cross-links. Redirect configuration is added after all sections land.

The authoritative description of the target structure — including the reasoning behind every contested placement decision — lives in `docs/AGENTS.md`. This spec drives execution, not design.

## Problem Statement

- Users must hunt across `Topics` and `Guides` to understand and use a single feature.
- AI assistants miss content buried deep in the menu hierarchy.
- The docs actively dissuade prospects and candidates from exploring Infrahub.
- The root cause is a common misapplication of Diataxis: the four modes were mapped to four top-level folders, forcing a rigid split that the framework never requires.

## Target Structure

Six top-level sections (full rationale in `docs/AGENTS.md`):

| Section | Audience intent |
|---|---|
| **Get Started** | "What is Infrahub? How do I try it?" |
| **Learn** | "Teach me by doing — structured, linear." |
| **Features** | "I'm using Infrahub. How does X work and how do I do Y?" |
| **Operate & Extend** | "I'm running it in production / building on it." |
| **Reference** | "I need to look up a specific parameter or spec." |
| **Project** | Contributing and release notes. |

## Execution Approach

### Branch model

```
stable
  └── docs/doc-reorg          ← long-lived feature branch (base for all section PRs)
        ├── docs/reorg-get-started
        ├── docs/reorg-learn
        ├── docs/reorg-schema
        ├── docs/reorg-version-control
        ├── docs/reorg-data-management
        ├── docs/reorg-ipam
        ├── docs/reorg-transforms-artifacts
        ├── docs/reorg-generators
        ├── docs/reorg-git-integration
        ├── docs/reorg-events-integrations
        ├── docs/reorg-user-management
        ├── docs/reorg-operate-extend
        ├── docs/reorg-reference
        └── docs/reorg-redirects  ← final pass, after all sections are merged
```

### Per-section PR rules

Each per-section PR:
1. Targets `docs/doc-reorg`, never `stable`.
2. Touches only `sidebars.ts` and, where required, adds `custom_edit_url`-style cross-links or `type: 'ref'` sidebar nodes. **No content edits.**
3. Must build cleanly (`uv run invoke docs.build`) with zero broken-link errors before the PR is opened.
4. Gets a manual human review before merging into `docs/doc-reorg`.

### Redirect pass

After all section PRs are merged into `docs/doc-reorg`, a single dedicated PR adds Docusaurus redirect entries for every URL whose slug changes. This PR also does a final broken-link check across the full site.

### Final merge

`docs/doc-reorg` is merged into `stable` as a single PR. A new doc version is released from `stable`.

---

## Section Work Breakdown

Each section below lists:
- **Sidebar changes** — what `sidebars.ts` must look like after the PR (described as the node structure, not code).
- **Cross-links needed** — `type: 'ref'` nodes or in-page links to add.
- **Redirects needed** — old slug → new slug for every page whose URL changes.

### PR 1 — Get Started

**Goal:** Surface Architecture and Community vs Enterprise alongside the existing overview pages; move FAQ from the bottom of the sidebar into this section.

**Sidebar changes:**
- Rename the existing `Overview` category to `Get Started` with two subsections:
  - **Introduction**: `overview/overview` (landing), `topics/architecture`, `topics/community-vs-enterprise`, `overview/concepts`
  - **Getting Started**: `overview/quickstart`, `overview/explore`, `overview/next-steps`
- Add `faq/faq` as a third item directly under `Get Started` (not nested deeper).
- Remove `topics/architecture` and `topics/community-vs-enterprise` from the `Topics → Overview` category (those nodes are removed entirely since the `Topics` top-level category is being replaced by `Features` in later PRs).

**Redirects needed:**
- None — the `.mdx` files do not move, only the sidebar references change. URL slugs are determined by the file paths which are unchanged.

---

### PR 2 — Learn

**Goal:** Rename the `Academy` section to `Learn`, surface the Academy landing page as a named item, and create a `Tutorials` subsection.

**Sidebar changes:**
- Rename top-level category label from `Academy` to `Learn`.
- Keep `academy/academy` as the section landing page.
- Keep the existing `Getting Started` subsection (courses) unchanged.
- Add a new `Tutorials` subsection containing `guides/groups` (the "Organize objects with groups" guide — first tutorial to migrate). Label it "Organize objects with groups" in the sidebar.
- Remove `guides/groups` from its current location in `Guides → Data Management`.

**Cross-links needed:**
- `guides/groups` in the `Tutorials` node should have its sidebar label set to "Organize objects with groups".

**Redirects needed:**
- None — file paths unchanged.

---

### PR 3 — Schema & Data Modeling _(first Features section)_

**Goal:** Create the `Features` top-level category with its first cluster: Schema & Data Modeling. This PR also establishes the `Features` category node in `sidebars.ts`.

**Sidebar changes — new `Features` category with `Schema & Data Modeling` cluster:**

```
Features
  └── Schema & Data Modeling
        ├── topics/schema              (Understanding Schemas)
        ├── guides/create-schema
        ├── guides/import-schema
        ├── topics/schema-extensions
        ├── topics/schema-display
        ├── topics/computed-attributes
        ├── guides/computed-attributes
        ├── topics/order-weight
        ├── guides/customize-field-ordering
        ├── topics/labels
```

- Remove these pages from their current locations in `Topics → Core Concepts → Schema` and `Guides → Schema & Data Modeling`.
- `guides/menu` (Menu Customization) is **not** moved in this PR — it moves in the User Management PR.

**Redirects needed:**
- None — file paths unchanged.

---

### PR 4 — Version Control & Branching

**Sidebar changes:**

```
Features
  └── Version Control & Branching
        ├── topics/version-control
        ├── topics/branching
        ├── topics/proposed-change
        ├── guides/change-approval-workflow   (moved from Guides → User Management)
        ├── guides/selective-branch-sync      (moved from Guides → Installation & Setup)
```

- Remove `guides/change-approval-workflow` from `Guides → User Management & Authentication`.
- Remove `guides/selective-branch-sync` from `Guides → Installation & Setup`.

**Redirects needed:**
- None.

---

### PR 5 — Data Management

**Sidebar changes:**

```
Features
  └── Data Management
        ├── topics/graphql
        ├── guides/graphql-fragment          (moved from Guides → Artifact & Transform)
        ├── guides/object-load
        ├── topics/resource-manager
        ├── guides/resource-manager
        ├── topics/profiles
        ├── guides/profiles
        ├── topics/object-template
        ├── guides/object-template
        ├── topics/object-conversion
        ├── guides/object-conversion
        ├── topics/metadata
        ├── topics/file-object               (moved from Topics → File Storage)
        ├── topics/check
        ├── guides/check
```

Notes:
- `topics/groups` and `guides/groups` are **not** included here — Groups is flagged as a Phase 2 migration (content consolidation required, not just nav move). Leave both in place for now.
- `guides/graphql-fragment` moves from `Guides → Artifact & Transform`; remove it there.
- `topics/file-object` moves from `Topics → File Storage`; remove it there.

**Redirects needed:**
- None.

---

### PR 6 — IPAM

**Sidebar changes:**

```
Features
  └── IPAM
        └── topics/ipam
```

- Remove from `Topics → Core Concepts → IPAM`.
- No rename of the page itself — only the sidebar section label changes from "IPAM & Resource Management" to "IPAM".

**Redirects needed:**
- None.

---

### PR 7 — Transforms & Artifacts

**Sidebar changes:**

```
Features
  └── Transforms & Artifacts
        ├── topics/transformation
        ├── guides/jinja2-transform
        ├── guides/python-transform
        ├── topics/artifact
        ├── guides/artifact
        ├── guides/artifact-content-composition
        ├── topics/object-storage             (moved from Topics → File Storage)
        ├── guides/object-storage
        ├── ref: topics/developer-guide       (cross-link, canonical home: Operate & Extend)
        ├── ref: topics/resources-testing-framework  (cross-link)
```

- Remove `topics/object-storage` from `Topics → File Storage`; remove it there.
- Remove `guides/graphql-fragment` — already moved in PR 5.
- Add `type: 'ref'` sidebar nodes pointing to Developer Guide and Testing Framework. Their canonical location is set in the Operate & Extend PR.
- After this PR, `Topics → File Storage` is empty and must be removed from `sidebars.ts`.

**Redirects needed:**
- None.

---

### PR 8 — Generators

**Sidebar changes:**

```
Features
  └── Generators
        ├── topics/generator
        ├── guides/generator
        ├── guides/chaining-generators
        ├── topics/modular-generators
        ├── guides/modular-generator-best-practices
        ├── ref: topics/developer-guide       (cross-link)
        ├── ref: topics/resources-testing-framework  (cross-link)
```

- Remove from `Topics → Core Concepts → Generators` and `Guides → Generators`.

**Redirects needed:**
- None.

---

### PR 9 — Git Integration

**Sidebar changes:**

```
Features
  └── Git Integration
        ├── topics/repository
        ├── guides/repository               (moved from Guides → Installation & Setup)
        ├── topics/infrahub-yml
        ├── topics/branch-synchronization
```

- Remove `guides/repository` from `Guides → Installation & Setup`.
- Remove from `Topics → Core Concepts → Git Integration`.

**Redirects needed:**
- None.

---

### PR 10 — Events & Integrations

**Sidebar changes:**

```
Features
  └── Events & Integrations
        ├── topics/events
        ├── topics/event-actions
        ├── guides/events-rules-actions
        ├── topics/webhooks
        ├── guides/webhooks
        ├── topics/activity-log
        ├── topics/log-forwarding
        ├── guides/log-forwarding
```

- Remove from `Topics → Platform Capabilities → Event Management & Logging` and `Guides → Integration & Events`.

**Redirects needed:**
- None.

---

### PR 11 — User Management & Security

**Sidebar changes:**

```
Features
  └── User Management & Security
        ├── topics/authentication
        ├── guides/sso
        ├── topics/permissions-roles
        ├── guides/accounts-permissions
        ├── guides/managing-api-tokens
        ├── guides/menu                     (moved from Guides → Schema & Data Modeling)
```

- Remove `guides/menu` from `Guides → Schema & Data Modeling`.
- Remove from `Topics → Platform Capabilities → User Management & Authentication`.
- After this PR, if `Topics → Platform Capabilities` is empty, remove it from `sidebars.ts`.

**Redirects needed:**
- None.

---

### PR 12 — Operate & Extend

**Goal:** Replace the current `Guides → Installation & Setup` and remaining scattered operational topics with a structured `Operate & Extend` section.

**Sidebar changes:**

```
Operate & Extend
  ├── Deploying & Managing Infrahub
  │     ├── guides/installation
  │     ├── guides/production-deployment
  │     ├── topics/hardware-requirements
  │     ├── reference/configuration         (ref: surfaced from Reference)
  │     ├── guides/configuration-changes
  │     ├── topics/database-backup
  │     ├── guides/database-backup
  │     ├── guides/upgrade
  │     ├── topics/tasks
  │     ├── ref: reference/task-worker      (ref: surfaced from Reference)
  │     └── guides/telemetry
  └── Development Resources
        ├── topics/developer-guide          (canonical home)
        ├── topics/local-demo-environment
        └── topics/resources-testing-framework
```

- Remove all these pages from their old locations in `Guides → Installation & Setup`, `Topics → Platform Capabilities → System Administration`, `Topics → Development Resources`, and `Topics → Platform Capabilities → Event Management & Logging` (tasks).
- `reference/configuration` and `reference/task-worker` appear in both `Operate & Extend` (via `type: 'ref'`) and remain in `Reference` as their canonical locations.
- After this PR, `Guides → Installation & Setup`, `Topics → Core Concepts`, and `Topics → Platform Capabilities` categories should be empty (all pages migrated across PRs 3–12) and must be removed from `sidebars.ts`.
- The old `Topics` and `Guides` top-level categories must be removed once all items are accounted for.

**Redirects needed:**
- None.

---

### PR 13 — Reference Reorganization

**Goal:** Reorganize the existing `Reference` section into 7 named subgroups and move `topics/schema-attr-kind-number-pool` into Schema Specification.

**Sidebar changes:**

```
Reference
  ├── API
  │     ├── reference/api-server
  │     └── reference/message-bus-events
  ├── CLI
  │     ├── reference/infrahub-cli/infrahub-db
  │     ├── reference/infrahub-cli/infrahub-server
  │     ├── reference/infrahub-cli/infrahub-dev
  │     └── reference/infrahub-cli/infrahub-upgrade
  ├── Configuration Files
  │     ├── reference/configuration
  │     ├── reference/dotinfrahub
  │     ├── reference/menu
  │     └── reference/infrahub-tests
  ├── Schema Specification
  │     ├── reference/schema/node
  │     ├── reference/schema/node-extension
  │     ├── reference/schema/attribute
  │     ├── reference/schema/groups
  │     ├── reference/schema/relationship
  │     ├── reference/schema/generic
  │     ├── reference/schema/validator-migration
  │     ├── topics/schema-attr-kind-number-pool   (moved from Topics → Schema)
  │     └── reference/schema-validation
  ├── Events
  │     └── reference/infrahub-events
  ├── Permissions
  │     └── reference/permissions
  └── Authentication
        └── reference/sso
```

- Remove `topics/schema-attr-kind-number-pool` from Topics (already handled in PR 3 removal); place it here under Schema Specification.

**Redirects needed:**
- `topics/schema-attr-kind-number-pool` → `reference/schema/number-pool` if the file is physically moved; otherwise the sidebar ref is enough and no redirect is needed.

---

### PR 14 — Redirects & Final Cleanup

**Goal:** Ensure no existing bookmarked or inbound-linked URL breaks after the reorganization.

**Scope:**
- Audit every page that changed sidebar position but kept its file path — confirm the URL is unchanged (most pages in this reorganization are sidebar-only moves and need no redirects).
- For any page whose file was physically relocated (only `topics/schema-attr-kind-number-pool` if moved), add a Docusaurus `redirects` plugin entry in `docusaurus.config.ts`.
- Run `uv run invoke docs.build` and confirm zero broken links.
- Run a full crawl of the built site to catch any broken anchor references.

**Redirect entry format (`docusaurus.config.ts`):**

```js
redirects: [
  {
    from: '/topics/schema-attr-kind-number-pool',
    to: '/reference/schema/number-pool',
  },
  // add entries for any other physically moved files
],
```

---

## Definition of Done

### Per-section PR
- [ ] `sidebars.ts` updated — pages appear in the correct capability cluster in the rendered nav.
- [ ] Old sidebar nodes for migrated pages removed; no orphaned entries.
- [ ] `uv run invoke docs.build` passes with zero errors and zero broken links.
- [ ] No `.mdx` content changes (structure-only phase).
- [ ] Human review approved.
- [ ] Merged into `docs/doc-reorg`.

### Feature branch (`docs/doc-reorg`) ready to merge
- [ ] All 14 section PRs merged.
- [ ] `Topics` and `Guides` top-level categories removed from `sidebars.ts` (all pages migrated or cross-linked).
- [ ] Redirect pass PR merged.
- [ ] Full site build clean.
- [ ] FAQ accessible under Get Started.
- [ ] No duplicate sidebar entries.

### Release
- [ ] `docs/doc-reorg` merged into `stable`.
- [ ] New documentation version cut from `stable`.

## What This Phase Does Not Include

- Content rewrites or new content.
- Groups consolidation (flagged as Phase 2 — requires content merging, not just nav moves).
- New external links (Python SDK ↗, Schema Library ↗, etc.) — add after the nav is stable.
- Academy course additions or tutorial authoring.
- Any changes to `docs/docs/development/` (Contributing section) beyond confirming the Local Demo Environment cross-link exists.
