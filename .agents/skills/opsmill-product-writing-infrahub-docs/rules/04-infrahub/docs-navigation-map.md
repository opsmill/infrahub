# Docs navigation map (Infrahub)

## Contents

- [How to use this file when writing an outline](#how-to-use-this-file-when-writing-an-outline)
- [docs.infrahub.app — the umbrella](#docsinfrahubapp--the-umbrella)
- [Infrahub main repo — top-level sections](#infrahub-main-repo--top-level-sections)
- [Diátaxis quadrants × where they land](#diátaxis-quadrants--where-they-land)
- [When content could fit in multiple sections](#when-content-could-fit-in-multiple-sections)
- [Cross-repo placement](#cross-repo-placement)
- [What this map is NOT](#what-this-map-is-not)

The map of where docs content lives on `docs.infrahub.app`. Use this file when deciding **where new content belongs** — at Step 3 (outline) when no recommendations doc exists, at Step 2.5 (spec review) when validating a doc against this map, and at Step 0.5 (detect repo) when content might need to land in more than one repo.

> **Eventual home:** this file will move into the Infrahub repo (likely `docs/dev/docs-navigation-map.md` or similar) once the structure has stabilized. For now it lives with the skill so updates ship with the workflow.

## How to use this file when writing an outline

1. **Identify what the content describes** — a feature, a workflow, a configuration option, a reference table, a tutorial scenario.
2. **Find the section it fits in** — use the sections table below. If it fits in more than one, see "When content could fit in multiple sections" at the bottom.
3. **Pick the Diátaxis quadrant** — concept/orientation, how-to (task), tutorial (scenario), or reference. The quadrant determines the structural pattern via [decision-rules](../03-patterns/decision-rules.md).
4. **Check cross-repo overlap** — if the content involves Infrahub Sync, Python SDK, Ansible, Nornir, infrahubctl, or MCP, see "Cross-repo placement" at the bottom.

## docs.infrahub.app — the umbrella

The Infrahub main docs site links out to satellite sites for adjacent repos. New content goes in **one canonical site** with cross-links from the others.

| Site | Repo | URL | Owns |
|---|---|---|---|
| Infrahub | `opsmill/infrahub` | `docs.infrahub.app` | The platform — schema, branches, generators, transformations, deployment, reference |
| Infrahub Sync | `opsmill/infrahub-sync` | `docs.infrahub.app/sync` | The sync engine — adapters, mapping rules, sync runs |
| Python SDK | `opsmill/infrahub-sdk-python` | `docs.infrahub.app/python-sdk` | Python client library — API surface, examples, type reference |
| Infrahubctl | `opsmill/infrahubctl` | `docs.infrahub.app/infrahubctl` | The CLI |
| Ansible | `opsmill/infrahub-ansible` | `docs.infrahub.app/ansible` | Ansible modules and roles |
| Nornir | `opsmill/infrahub-nornir` | `docs.infrahub.app/nornir` | Nornir inventory plugin |
| MCP Server | `opsmill/infrahub-mcp` | `docs.infrahub.app/mcp` | MCP integration |

The main Infrahub sidebar links out to these from two places:

- **Design & Integrate > Integrations** — Ansible, Nornir, Infrahub Sync
- **Development Resources > APIs & interfaces** — Python SDK, infrahubctl, MCP Server

If new content describes one of those satellites, **the canonical page lives in the satellite repo**, not in main Infrahub. Main Infrahub gets a one-line pointer at most.

## Infrahub main repo — top-level sections

In sidebar order, with what each section is for.

### Get started

First-touch reading for someone new to Infrahub. **Orientation, not depth.** No how-to content beyond the Quickstart.

- **Introduction** — What is Infrahub, Key Concepts, Architecture, Community vs Enterprise. Concept pages. Each is a single page; no hub+spokes.
- **Getting Started** — Quickstart, Explore Infrahub, Next Steps. Tutorial-shaped but lightweight (≤ 30 minutes of reader time).

**Goes here:** introductory framings, first-time-user content, conceptual overviews of the platform as a whole.
**Does NOT go here:** feature-specific how-tos (those go in their feature section), deep concepts (those go in the feature's `overview.mdx`), deployment content (that's its own section).

### Learn

Academy tutorials. **Scenario-shaped only** — the [tutorial-shape-test](../01-principles/tutorial-shape-test.md) applies. Each tutorial teaches a coherent end-to-end scenario someone would actually want to learn (e.g. "Build a check", "Onboard a new team", "Model a service").

**Goes here:** scenario-shaped tutorials. End-to-end, one running example, narrative arc, "What you learned" closer.
**Does NOT go here:** feature-by-feature walkthroughs with sequence numbers stuck on them (that's a feature-oriented tutorial; drop it per the shape test).

### Schema & Data

The data modeling section. Covers how to model, what primitives exist, and the higher-level constructs built on top.

| Sub-section | Purpose |
|---|---|
| About Schema | Concept pages — nodes, attributes, relationships, generics, hierarchy, branch awareness, extensions |
| Schema operations | How-to — create and load schema, schema migration |
| Advanced schema features | Computed attributes, Number pools, File objects |
| Display & presentation | Field visibility, Display labels, Order weight, Menu customization |
| Objects | Convert object kind, Metadata & lineage, Load data in bulk |
| IPAM | The IPAM primitive — own hub+spokes |
| Resource Manager | Resource allocation — own hub+spokes |
| Groups | Object grouping — own hub+spokes |
| Profiles | Default attribute values — own hub+spokes |
| Object Templates | Reusable object definitions — own hub+spokes |

**Goes here:** any data model concept, schema operation, or primitive built on the schema.
**Does NOT go here:** how data flows through Infrahub (that's Branches & Change Control or Design & Integrate depending on the flow), how to query data (that's Development Resources > APIs & interfaces), the Reference for schema attribute kinds (that's Reference > Schema Specification).

### Branches & Change Control

The version-control story. How changes are proposed, reviewed, validated, and merged.

| Sub-section | Purpose |
|---|---|
| Immutable History | Concept — what's tracked and how |
| Branches | The branching model — own hub+spokes |
| Proposed Changes | The PC workflow — own hub+spokes |
| Checks & Validation | What runs on a PC |
| Testing Framework | How to write tests |
| Change Approval Policy | Who can approve what |
| Git Integration | Connecting external Git repos — own hub+spokes |

**Goes here:** anything about branching, proposing changes, validating changes, approving changes, or Git integration.
**Does NOT go here:** schema migration (that's Schema & Data > Schema operations even though it interacts with branches), CI/CD-level integration (that's Design & Integrate).

### Design & Integrate

The automation surface. How Infrahub data turns into outputs that drive other systems.

| Sub-section | Purpose |
|---|---|
| Generators | Generate Infrahub objects from rules — own hub+spokes |
| Transformations | Transform data into rendered output (Jinja2, Python) — own hub+spokes |
| Artifacts | Persisted rendered output — own hub+spokes |
| Artifact & File Storage | Storage backends for artifacts and files — own hub+spokes |
| Events | Event system, rules, actions — own hub+spokes |
| Webhooks | HTTP push notifications — own hub+spokes |
| Integrations | External links to satellite docs (Ansible, Nornir, Infrahub Sync) |

**Goes here:** anything about turning data in Infrahub into outputs or actions.
**Does NOT go here:** the data itself (that's Schema & Data), the change workflow that triggers transformations (that's Branches & Change Control), references for events (Reference > Events).

### Deployment & Management

Operational concerns. Installing, running, observing, maintaining, securing.

| Sub-section | Purpose |
|---|---|
| Install & configure | Hardware reqs, Installation (community/enterprise), Production deployment, Configure Infrahub |
| Run & observe | Tasks, Telemetry, Activity log, Log forwarding |
| Maintain & upgrade | Database backup, Upgrade (community/enterprise/observability) |
| User Management & Security | Authentication, SSO, Permissions & roles, API tokens |

**Goes here:** anything an operator does to keep Infrahub running.
**Does NOT go here:** developer-facing API content (that's Development Resources), data modeling (that's Schema & Data).

### Development Resources

Content for developers building against Infrahub — using the APIs, the SDK, testing.

| Sub-section | Purpose |
|---|---|
| Developer Guide | High-level developer orientation |
| Testcontainers | Integration testing |
| APIs & interfaces > GraphQL | Queries and mutations, stored queries, single-target queries, working with groups |
| APIs & interfaces > Python SDK ↗ | External link |
| APIs & interfaces > Infrahubctl CLI ↗ | External link |
| APIs & interfaces > MCP Server ↗ | External link |

**Goes here:** GraphQL usage, testing patterns, anything a developer using the API needs.
**Does NOT go here:** Python SDK content (lives in its own repo), CLI content (lives in its own repo).

### Reference

Look-up material. Not learning material. Terse, complete, accurate.

| Sub-section | Purpose |
|---|---|
| Schema Specification | Node, Node extension, Attribute, Relationship, Generic, Groups, Validator/Migration, Schema validation |
| CLI | infrahub-db, infrahub-server, infrahub-dev, infrahub-upgrade |
| Configuration Files | Infrahub Configuration, Repository Config, Menu Configuration, Tests Configuration |
| Events | Account, Artifact, Branch, Commit, Group, Node, Proposed change, Schema, Validator |
| Permissions | The permissions reference |
| Authentication | SSO reference |
| Message Bus Events | One page |

**Goes here:** attribute tables, configuration option lists, event payload schemas, anything someone looks up to confirm a specific detail.
**Does NOT go here:** "how to" content (that goes in the relevant feature section), concepts (feature `overview.mdx` or its own concept page).

### Project

Project metadata. Contributors and consumers checking versions.

| Sub-section | Purpose |
|---|---|
| Contributing | Git practices, editor setup, changelog, backend, frontend, docs, style guide |
| Release Notes | Per-version release notes + Deprecation Guides |

**Goes here:** how to contribute, what changed in each release.
**Does NOT go here:** anything user-facing.

## Diátaxis quadrants × where they land

For any feature, content of each quadrant typically lands as follows:

| Quadrant | Where it lands |
|---|---|
| **Concept / Orientation** | The feature's `overview.mdx` (the hub page) inside its own folder, e.g. `docs/docs/generators/overview.mdx` |
| **How-to (task)** | A spoke page inside the feature's folder, e.g. `docs/docs/generators/build.mdx`. Use imperative title ("Build a generator") |
| **Tutorial (scenario)** | An Academy tutorial in `docs/docs/academy/tutorials/<slug>.mdx`. Must pass the [tutorial-shape-test](../01-principles/tutorial-shape-test.md) |
| **Reference** | A `docs/docs/reference/<area>/<page>.mdx` page in the Reference section |

The same feature usually appears in **all four quadrants**, in different sections. Don't put reference content on the feature's hub page; don't put how-tos in the Reference section.

## When content could fit in multiple sections

Sometimes a feature spans two top-level sections. Rules of thumb:

- **Data primitives go in Schema & Data, even if they're operationally relevant.** Example: Number pools are a schema feature, not a resource-manager feature, even though Resource Manager uses them.
- **Operational concerns (auth, telemetry, upgrades) go in Deployment & Management, even if they involve schema concepts.** Example: SSO has schema implications (Account objects) but the SSO docs go in Deployment & Management; the Account object schema goes in Reference.
- **APIs go in Development Resources.** Example: GraphQL fragments are an API thing, not a schema thing.
- **The canonical page lives in one section; the other sections get cross-links, not duplicated content.** A how-to that mentions branches should link to the Branches & Change Control hub, not re-explain branches.

When unsure, surface the decision to the user per [gate-discipline](../01-principles/gate-discipline.md).

## Cross-repo placement

When new content describes behavior that spans Infrahub main and a satellite (Sync, SDK, Ansible, Nornir, infrahubctl, MCP), decide where the **canonical** content lives:

| Content shape | Canonical home |
|---|---|
| How Infrahub Sync works (concepts, configuration, adapters) | Infrahub Sync repo (`docs.infrahub.app/sync`) |
| How the Python SDK works (API methods, types, examples) | Python SDK repo (`docs.infrahub.app/python-sdk`) |
| The Ansible modules / Nornir plugin / infrahubctl CLI / MCP server | The respective satellite repo |
| Infrahub main features the satellite uses | Infrahub main; satellite docs link in |
| The satellite's existence and what it does at a high level | One-line entry in the relevant main-Infrahub Integrations or APIs section, linking to the satellite docs |

**Update both places only when both repos' docs need to change for the same release.** Example: a new GraphQL query that Infrahub Sync depends on — add the query to main Infrahub's GraphQL docs **and** mention it in the Sync adapter docs that consume it. Each repo gets its own PR.

## What this map is NOT

- **Not a substitute for reading the actual sidebar.** Section names and sub-sections drift. When the map disagrees with `docs/sidebars.ts`, the sidebar wins — update this file.
- **Not a list of every page.** Spoke-level pages are listed only when their existence matters for placement decisions. For a full inventory, read `docs/sidebars.ts`.
- **Not opinionated about page content.** This file decides *where*; [voice-and-tone](../01-principles/voice-and-tone.md), [decision-rules](../03-patterns/decision-rules.md), and the pattern files decide *what* and *how*.
