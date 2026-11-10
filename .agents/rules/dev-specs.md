---
paths:
  - "dev/specs/**"
---

# Feature specs in dev/specs

Applies to the spec folders under `dev/specs/`. A spec folder records what a feature does and how it was planned and reviewed; it is read after the PR merges by people who were not in the session.

## Which files to commit

- Commit the spec-kit documents: `spec.md`, `plan.md`, `research.md`, `data-model.md`, `quickstart.md`, `tasks.md`, `contracts/`, `checklists/`, the critiques (`critique.md` or `critiques/`) and the implement report.
- Do not commit pipeline scratch: synthesis files (`plan-synthesis.md`, `review-synthesis.md`), rework contracts (`rework-contract*.md`), research briefs, PR notes and audit worksheets (`*.checks.md`). They record an agent's intermediate steps, not decisions, and a later reader cannot tell them from the spec. Move PR notes into the PR description before deleting them.
- Do not commit screenshots, runnable tools or PR drafts to a spec folder: it holds design documents only. Put tooling in `utilities/`.

## Content

- Do not write absolute machine paths (`/Users/...`, `/home/...`, `/tmp/...`, `/private/...`). Use paths relative to the repository root: a machine path resolves on one laptop only.
- When a change moves or renames code that a spec file names, search the whole spec folder for the old paths and symbols (`grep -rn '<old>' dev/specs/<feature>/`) and update every file that repeats them in the same commit. A spec that names files that no longer exist sends the next reader to the wrong place.

## Not violations

- An old path in a dated review record (a critique or the implement report): append an erratum footer instead of editing the body.

Full reference: `dev/guidelines/documentation.md` ("For Internal Docs" and "Don't"); the spec-kit line in the root `AGENTS.md` "Boundaries".
