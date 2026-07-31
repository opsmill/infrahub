---
description: Extract knowledge, guidelines, and ADRs from one or more completed spec
  directories into the project documentation system.
---


<!-- Extension: opsmill -->
<!-- Config: .specify/extensions/opsmill/ -->
## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Outline

Goal: Analyze one or more completed spec directories and extract durable knowledge into the project's documentation system (`dev/knowledge/`, `dev/guidelines/`, `dev/adr/`), then mark each spec as extracted.

This command accepts multiple specs as input (space-separated) and processes them sequentially. It operationalizes the documentation lifecycle: `specs/ → knowledge/ or guidelines/` (see `dev/guidelines/markdown.md`).

## Phase 0: Setup & Validation

<thinking>
First, resolve all spec directories from the user's arguments and validate each one contains the expected artifacts.
</thinking>

1. **Parse arguments** — split `$ARGUMENTS` into individual spec identifiers (space-separated). If `$ARGUMENTS` is empty, list available spec directories and ask the user to pick one or more.

2. **Resolve each spec directory**:
   - For each identifier in the arguments:
     - If it matches `specs/NNN-*` or `NNN-*`, resolve to `REPO_ROOT/specs/NNN-*`
     - If it is a bare name like `graphql-name-lookup`, search `specs/` for a matching directory
     - If no match found for an identifier, report it and continue resolving the rest
   - If **no** identifiers could be resolved, list available spec directories and ask the user to pick

3. **Validate each resolved spec**:
   - `spec.md` MUST exist — skip that spec with an error if missing
   - `research.md` SHOULD exist — warn if missing ("No ADRs can be extracted without research.md") but continue

4. **Check extraction status** for each spec:
   - If `EXTRACTED.md` exists in the spec directory, warn the user that this spec was previously extracted
   - Also check if the spec already lives under `specs/archive/` — if so, it was previously extracted and archived
   - Ask for confirmation before re-extracting — default is abort
   - The user can choose to skip individual specs from the batch

5. **Summarize resolved specs** — before proceeding, print the list of specs that will be processed:
   ```
   Processing N spec(s):
   1. specs/<spec-name-1>
   2. specs/<spec-name-2>
   ...
   ```

6. **Load existing documentation index** (once, shared across all specs):
   - List all files in `dev/knowledge/` (recursively)
   - List all files in `dev/guidelines/` (recursively)
   - List all files in `dev/adr/` to determine the next ADR number
   - Read the first 20 lines of each knowledge and guidelines file to build a topic index (title + overview section)

7. **Load spec artifacts** — for each spec, read all available files from its directory:
   - `research.md` (primary source for ADRs)
   - `spec.md` (context, scope decisions)
   - `data-model.md` (schema changes, new methods — if exists)
   - All files in `contracts/` (API changes — if exists)
   - `plan.md` (architectural context — if exists)

## Phase 1: Analysis & Classification

<thinking>
For each spec, I need to parse each source and classify content into three buckets: ADR, Knowledge, Guideline. I should also identify content to skip with a clear reason. I'll process specs sequentially and tag each finding with its source spec.
</thinking>

Repeat the following steps for **each resolved spec directory**. Tag every finding with the source spec name so the extraction plan in Phase 2 groups items by spec.

### Step 1: Extract ADR candidates from research.md

Parse each `## R#` section in `research.md`. For each entry:

1. Extract: Decision, Rationale, Alternatives considered, Implementation pattern
2. Determine if it is ADR-worthy using this heuristic:
   - **ADR-worthy**: Affects system structure, API contracts, data models, error handling strategy, or establishes a pattern used across multiple components
   - **Not ADR-worthy**: One-off implementation detail with no broader implications (e.g., a local variable naming choice, a single method signature)
3. Draft an ADR title (concise, decision-focused — e.g., "Dual identifier resolution via service-layer helpers")

Also scan `spec.md` for scope decisions or trade-offs in the Clarifications or Assumptions sections that represent architectural choices worth recording.

### Step 2: Extract knowledge candidates

Scan for content that describes **how the system works after the feature**:

