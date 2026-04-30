# AGENTS.md - Documentation

> See [root AGENTS.md](../AGENTS.md) for project-wide commands and guidelines.

## Overview

Infrahub docs follow the [Diataxis framework](https://diataxis.fr/) as a **writing discipline**, not a folder scheme.
The four modes (explanation, how-to, tutorial, reference) define *what a chunk of content is*, not where its file lives.
A single feature section can include an explanatory overview, several how-to pages, and a reference spec — all nested together.

The previous layout mapped modes directly to top-level folders (`topics/`, `guides/`), which forced readers to look in two places for every feature. The new layout groups content by **capability**, keeping explanation and how-to together under one nav node.

## Site Structure

The site has six top-level sections. Each section has a distinct audience intent.

### 1. Get Started

**Audience intent:** "I just heard about Infrahub. What is it, and how do I try it?"

Contains orientation and entry-point content only. Nothing here requires a running instance.

| Subsection | What belongs here |
|---|---|
| **Introduction** | What Infrahub is, key concepts, architecture overview, Community vs Enterprise comparison |
| **Getting Started** | Quickstart, guided exploration, next-steps signpost |
| **FAQ** | Beginner questions ("Do I need it?", "How do I see it in action?") |

**Do not add** feature how-to guides, reference pages, or deep-dive explanations here. If you're unsure, ask: "Would a prospect read this before deciding to try Infrahub?" If no, it belongs elsewhere.

---

### 2. Learn

**Audience intent:** "I want to learn Infrahub by following structured, linear content."

Contains Academy courses and per-feature tutorials. Content here is **learning-oriented and sequential** — readers work through it from top to bottom, often for the first time.

| Subsection | What belongs here |
|---|---|
| **About Academy** | Landing/welcome page for Academy |
| **Getting Started** *(courses)* | Foundational linear walkthroughs (Introduction course, Deploy First Configuration) |
| **Tutorials** *(per-feature)* | Linear walkthroughs for specific features — "teach me by doing" |

**Do not add** scannable how-to recipes here. A tutorial tells a story and assumes a learner; a how-to guide assumes someone who already knows the goal and wants the fastest path to it. Guides belong in **Features**.

---

### 3. Features

**Audience intent:** "I'm using Infrahub. How does capability X work, and how do I do Y with it?"

This is the largest section. Each subsection is a **capability cluster** that groups both explanatory (topic) and task-oriented (how-to) content for that capability together. Readers should not have to leave the section to understand and use a feature.

The section label is open for team discussion (alternatives: *Working with Infrahub*, *Capabilities*, *Platform features*).

#### Capability clusters and what belongs in each

**Schema & Data Modeling**
Everything about defining the data model: schema structure, extensions, display, computed attributes, field ordering, labels, profiles, templates. Both concept pages ("what is a schema extension?") and how-to pages ("how do I import a schema?") live together here.

**Version Control & Branching**
Everything about Infrahub's Git-like change model: how version control works, branching, Proposed Changes, the change-approval workflow (review/approve/merge), and Selective Branch Sync. The change-approval workflow belongs here — not in User Management — because it describes the branching workflow; permissions are a secondary concern on that page.

**Data Management**
The general data layer: GraphQL (including GraphQL Fragments, which are a GraphQL primitive, not an artifact-specific concept), loading data, Resource Manager, Groups, Profiles, Object Templates, Object Conversion, Metadata & Lineage, File Objects, and Checks & Validation. File Objects belong here — they are first-class graph data modeled as nodes, not file storage infrastructure.

**IPAM**
IP address management. Named "IPAM" only (not "IPAM & Resource Management") because Resource Manager is a general data primitive that now lives in Data Management.

**Transforms & Artifacts**
Everything about user-authored data transformations and their output artifacts: Jinja2 and Python Transforms, Artifacts, Artifact Content Composition, Object Storage. Object Storage belongs here — it is the substrate where Artifacts are stored, and the Artifacts ↔ Object Storage relationship is most useful in this context.

**Generators**
Generator Overview, Chaining Generators, Modular Generators, Modular Generator Best Practices. Cross-links to Developer Guide and Testing Framework (canonical home: Development Resources).

**Git Integration**
Repository Management (topic + guide), `infrahub.yml` configuration, Branch Synchronization. The Repository Management guide was previously under Installation & Setup because repos are connected at install time, but the doc is about working with Git repos — it lives with its topic here.

**Events & Integrations**
Events System, Event Actions, Rules & Actions, Webhooks, Activity Log, Log Forwarding. External integration links (Ansible, Nornir, Sync, MCP). Activity Log and Log Forwarding are siblings — they describe the same audit events from two angles (in-app view vs. external SIEM export).

**User Management & Security**
Authentication, SSO, Permissions & Roles, Managing API Tokens, Menu Customization. Menu Customization belongs here because its user intent is "customize what users see in the UI" — an admin/UX concern — even though menus are defined via schema-like config files.

#### Placement decision rule for Features

When adding a new page, ask: "What is a user trying to do when they need this?" Place it under the capability cluster that matches the user's goal, not the internal implementation detail. If the page spans two clusters, place it under the one that owns the primary user intent and cross-link from the other.

---

### 4. Operate & Extend

**Audience intent:** "I'm running Infrahub in production, or I'm building on top of it."

Two subsections with different audiences:

**Deploying & Managing Infrahub** — for operators running instances:
Installation, Production Deployment, Hardware Requirements, Configuration (surfaced from Reference), Configuration Changes, Database Backup, Upgrade, Tasks (the async task system), Task Worker reference, Telemetry. Configuration and Task Worker are surfaced from Reference into this section because an operator deploying Infrahub looks here, not in Reference.

**Development Resources** *(canonical home)* — for developers extending Infrahub:
Developer Guide, Local Demo Environment, Testing Framework. These pages are cross-linked from Transforms & Artifacts, Generators, and Contributing — but the canonical location is here.

**Solutions** — external links to solution blueprints (e.g., AI Datacenter).

---

### 5. Reference

**Audience intent:** "I need to look up a specific parameter, endpoint, flag, or rule."

Reference content is **lookup-oriented, not read linearly**. Pages here have a clear spec shape: parameter tables, syntax rules, enumerated options.

Organized into 7 subgroups:

| Subgroup | What belongs here |
|---|---|
| **API** | API Server, Message Bus Events |
| **CLI** | `infrahub-db`, `infrahub-server`, `infrahub-dev`, `infrahub-upgrade` |
| **Configuration Files** | Infrahub Configuration, Repository Config, Menu Configuration, Tests Configuration |
| **Schema Specification** | Node, Attribute, Relationship, Generic, Extensions, NumberPool, Schema Validation Rules |
| **Events** | Infrahub Events spec |
| **Permissions** | Permission Types & Scopes |
| **Authentication** | SSO Reference |

**NumberPool** belongs in Schema Specification (not in Features > Schema) because the page is a parameter spec — syntax, defaults, rules — designed for lookup, not for narrative reading.

If a page reads like a table of parameters or a list of allowed values, it belongs in Reference. If it explains how something works or walks through a task, it belongs in Features.

---

### 6. Project

**Audience intent:** "I want to contribute to Infrahub or understand its release history."

**Contributing** — same as before, with a cross-link to Local Demo Environment (contributor tooling; canonical home in Development Resources).

**Release Notes** — new releases added at the top. Structure unchanged.

---

## Diataxis in practice

The four modes can coexist on a single page or within a single capability cluster:

| Mode | Shape | Signals |
|---|---|---|
| **Explanation** (Topic) | Narrative prose, "why it exists", conceptual diagrams | Reads like background reading; no specific task to complete |
| **How-to** (Guide) | Short numbered steps, imperative verbs, scannable | User has a goal and wants the fastest path |
| **Tutorial** | Linear walkthrough, "learn by doing", assumes first-time reader | Sequential narrative; goes in **Learn** |
| **Reference** | Parameter tables, syntax specs, enumerated values | Designed to be looked up, not read; goes in **Reference** |

The discipline is: know which mode each chunk of writing is, and write it in that mode. You do not need to split a feature across separate folders to honor Diataxis.

---

## Adding a new page — decision checklist

1. **Is this lookup material?** (parameter table, CLI flag list, API spec) → **Reference**
2. **Is this a linear tutorial for first-time learners?** → **Learn > Tutorials**
3. **Is this orientation content for someone evaluating Infrahub?** → **Get Started**
4. **Is this about running/deploying an instance?** → **Operate & Extend > Deploying & Managing**
5. **Is this developer-extension tooling?** → **Operate & Extend > Development Resources**
6. **Otherwise** → **Features**, under the capability cluster that owns the user's primary goal

If you place a page in a location that is not its natural home (e.g., the same concept is useful in two clusters), use a cross-link (`type: 'ref'`) rather than duplicating the file.

---

## File Structure

- `docs/` – MDX content
  - `guides/` – How-to content (task-oriented); will migrate into capability clusters over time
  - `topics/` – Explanation content; will migrate into capability clusters over time
  - `reference/` – Lookup-oriented specs
  - `tutorials/` – Linear walkthroughs (Academy and per-feature)
  - `media/` – Images and screenshots
  - `development/` – Contributing docs and style guide
- `sidebars.ts` – Navigation configuration (source of truth for the site structure)

> **Note on directory layout:** During the migration, file paths under `docs/` do not need to match the new nav structure perfectly. The sidebar configuration in `sidebars.ts` controls what the user sees. A file at `docs/guides/foo.mdx` can appear under Features > Git Integration in the nav.

## Commands

```bash
uv run invoke docs.lint     # Run all linters (Vale + markdownlint)
uv run invoke docs.build    # Build documentation site
uv run invoke docs.serve    # Serve documentation site
uv run invoke docs.format   # Auto-format markdown files
```

## Target Audience

- **Primary:** Automation engineers, network operators, infrastructure teams
- **Assumed knowledge:** Git, CI/CD, YAML/JSON, infrastructure-as-code
- **Not assumed:** Prior Infrahub experience

## Writing Guidelines

For detailed writing standards see:

- `dev/guides/docs/writing-a-guide.md` — how to write how-to guides
- `dev/guides/docs/writing-a-topic.md` — how to write explanation pages
- `dev/guidelines/documentation.md` — general documentation guidelines
- `dev/guidelines/markdown.md` — markdown formatting standards
- `docs/development/style-guide.mdx` — terminology and voice

### Voice and Tone

- **Active voice**: "Create a branch" (not "A branch can be created")
- **Imperative mood** for guides: "Click **New Branch**"
- **Present tense**: "Infrahub uses branches to isolate changes"
- **Professional but approachable**: Avoid "simple", "easy", or "just"

### Infrahub Terminology

| Term | Capitalize? | Example |
|---|---|---|
| Generator(s) | Yes | "Infrahub **Generators** convert service models into objects." |
| Transformation(s) | Yes | "**Transformations** convert graph data into artifacts." |
| Profile(s) | Yes | "Create **Profiles** for your devices." |
| Resource Manager | Yes (singular) | "Use **Resource Manager** to allocate IPs." |
| artifact(s) | No | "The **artifact** is stored in object storage." |
| transform (verb) | No | "Use this to **transform** data into vendor formats." |

**Never use "transform" or "transforms" as a noun.** Always use "Transformation" or "Transformations".

## Boundaries

### Always Do

- Run `uv run invoke docs.lint` before committing
- Build docs to check for broken links
- Use sentence case for headings
- Include language tags on code blocks
- Define technical terms on first use
- Place new pages using the decision checklist above

### Ask First

- New top-level navigation sections
- Docusaurus configuration changes
- Moving pages between top-level sections

### Never Do

- Use "simple", "easy", or "just"
- Leave broken links
- Commit large unoptimized images
- Skip alt text for images
- Duplicate a page's content — use cross-links (`type: 'ref'`) instead