---
name: migrate-feature-page
description: Migrate a single Infrahub docs feature page (Layer 2 capability content like Profiles, Resource Manager, Webhooks) from the legacy topic+guide pair to a single merged page or hub+spokes pattern. Trigger when the user names a specific feature to migrate (e.g. "let's migrate profiles", "start the Resource Manager migration", "do the webhooks page next"). Each migration is its own branch off `demo/groups-diataxis-example`, its own PR back to that branch, scoped to one feature only.
---

# Migrate Feature Page

Used during the Infrahub docs revamp to migrate one feature page (Layer 2 content under a Features sub-category) from a topic + guide pair to a cleaner structure. Each feature gets its own branch and PR for scoped review.

## Reference precedent

The Groups feature was the first migration. Files to reference when in doubt:

- `docs/docs/groups/index.mdx` — hub
- `docs/docs/groups/*.mdx` — spokes
- `docs/docs/academy/tutorials/groups.mdx` — preserved tutorial
- Confluence: [Docs Revamp — Groups Before/After Content Diff](https://opsmill.atlassian.net/wiki/spaces/Product/pages/566755331)

## Inputs the user provides

- **Feature name** (e.g. "Profiles", "Resource Manager", "Webhooks")
- **Optional notes** about this feature

## Inputs the skill derives

- Topic file: `docs/docs/topics/<slug>.mdx`
- Guide file: `docs/docs/guides/<slug>.mdx`
- Sidebar location: usually `Features > <Section>` in `docs/sidebars.ts`
- Inbound links from other docs (via grep)

## Workflow

Use TodoWrite to track. Stop and confirm with the user at every ★ gate.

### Step 1 — Pre-flight

- Verify current branch is `demo/groups-diataxis-example` (the consolidated parent branch). If not, switch.
- Run `git status -s`. Any uncommitted changes? Stop and ask user how to handle them before creating a new branch.
- Create new branch: `docs/migrate-<feature-slug>` (e.g. `docs/migrate-profiles`).
- Confirm the local serve and build work as a baseline.

### Step 2 — Audit existing content ★

Read both files completely:

- `docs/docs/topics/<slug>.mdx`
- `docs/docs/guides/<slug>.mdx`

Produce a compact summary covering:

- **Topic page**: section headings, line count, observations on quality / gaps
- **Guide page**: section headings, line count, **is it tutorial-shaped?** Tutorial-shape signals: Step 1/2/3 headings, single running example used throughout, "Next steps" closer, linear narrative
- **Inconsistencies / gaps** — flag for user review (don't silently fix)
- **Inbound cross-links** — `grep -rln 'topics/<slug>\|guides/<slug>' docs/docs/` (excluding the files themselves and other obvious matches). List which other docs reference them.

★ **Gate**: present the audit to the user. Wait for confirmation before proceeding.

### Step 3 — Pattern decision ★

Recommend a pattern based on the audit. Get user approval before creating files.

**Decision rules:**

| Condition | Pattern |
|---|---|
| Single concept + one workflow, content fits under ~300 lines | **Single-page merge** — topic content as overview at top, guide content rewritten as `## How to X` sections below |
| Multiple distinct tasks (3+ separable workflows) | **Hub + spokes** — short hub explaining the concept; one spoke page per task (Groups precedent) |
| Guide is genuinely tutorial-shaped | **Tutorial extraction** — guide content moves to `academy/tutorials/<slug>.mdx` (preserve original title); topic content becomes the canonical feature page |
| Mix of tutorial + recipes | **Split** — tutorial portion → Academy; recipe portion → feature page (Groups precedent) |

**Default**: single-page merge unless the feature genuinely warrants more complexity.

★ **Gate**: present the recommended pattern with rationale. User approves or chooses different.

### Step 4 — Create new files

Follow the chosen pattern.

**Single-page merge:**

- Edit `docs/docs/topics/<slug>.mdx` (the existing topic file becomes the canonical feature page)
- Topic content stays at the top, light edits OK
- Guide content rewritten below as how-to sections (drop "Step 1/2/3" wording; replace running examples with placeholders like `<group-name>`, `<object-id>`)
- Original guide file `docs/docs/guides/<slug>.mdx`: **leave on disk** during iteration (legacy URL still works); will be deleted in cleanup PR

**Hub + spokes** (Groups / Profiles precedent):

- Hub at `docs/docs/<feature>/index.mdx` — topic content only. **Do NOT add a "Common tasks" or "Deeper concepts" link list** — the spokes already appear in the sidebar when the user is on the hub, so a body link list is redundant clutter. A "Learn by doing" body link to an Academy tutorial is OK because the tutorial lives in a different sidebar section.
- Spokes at `docs/docs/<feature>/<task>.mdx` — one per task. Each spoke should have a brief "Next" or "Related" section at the bottom pointing to adjacent spokes.
- Optional concept spoke at `docs/docs/<feature>/<concept>.mdx` for substantial deep-dive content (e.g. priority and inheritance) when it's a frequently-referenced topic and would otherwise bloat the hub.
- Optional Academy tutorial at `docs/docs/academy/tutorials/<feature>.mdx`

**Tutorial extraction:**

- Move guide to `docs/docs/academy/tutorials/<slug>.mdx`
- Preserve original title (e.g. "How to organize objects with groups" stays the same)
- Reframe as tutorial: add "By the end of this tutorial you will…" preamble; "What you learned" closer
- Topic page may need light edits if it referenced the old guide

### Step 5 — Update sidebar

Modify `docs/sidebars.ts`. Replace the old topic+guide pair entries with the new structure. Use the small color-matched caret (already styled in `custom.css`) for nested categories where used.

### Step 6 — Build + verify

```bash
cd docs && npm run build
```

Fix any broken doc IDs or links. Run `npm run serve` to visually check.

### Step 7 — Add redirects-pending file

Each feature migration drops a YAML file in `docs/redirects-pending/` listing the URL redirects this migration introduces. At end-of-Phase-2 (cleanup PR), all files are aggregated into a single redirects array in `docs/docusaurus.config.ts` via `@docusaurus/plugin-client-redirects`. See `docs/redirects-pending/README.md` for the format.

Create `docs/redirects-pending/<feature-slug>.yml`:

```yaml
feature: <Feature Name>
pr: TBD
description: |
  Brief explanation of what changed and why these redirects exist.
redirects:
  - from: /docs/<old-path>
    to: /docs/<new-path>
```

Common patterns:

- **Hub + spokes (Groups / Profiles precedent)** — both legacy URLs redirect to the new hub:
  - `/docs/topics/<feature>` → `/docs/<feature>/`
  - `/docs/guides/<feature>` → `/docs/<feature>/`
- **Single-page merge** — guide URL redirects to canonical topic:
  - `/docs/guides/<feature>` → `/docs/topics/<feature>`
- **Tutorial extraction only** — guide URL redirects to topic; tutorial URL is new (no redirect needed):
  - `/docs/guides/<feature>` → `/docs/topics/<feature>`

Update `docs/redirects-pending/README.md` "Files in this folder" table to add the new entry.

### Step 8 — Cross-reference scan

- Run `grep -rln '<feature-slug>' docs/docs/` to find inbound references.
- For each, identify whether the page actually mentions / depends on the migrated feature (vs a path coincidence).
- For pages in **other sections** that should reference this feature in CONTENT (not sidebar), add an entry to the Confluence [Open Questions](https://opsmill.atlassian.net/wiki/spaces/Product/pages/567279617) page under "Surface cross-section content via prose." **Do NOT modify those other-section pages in this PR** — out of scope.
- For pages in other sections that have **stale Markdown links** to the legacy paths (will resolve via redirect once cleanup happens, but should be updated to the new paths), add to the Open Questions cleanup checklist with file paths and line numbers.
- For internal cross-links within the feature itself that are now stale, fix them in this PR.

### Step 9 — Generate PR description ★

Draft a slimmed-down summary as the PR body. Template below.

★ **Gate**: present the draft PR description to the user. They approve or edit. **Do not commit until approved.**

#### PR description template

```markdown
## Summary

Migrate the **<Feature>** feature page per the Infrahub docs revamp.
Pattern: <single-page merge / hub + spokes / tutorial extraction / split>.

## Content changes

[Section-by-section list — keep brief.]

- **<Section name>**: <preserved as-is / rewritten as how-to / moved to Academy tutorial / etc.>

## What didn't change

- All factual content preserved; no new claims invented
- Original URLs continue to resolve (legacy `topics/<slug>.mdx` and `guides/<slug>.mdx` remain on disk during iteration; cleanup happens in a separate PR before production merge)

## Out of scope (tracked in Open Questions)

- [Cross-section content references to add elsewhere — links to Confluence Open Questions item]
- [Any structural gaps deferred]

## Verification

- `cd docs && npm run build` succeeds
- Local preview: `npm run serve` → http://localhost:3000

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

### Step 10 — Commit + push + open PR

```bash
git add <files>
git commit -m "docs: migrate <Feature> page per docs revamp"
git push -u origin docs/migrate-<slug>
gh pr create --base demo/groups-diataxis-example --title "docs: migrate <Feature> per docs revamp" --body "<approved description>"
```

### Step 11 — End-of-migration audit ★

**After the user confirms the PR is open and content looks good**, do a separate audit pass.

- Re-read every new / modified file in this PR.
- For each **factual claim**, find a source: existing docs (current topic, guide, reference, schema specs, related feature docs), schema definitions, code comments. If a claim can't be sourced, flag it.
- Verify GraphQL mutations / queries match actual schema. Cross-check against:
  - `docs/docs/reference/schema/<feature>.mdx` if present
  - `docs/docs/topics/schema-attr-kind-*.mdx` for attribute kinds
  - Other feature docs that reference the same primitives
- Verify SDK examples are syntactically plausible. Compare against existing working examples in other feature pages.
- Verify all cross-links resolve to the correct page and section.
- Verify any new diagrams / tables / callouts are factually correct.
- Report findings with specific file paths + line numbers, e.g.:
  - `groups/use-in-automation.mdx:54` — claim about "Generator owns a CoreGeneratorGroup" is incorrect; per `topics/generator.mdx`, the SDK manages the CoreGeneratorGroup automatically.

★ **Gate**: present audit findings to the user. User decides which to fix in this PR vs defer.

## Decision rules — content edits during migration

| Issue type | Action |
|---|---|
| Clear factual error | Fix in this PR |
| Structural gap (missing prereqs, troubleshooting) | Flag to user; ask whether to fix or defer to post-launch |
| Stylistic improvement | Flag to user; default is defer |
| Outdated example | Flag to user; ask |
| Stale terminology / voice inconsistency | Defer (out of scope for this revamp) |

## Confluence updates done as part of each feature migration

- **[Open Questions](https://opsmill.atlassian.net/wiki/spaces/Product/pages/567279617)** — append any new cross-section work needed; append any structural gaps deferred for later

**Do NOT** update the Navigation Map for individual feature migrations during iteration. The Map gets a single end-of-revamp update once Phase 2 is complete.

## What's explicitly NOT done in feature-migration PRs

- URL redirects (handled in cleanup PR before production merge)
- Modifications to other-section pages (cross-section work goes in Open Questions; out of scope)
- Renaming or moving legacy `topics/<slug>.mdx` / `guides/<slug>.mdx` files (left in place so old URLs keep working)
- Sidebar restructure outside the one feature being migrated
- Bulk rewriting / voice-and-tone polishing

## After merge to `demo/groups-diataxis-example`

The feature PR merges into the consolidated parent branch (`demo/groups-diataxis-example`). Subsequent feature migrations branch off the updated parent so they pick up cumulative changes.

## End-of-revamp cleanup (out of scope for this skill)

When all feature migrations land in `demo/groups-diataxis-example` and the team is ready to ship to production:

- Delete legacy `topics/<slug>.mdx` and `guides/<slug>.mdx` files
- Update inbound cross-links in other docs to point at new paths
- Install `@docusaurus/plugin-client-redirects` and add redirect entries
- Single-pass content audit
- Single Navigation Map / Confluence update reflecting final state