| Source | What to look for | Target file |
|--------|-----------------|-------------|
| `data-model.md` | New entities, fields, relationships, constraints | `dev/knowledge/backend/data-models.md` |
| `contracts/` | New or changed GraphQL queries, mutations, types | `dev/knowledge/backend/api.md` |
| `research.md` | New service patterns, architectural patterns | `dev/knowledge/backend/services.md` or relevant file |
| `spec.md` | New concepts or domain terminology | `dev/knowledge/backend/overview.md` or relevant file |

For each finding, map it to a specific existing knowledge file and section. If no existing file fits, propose a new file with a name following `kebab-case.md` convention.

### Step 3: Extract guideline candidates

Scan `research.md` for implementation patterns that establish **repeatable, prescriptive conventions** for future code:

- New parameter patterns → `dev/guidelines/backend/python.md` or `dev/guidelines/cyclopts.md`
- New error handling conventions → `dev/guidelines/backend/python.md`
- New API design conventions → `dev/guidelines/backend/graphql.md` (create if needed)
- New testing patterns → relevant guidelines file

Only extract patterns that are **prescriptive** (should be followed in future code). Do NOT extract patterns that are merely **descriptive** of how this specific feature works — those belong in knowledge.

### Step 4: Identify skipped content

For each piece of spec content not classified above, note it with a reason:
- Execution artifacts (`plan.md`, `quickstart.md`) — no durable knowledge
- Implementation details already captured in code — no need to duplicate
- One-off decisions with no broader applicability

## Phase 2: Interactive Review

Present findings in a structured extraction plan. When processing multiple specs, group the plan by spec. Use a **global numbering scheme** across all specs so that item numbers are unique (e.g., spec 1 items are 1–4, spec 2 items are 5–8).

Use this format:

```markdown
## Extraction Plan

### specs/<spec-name-1>

#### ADRs to Create (<count>)

| # | Source | Title | Target File |
|---|--------|-------|-------------|
| 1 | R1 | <title> | dev/adr/nnnn-<slug>.md |
| 2 | R2 | <title> | dev/adr/nnnn-<slug>.md |

#### Knowledge Updates (<count>)

| # | Target File | Section | Change | Summary |
|---|-------------|---------|--------|---------|
| 3 | dev/knowledge/backend/api.md | Queries | UPDATE | <what changes> |

#### Guidelines Updates (<count>)

| # | Target File | Section | Change | Summary |
|---|-------------|---------|--------|---------|
| 4 | dev/guidelines/backend/python.md | Error Handling | UPDATE | <what changes> |

#### Skipped (with reasons)

| Source | Reason |
|--------|--------|
| plan.md | Execution artifact — no durable knowledge |

---

### specs/<spec-name-2>

#### ADRs to Create (<count>)

| # | Source | Title | Target File |
|---|--------|-------|-------------|
| 5 | R1 | <title> | dev/adr/nnnn-<slug>.md |

...
```

When processing a single spec, omit the per-spec grouping headers and use the simpler flat format (same as the multi-spec table structure but without the `### specs/<name>` wrapper).

After presenting, tell the user:

> **Actions:**
> - `approve all` — proceed with all extractions across all specs
> - `approve spec <name>` — approve all items for a specific spec
> - `approve adrs` / `approve knowledge` / `approve guidelines` — approve by category (across all specs)
> - `skip N` — skip a specific numbered item
> - `edit N` — modify a specific item before writing
> - `group N,M` — merge multiple ADR items into a single ADR

Wait for user response before proceeding. Do NOT write any files until the user approves.

## Phase 3: Write Extractions

For each approved item across all specs, write the content. ADR numbering is sequential across all specs (i.e., if spec 1 creates `0005` and `0006`, spec 2 starts at `0007`).

### ADRs

Create new files in `dev/adr/` using this format:

```markdown
# N. <Title>

**Status**: Accepted
**Date**: <today's date YYYY-MM-DD>
**Source**: specs/archive/<spec-name>/research.md (R#)

## Context

<What is the issue that motivates this decision? Derive from the feature context in spec.md and the specific problem the R# entry addresses.>

## Decision

<What was decided. Taken from the Decision field of the R# entry.>

## Consequences

<What becomes easier or harder as a result. Synthesize from the Rationale and any implementation notes.>

## Alternatives Considered

<What other options were evaluated and why they were rejected. Taken from the Alternatives considered field.>
```

**Numbering**: Read existing files in `dev/adr/` to find the highest existing ADR number. Start new ADRs at the next sequential number. Zero-pad the **filename** sequence to **4 digits** (e.g., `0001`, `0012`); the H1 heading uses the un-padded number (e.g., `# 1.`, `# 12.`).

**File naming**: canonical MADR `nnnn-kebab-case-short-title.md` — 4-digit zero-padded sequence, lowercase kebab title, **no** `adr-`/`ADR-` prefix (e.g., `0001-schema-changes-without-migrations.md`).

### Knowledge updates

For each knowledge update:
1. Read the full target file
2. Find the appropriate section (match by heading)
3. Add or update content within that section
4. If the section does not exist, create it in a logical position
5. Add a source marker: `<!-- Extracted from specs/<spec-name> on YYYY-MM-DD -->`

### Guidelines updates

Same approach as knowledge updates:
1. Read the full target file (or create a new one if needed)
2. Find the appropriate section
3. Add the prescriptive pattern with code examples where relevant
4. Add a source marker: `<!-- Extracted from specs/<spec-name> on YYYY-MM-DD -->`

If creating a new guidelines file, follow the standard structure:
```markdown
# <Topic> Guidelines

## Overview

<Brief description of what this document covers.>

## <Sections...>
```

## Phase 4: Cleanup & Report

Perform the following steps for **each spec** that had approved extractions.

### 1. Create extraction record

Write `EXTRACTED.md` in each spec directory:

```markdown
# Extraction Record

**Extracted on**: <YYYY-MM-DD>
**Extracted by**: speckit.opsmill.extract

## ADRs Created

- <path to ADR file> (from R#)
- ...

## Knowledge Updated

- <path to knowledge file> (<section name>)
- ...

## Guidelines Updated

- <path to guidelines file> (<section name>)
- ...

## Archive

Spec directory moved to `specs/archive/<spec-name>/` as a historical record.
```

### 2. Update spec status and archive

For each spec:
1. In `spec.md`, update or add the status field to: `**Status**: Extracted`
2. Move the entire spec directory into `specs/archive/`:
   ```bash
   mkdir -p specs/archive
   mv specs/<spec-name> specs/archive/<spec-name>
   ```
   This makes it immediately clear which specs have been processed and which are still active.

### 3. Update dev/README.md

After **all** specs have been processed, update `dev/README.md` once with all new files:
- If any **new** files were created in `dev/knowledge/`, `dev/guidelines/`, or `dev/adr/`:
  - Read `dev/README.md`
  - Add new entries to the appropriate section (Current Guidelines, Current Knowledge, or a new Current ADRs section)
  - Follow the existing link format: `- [filename.md](path/to/filename.md) - Brief description`
- If `dev/adr/` now has content and there is no "Current ADRs" section in the README, create one following the pattern of the existing sections.

### 4. Report

Print a combined summary covering all processed specs:

```markdown
## Extraction Complete

**Date**: YYYY-MM-DD
**Specs processed**: N

### Per-Spec Summary

| Spec | ADRs | Knowledge | Guidelines | Status |
|------|------|-----------|------------|--------|
| specs/<spec-name-1> | N | N | N | archived |
| specs/<spec-name-2> | N | N | N | archived |

### Totals
- N ADR(s) created in dev/adr/
- N knowledge file(s) updated
- N guideline file(s) updated

### Archived
- specs/<spec-name-1> → specs/archive/<spec-name-1>
- specs/<spec-name-2> → specs/archive/<spec-name-2>

### Files Created/Modified
- <list each file path>

### Next Steps
- Review the created ADRs for accuracy
- Verify knowledge and guideline updates read well in context
```


## Behavior Rules

- **Never write files without user approval** in Phase 2
- If analysis finds nothing to extract (empty across all categories), report cleanly: "No extractable content found in this spec." and skip the review phase
- If a knowledge file section already contains similar content, flag it for user review rather than duplicating
- Do not reformat or restructure existing content in knowledge/guidelines files beyond the specific additions
- Always create `specs/archive/` before moving if it does not exist
- ADR `Source` paths must reference the archive location (`specs/archive/<spec-name>/`) since the spec will be moved there
- For single quotes in bash args, use escape syntax: e.g. `'I'\''m Groot'` (or double-quote if possible: `"I'm Groot"`)