---
name: migrate-feature-page
description: Migrate Infrahub docs feature pages from the legacy topic+guide pair into a cleaner structure (single merged page, hub+spokes, or tutorial extraction). Supports both single-feature migrations (one feature like Profiles or Webhooks) and section-wide migrations (a whole section like Branches & Change Control with multiple features migrated together) when the team has agreed on a section-wide restructure plan. Trigger when the user names a specific feature or section to migrate (e.g. "let's migrate profiles", "start the Resource Manager migration", "do the entire Branches & Change Control section"). Each migration is its own branch off `demo/groups-diataxis-example`, its own PR back to that branch.
---

# Migrate Feature Page

Used during the Infrahub docs revamp to migrate one feature page (Layer 2 content under a Features sub-category) — or an entire docs section — from a topic + guide pair to a cleaner structure. Each migration gets its own branch and PR for scoped review.

## Reference precedent

The Groups feature was the first single-feature migration. Files to reference when in doubt:

- `docs/docs/groups/index.mdx` — hub
- `docs/docs/groups/*.mdx` — spokes
- `docs/docs/academy/tutorials/groups.mdx` — preserved tutorial
- Confluence: [Docs Revamp — Groups Before/After Content Diff](https://opsmill.atlassian.net/wiki/spaces/Product/pages/566755331)

For section-wide restructures, look for a per-section recommendation page on Confluence (e.g. [Branches & Change Control Recommendations](https://opsmill.atlassian.net/wiki/spaces/Product/pages/572358657)) — these capture the team-approved structure before migration starts.

## Inputs the user provides

- **Feature or section name** (e.g. "Profiles", "Resource Manager", "Webhooks", "Branches & Change Control section")
- **Recommendation doc** (Confluence link) for section-wide migrations — confirms the approved structure
- **Optional notes** about this feature/section

## Inputs the skill derives

- Topic file(s): `docs/docs/topics/<slug>.mdx`
- Guide file(s): `docs/docs/guides/<slug>.mdx`
- Sidebar location: usually `Features > <Section>` in `docs/sidebars.ts`
- Inbound links from other docs (via grep)

## Workflow

Use TodoWrite to track. Stop and confirm with the user at every ★ gate. For section-wide migrations, also see [Recommendations for large or section-wide migrations](#recommendations-for-large-or-section-wide-migrations) at the bottom — apply those on top of the standard workflow.

**Meta-rule: never recommend silently.** When the spec-review (Step 2.5) or implementation surfaces additional changes beyond what the recommendations doc already states — like merging two pages into one, adding a missing spoke, renaming a label, restructuring a sub-category — **present the recommendation to the user with rationale and wait for a decision before implementing.** The recommendations doc is the canonical spec; deviations get explicit approval, not silent application.

### Step 1 — Pre-flight

- Verify current branch is `demo/groups-diataxis-example` (the consolidated parent branch). If not, switch.
- Run `git status -s`. Any uncommitted changes? Stop and ask user how to handle them before creating a new branch.
- Create new branch:
  - **Single-feature migration**: `docs/migrate-<feature-slug>` (e.g. `docs/migrate-profiles`)
  - **Section-wide migration**: `docs/migrate-<section-slug>` (e.g. `docs/migrate-branches-and-change-control`)
- Confirm the local serve and build work as a baseline.

### Step 2 — Audit existing content ★

Read the source files completely:

- `docs/docs/topics/<slug>.mdx`
- `docs/docs/guides/<slug>.mdx`
- For section-wide migrations: read every page that's part of the section, not only one feature

Produce a compact summary covering:

- **Topic page(s)**: section headings, line count, observations on quality / gaps
- **Guide page(s)**: section headings, line count, **is it tutorial-shaped?** Tutorial-shape signals: Step 1/2/3 headings, single running example used throughout, "Next steps" closer, linear narrative
- **Inconsistencies / gaps** — flag for user review (don't silently fix)
- **Inbound cross-links** — `grep -rln 'topics/<slug>\|guides/<slug>' docs/docs/` (excluding the files themselves and other obvious matches). List which other docs reference them.

★ **Gate**: present the audit to the user. Wait for confirmation before proceeding.

### Step 2.5 — Spec review against skill rules ★ (when a recommendations doc exists)

**When the user provides a Confluence recommendations doc** (typical for section-wide migrations), the doc replaces Steps 2 and 3 as the planning artifact. But the doc may have gaps — review it critically against the skill's decision rules before implementing.

Read the doc end-to-end. Then run this checklist against the proposed structure:

- **Topic+guide pairs being treated as separate moves.** A topic file + a guide file describing the same single feature → **single-page-merge candidate** per the decision rules below. Don't preserve the split.
- **Shared name roots that suggest merging.** If multiple files share a name root (e.g. `branch-synchronization` + `selective-branch-sync`) AND describe related procedural work, they're merge candidates. Treat them as one feature unless there's a specific reason to keep them separate.
- **Hub categories without a clickable link.** Every category that becomes a hub in `sidebars.ts` must have `link: { type: 'doc', id: '<feature>/index' }`. Without that, the category caret expands but the label is dead. Confirm the doc specifies an explicit hub for each new category.
- **Tutorial-shaped guides not being extracted.** Run the tutorial-shape check (Step 1/2/3 headings, single running example, narrative arc) on every guide in the spec. If a guide is tutorial-shaped but the doc says "keep here," ask whether to extract or reframe.
- **Missing common spokes.** When converting a feature to hub+spokes, common operations (`create`, `update`, `delete`, `query`, etc.) typically each get a spoke. If the doc lists 3 spokes but obvious operations are missing, flag it.
- **Legacy `(Topic)` / `(Guide)` sidebar labels.** If the new sidebar still has these suffixes, that means the migration is half-done — those labels should disappear when files convert to hub+spokes or single-page merge. Check.
- **Broken cross-link patterns.** When a feature moves into a sub-section (e.g. Git Integration nesting under Branches & Change Control), pages from that sub-section reference each other via paths that may need updating.

**Per the meta-rule**: every finding gets presented to the user with rationale, not silently applied. The user updates the doc, then you implement against the updated spec.

★ **Gate**: present spec-review findings. User decides which to add to the spec, which to leave as-is. Once decisions land, the user (or you, on their behalf) updates the recommendations doc to reflect the final spec. Then proceed to Step 4.

### Step 3 — Pattern decision ★ (when no recommendations doc exists)

When no doc exists (typical for single-feature migrations), recommend a pattern based on the Step 2 audit. Get user approval before creating files.

**Decision rules:**

| Condition | Pattern |
|---|---|
| Single concept + one workflow, content fits under ~300 lines | **Single-page merge** — both files combined into `docs/docs/<feature>/index.mdx` |
| Multiple distinct tasks (3+ separable workflows) | **Hub + spokes** — short hub explaining the concept; one spoke page per task (Groups precedent) |
| Guide is genuinely tutorial-shaped | **Tutorial extraction** — guide content moves to `academy/tutorials/<slug>.mdx` (preserve original title); topic content becomes the canonical feature page |
| Mix of tutorial + recipes | **Split** — tutorial portion → Academy; recipe portion → feature page (Groups precedent) |
| Multiple files sharing a name root + related procedural scope | **Likely single-page merge** even if file count > 2 — they're describing one feature |

**Default**: single-page merge unless the feature genuinely warrants more complexity.

**Tutorial scenario-shape test.** If the chosen pattern preserves an Academy tutorial (Tutorial extraction or Split), apply this check before keeping it: read the source guide and ask "does this teach a coherent end-to-end scenario someone would actually want to learn — routers/switches at scale, modeling a service, onboarding a new team — or is it the same content as the existing guide with sequence numbers stuck on it?" If the latter, the tutorial is feature-oriented, not scenario-oriented; flag it to the user and recommend **dropping the tutorial** from this PR with a follow-up entry on the Open Questions Confluence page describing the scenario rewrite. Do not ship feature-oriented tutorials — they don't earn their sidebar slot. (Precedent: the Profiles tutorial was dropped on PR #9114 review for exactly this reason.)

★ **Gate**: present the recommended pattern with rationale, including the tutorial scenario-shape verdict if applicable. User approves or chooses different.

### Step 4 — Create new files

Follow the chosen pattern. For section-wide migrations, do this **one feature at a time** with a build verification between each — see the section-wide recommendations below.

**Match the interfaces shown in the existing guide / tutorial.** Before writing any how-to or spoke content, look at the existing guide and tutorial for that feature. They use Tabs to show the same task across the **UI**, **Python SDK**, and **GraphQL** — that ordering reflects how users actually interact with the feature (UI primary, SDK via generators, GraphQL last). When you create the new how-to spokes, preserve that same set of interface tabs and reuse the same running example. Do **not** reduce a multi-interface task to GraphQL-only because it's faster to write — the existing guide content is the source of truth for which interfaces matter and what the canonical UI navigation steps look like. If a new task isn't covered in the existing guide, mirror the interface set used elsewhere in the same feature's docs.

#### Voice and tone

Match the voice of the canonical Infrahub docs and the conventions of well-regarded open-source documentation (Stripe, Tailwind, FastAPI, Docusaurus). The reader knows they are reading a docs page — do not narrate that fact at them.

**Do not refer to "this page", "this section", or "this document".** Those describe the layout/medium, not the content — the reader knows they are reading a page, and headers and the URL already do that wayfinding work. Banned phrases:

- ❌ "This page covers …" / "This page applies to …" / "This page collects …"
- ❌ "This document explains …" / "This section describes …"
- ❌ "On this page you'll find …"

Instead, just state what is true. If you genuinely need to direct the reader to nearby content, use **"below"** or **"here"**:

- ✅ "The steps below cover the canonical workflow for creating one."
- ✅ "The patterns below come from real-world experience …"
- ✅ "Standard groups only — Generator and Query groups …"

**"This guide" and "this tutorial" are fine** — those refer to the *functional kind of document* (a guide guides you, a tutorial teaches you). They are genre markers, not layout descriptors. Use them when the genre framing actually helps the reader:

- ✅ "This guide shows how to connect a remote repository …"
- ✅ "In this guide, we'll walk through three approaches and when to pick each."
- ✅ "By the end of this tutorial you will have built, deployed, and validated …"
- ✅ "This tutorial uses `BuiltinTag` objects so you can follow along without any special schema."

When the legacy source content uses the banned "this page / this section / this document" phrases (it often does), **rewrite them on extraction** — don't carry them forward. The new file is shipping under the new structure; legacy slop doesn't get a free pass just because it was already there. Legacy "this guide" / "this tutorial" usage on a guide or tutorial page is fine to keep.

**Tutorial opener convention.** Academy tutorials use ONE consolidated opener — see `academy/tutorials/groups.mdx` and `academy/tutorials/build-a-check.mdx` for the precedent:

- ✅ "By the end of this tutorial you will have built, deployed, and validated …" — one paragraph combining the framing with the outcomes, then the body

Do **not** use both a "This tutorial walks you through …" intro AND a separate "By the end of this tutorial you will:" bullet list — that's redundant. Pick one paragraph that does both jobs.

**Other voice rules** (carryover from project house style — apply to any new prose you author):

- No "Let me walk you through …" / "Let's get started …" — drop the meta and start the work
- No apologies, compliments, or filler ("Great!", "Awesome!", "Now you've successfully …")
- No "simply", "easily", "just", "simple", "easy" — they imply the reader is failing if it isn't simple for them (also caught by the AGENTS.md word check at PR time, but cheaper to avoid up front)
- Active voice, present tense, second person ("you create a Generator …", not "a Generator can be created by you")

**Single-page merge** (Computed Attributes precedent — PR #9120):

- Create `docs/docs/<feature>/index.mdx` — combine topic content (top) and guide content (rewritten below as how-to sections)
- Drop "Step 1/2/3" wording from headers; use action-named section headers ("Configure your X", "Verify your X")
- Numbered procedural lists *inside* sections stay numbered when sequence matters
- Replace running examples with placeholders like `<group-name>`, `<object-id>`
- Original `docs/docs/topics/<slug>.mdx` and `docs/docs/guides/<slug>.mdx`: **leave on disk** during iteration (legacy URLs work); deleted in cleanup PR
- Sidebar entry: `{ type: 'doc', id: '<feature>/index', label: '<Feature>' }` — the merged page IS the canonical sidebar entry; no folder/category needed

> **Why folder + index.mdx for single-page merges too?** Even when there's only one page, using `<feature>/index.mdx` keeps URLs stable (`/<feature>/`) regardless of future restructures. If the page later grows into hub+spokes, no file move is needed — only adding sibling spokes. Computed Attributes shipped this way; it's the established pattern.

**Hub + spokes** (Groups / Profiles precedent):

- Hub at `docs/docs/<feature>/index.mdx` — topic content only. **Do NOT add a "Common tasks" or "Deeper concepts" link list** — the spokes already appear in the sidebar when the user is on the hub, so a body link list is redundant clutter. A "Learn by doing" body link to an Academy tutorial is OK because the tutorial lives in a different sidebar section.
- Spokes at `docs/docs/<feature>/<task>.mdx` — one per task. Each spoke should have a brief "Next" or "Related" section at the bottom pointing to adjacent spokes.
- Optional concept spoke at `docs/docs/<feature>/<concept>.mdx` for substantial deep-dive content (e.g. priority and inheritance) when it's a frequently-referenced topic and would otherwise bloat the hub.
- Optional Academy tutorial at `docs/docs/academy/tutorials/<feature>.mdx`

> **Critical: hub categories must have a clickable link.** In `sidebars.ts`, every category that becomes a hub must include `link: { type: 'doc', id: '<feature>/index' }`. Without this, the category caret expands but the label itself is dead — clicking "Profiles" or "Branches" does nothing. The Groups, Profiles, and Branches categories all have this; it's a recurring bug to forget. Verify after writing the sidebar entry.

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

Each migration drops a YAML file in `docs/redirects-pending/` recording the URL changes the migration introduces. The file has three sections — redirects (legacy → new), new pages introduced (canonical URLs for cross-reference), and cross-links in other files that need updating at cleanup. At end-of-Phase-2 (cleanup PR), all files are aggregated. See `docs/redirects-pending/README.md` for the schema.

Create `docs/redirects-pending/<feature-or-section-slug>.yml`:

```yaml
---
feature: <Feature Name or Section Name>
pr: TBD
description: |
  Brief explanation of what changed and why these redirects exist.

# Legacy URLs that will redirect to new locations
redirects:
  - from: /docs/<old-path>
    to: /docs/<new-path>

# Net-new pages introduced by this migration (canonical URLs for cross-reference)
new_pages:
  - path: /docs/<feature>/
    title: <Feature> (hub)
  - path: /docs/<feature>/<task>
    title: <Task title>

# Internal cross-link references in OTHER files that point at legacy paths
# (will resolve via redirect at runtime but should be updated to new paths at cleanup)
cross_links_to_update:
  - file: docs/docs/topics/some-other-page.mdx
    line: 42
    current: ../topics/<slug>
    should_be: ../<feature>/
```

Common patterns for the `redirects` section:

- **Hub + spokes (Groups / Profiles precedent)** — both legacy URLs redirect to the new hub:
  - `/docs/topics/<feature>` → `/docs/<feature>/`
  - `/docs/guides/<feature>` → `/docs/<feature>/`
- **Single-page merge** — guide URL redirects to canonical topic:
  - `/docs/guides/<feature>` → `/docs/topics/<feature>`
- **Tutorial extraction only** — guide URL redirects to topic; tutorial URL is new (no redirect needed):
  - `/docs/guides/<feature>` → `/docs/topics/<feature>`

Update `docs/redirects-pending/README.md` "Files in this folder" table to add the new entry.

### Step 8 — Cross-reference scan

- Run `grep -rln '<feature-slug>' docs/docs/` to find inbound references to the legacy paths.
- For each, identify whether the page actually mentions / depends on the migrated feature (vs a path coincidence).
- For pages in **other sections** that should reference this feature in CONTENT (not sidebar), add an entry to the Confluence [Open Questions](https://opsmill.atlassian.net/wiki/spaces/Product/pages/567279617) page under "Surface cross-section content via prose." **Do NOT modify those other-section pages in this PR** — out of scope.
- For pages in other sections that have **stale Markdown links** to legacy paths (will resolve via redirect at runtime but should be updated to new paths at cleanup): **add an entry to the redirects-pending file's `cross_links_to_update` section** with `file`, `line`, `current` link target, and `should_be` link target. This gives the cleanup PR a complete inventory.
- For internal cross-links **within the feature itself** (e.g. spokes referencing each other, hub referencing spokes) that are now stale, fix them in this PR.

### Step 9 — Pre-PR audit ★

**Before opening the PR**, do a thorough audit pass. (This used to be the end-of-migration audit; moved earlier so issues land in the PR clean rather than as fix-up commits afterward.)

> **The audit is a real read-through, not a tool run.** Build + markdownlint + Vale + word-check are necessary but not sufficient. They catch syntax problems and policy violations, not factual drift or content gaps. The audit means **reading every new/modified file end-to-end with the source content open alongside**, looking for: extraction faithfulness (did the new spoke preserve every claim from the source?), hub coherence (does the hub still read as a complete concept page after the spokes were extracted?), invented content (did you write anything that has no analog in the source?), cross-link target accuracy (does each link land on the right page and section?). If the audit feels short, you're not doing it.
>
> **For section-wide migrations with 10+ pages, delegate to an Explore agent** with a focused brief. That's what scales — the agent reads everything in parallel and produces a structured findings report. Do not skip this with "I built clean and lint passed" — those caught zero of the real issues last time.

Specific things to verify:

- Re-read every new / modified file in this PR.
- For each **factual claim**, find a source: existing docs (current topic, guide, reference, schema specs, related feature docs), schema definitions, code comments. If a claim can't be sourced, flag it.
- Verify GraphQL mutations / queries match actual schema. Cross-check against:
  - `docs/docs/reference/schema/<feature>.mdx` if present
  - `docs/docs/topics/schema-attr-kind-*.mdx` for attribute kinds
  - Other feature docs that reference the same primitives
- Verify SDK examples are syntactically plausible. Compare against existing working examples in other feature pages.
- Verify all cross-links resolve to the correct page and section.
- Verify any new diagrams / tables / callouts are factually correct.
- For section-wide migrations: do a **user-perspective walk-through** as well — spin up the dev server, click through every new page in the order a real user would encounter them, look for orphan paragraphs / broken sidebar order / hub pages that read like stubs.
- Report findings with specific file paths + line numbers, e.g.:
  - `groups/use-in-automation.mdx:54` — claim about "Generator owns a CoreGeneratorGroup" is incorrect; per `topics/generator.mdx`, the SDK manages the CoreGeneratorGroup automatically.

★ **Gate**: present audit findings to the user. User decides which to fix in this PR vs defer. Fix the in-PR ones before continuing.

### Step 10 — Generate PR description ★

Draft a slimmed-down summary as the PR body. Template below.

★ **Gate**: present the draft PR description to the user. They approve or edit. **Do not commit until approved.**

#### PR description template

```markdown
## Summary

Migrate the **<Feature or Section>** per the Infrahub docs revamp.
Pattern: <single-page merge / hub + spokes / tutorial extraction / split / section-wide restructure>.

## Content changes

[Section-by-section list — keep brief.]

- **<Section name>**: <preserved as-is / rewritten as how-to / moved to Academy tutorial / etc.>

## What needs reviewer attention

[List the actual NEW prose the reviewer should read carefully. Skip anything that's verbatim extraction with only cross-link updates — the reviewer can trust those.]

Most of this PR is preserved content with cross-link updates. The actual NEW prose to review is small:

- **`<file>:<lines>` — <one-line description of new section/prose>.** <Brief rationale or where it came from — e.g. "Sourced from the Confluence net-new content draft" or "Standard spoke 'Related' closer matching Generators/Transformations precedent.">

Everything else (~XX% of the lines changed) is verbatim from the source legacy files with only cross-link path updates — safe to skim.

## What didn't change

- All factual content preserved; no new claims invented
- Original URLs continue to resolve (legacy `topics/<slug>.mdx` and `guides/<slug>.mdx` remain on disk during iteration; cleanup happens in a separate PR before production merge)

## Out of scope (tracked in Open Questions)

- [Cross-section content references to add elsewhere — links to Confluence Open Questions item]
- [Any structural gaps deferred]

## Verification

- `cd docs && npm run build` succeeds
- Local preview: `npm run serve` → http://localhost:3000
- Pre-PR audit completed (Step 9 of migrate-feature-page skill)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

### Step 11 — Lint, commit, push, open PR

**Always lint before committing** — required by `docs/AGENTS.md`:

```bash
uv run invoke docs.lint
```

This runs both markdownlint and Vale. **Both must pass** — Vale (documentation style) failures block CI in the `validate-documentation-style` check. Fix every error reported before committing. Warnings are not blocking but should be triaged: if a warning is in NEW content, fix it; if it's in pre-existing content unrelated to this PR, leave it.

> **Verify each lint tool actually ran** — don't infer from a clean wrapper exit. Some tools silently skip if not installed — `uv run invoke docs.lint` exits 0 even when Vale didn't run because the binary is missing. Run `which vale` first, or look for Vale's per-file output. Markdownlint passing ≠ Vale ran.

If Vale isn't installed locally, install it first — `brew install vale` on macOS, or download from https://github.com/errata-ai/vale/releases. Don't skip Vale checks; CI will catch what you missed and you'll have to push fix-up commits.

Common Vale rules to watch for:

- **`Infrahub.spelling`** — flags non-dictionary words. Either rephrase, or if it's a real word that should be in the vocabulary, add it to `.vale/styles/spelling-exceptions.txt`.
- **`Infrahub.swap`** — substitutes specific terms (e.g. "repo" → "repository"). Use the preferred term.
- **`Infrahub.branded-terms-case-swap`** — Infrahub product names should be capitalized (Transformations, Generators, Profiles, etc.) when used as branded references.
- **`Infrahub.eg-ie`** (warning) — replace `e.g.` and `i.e.` with `for example,` or `that is,`.
- **`Infrahub.sentence-case`** (warning) — headings should use sentence case, not title case.

For dev-internal docs that shouldn't be subject to Vale style rules (team workflow READMEs, planning artifacts), add a `BasedOnStyles =` exclusion in `.vale.ini` rather than fighting individual rules. Examples already excluded: `docs/docs/reference/**`, `docs/redirects-pending/**`, `**/AGENTS.md`.

Also check for AGENTS.md "Never Do" words that linters miss (`simple`, `easy`, `just`). Run this against **every file changed in the PR** — not just the docs pages, but also any skill, agent guide, or dev doc you touched. The forbidden-words rule is global; in-house dev docs aren't exempt.

```bash
git diff --name-only origin/demo/groups-diataxis-example...HEAD \
  | xargs grep -niE '\bsimple\b|\beasy\b|\bjust\b' 2>/dev/null
```

If any matches are in NEW content (whether docs or skill/dev files), fix in place. If matches are in PRESERVED content, propose fixing as part of the migration since the file is shipping under the new structure (the Profiles migration set this precedent).

Then commit, push, and open the PR:

```bash
git add <files>
git commit -m "docs: migrate <Feature or Section> per docs revamp"
git push -u origin docs/migrate-<slug>
gh pr create --base demo/groups-diataxis-example --title "docs: migrate <Feature or Section> per docs revamp" --body "<approved description>"
```

## Decision rules — content edits during migration

| Issue type | Action |
|---|---|
| Clear factual error | Fix in this PR |
| Structural gap (missing prereqs, troubleshooting) | Flag to user; ask whether to fix or defer to post-launch |
| Stylistic improvement | Flag to user; default is defer |
| Outdated example | Flag to user; ask |
| Stale terminology / voice inconsistency | Defer (out of scope for this revamp) |

## Recommendations for large or section-wide migrations

When migrating multiple features in a single PR (a whole docs section like Branches & Change Control), apply these patterns on top of the standard workflow above:

- **One feature at a time, with build verification between each.** Don't extract spokes from all hubs at once. Convert one feature → build → verify the pages render → move to the next. For B&CC: do Branches first (hub + 4 spokes + verify), then Proposed Changes (hub + 3 spokes + verify), then Checks (hub only). Catches problems early instead of compounding them.
- **Hub-after-extraction review.** When a hub loses its H3 content to spokes, verify the hub still reads as a coherent concept page on its own — not a stub. Re-read the hub cold after extraction; add bridging prose if the structure feels gappy. The Groups and Profiles hubs are good shape references.
- **Cross-link verification pass.** When pages move, internal `[link](../topics/foo)` references in OTHER files become broken at the URL level even though redirects will catch them. Run `grep -rn 'topics/<slug>\|guides/<slug>' docs/docs/` after each file move. For each match: fix immediately if it's within the feature being migrated, or log to the `cross_links_to_update` section of the redirects-pending file if it's in another feature/section.
- **Tutorial extraction is its own mini-migration.** If a feature's guide moves to Academy, treat it as a self-contained subtask with its own checklist: source location → destination, title change, placement decision (which Tutorials sub-category), cross-link from the source feature page back to the tutorial. Don't fold it into the hub-conversion work for the same feature.
- **Pre-PR user-perspective walk-through.** Already part of Step 9 for section-wide migrations. Spin up the dev server and click through every new page in the order a real user would encounter them. Look for: orphan paragraphs (content that lost its context when extracted), broken sidebar order, missing breadcrumbs, hub pages that read like stubs. This is a separate pass from the fact-check audit — it's a usability pass.
- **TodoWrite per page.** With 10+ pages being created, edited, or moved, a per-page todo prevents losing track. Each todo: "Extract <X> spoke from <hub>.mdx → docs/<feature>/<x>.mdx + verify build."
- **Stop at build verification gates.** If feature N doesn't build cleanly, don't proceed to feature N+1. Compounding failures are harder to debug.

## Confluence updates done as part of each feature migration

- **[Open Questions](https://opsmill.atlassian.net/wiki/spaces/Product/pages/567279617)** — append any new cross-section work needed; append any structural gaps deferred for later

**Do NOT** update the Navigation Map for individual feature migrations during iteration. The Map gets a single end-of-revamp update once Phase 2 is complete.

## Spec drift during implementation is normal

When implementation surfaces a gap in the recommendations doc (a missing spoke, a topic+guide that should merge, a hub click-target, a mistaken page move), **update the doc first, then implement against the updated spec.** The doc stays canonical; deviations are explicit. A few cycles of doc edits during a section-wide migration is expected — that's the planning-vs-implementation separation working as designed. The skill's meta-rule (above) catches the moment-of-decision; this section is the broader workflow note.

What this looks like in practice:

1. You hit a finding (e.g. "Git Integration category has no clickable hub link")
2. Per the meta-rule, present it to the user with rationale
3. User decides: yes, fix it / no, leave as-is / different approach
4. If yes, update the recommendations doc on Confluence to reflect the new spec
5. Then implement against the updated doc

Don't quietly diverge from the doc — that breaks the "one canonical spec" property and makes future review harder.

## What's explicitly NOT done in feature-migration PRs

- URL redirects (handled in cleanup PR before production merge)
- Modifications to other-section content (cross-section work goes in Open Questions; out of scope)
- Renaming or moving legacy `topics/<slug>.mdx` / `guides/<slug>.mdx` files (left in place so old URLs keep working)
- Bulk rewriting / voice-and-tone polishing

> **Distinction**: cross-section *content* changes are out of scope, but moving an *entire sub-category's sidebar position* is in scope when the recommendations doc specifies it. Example: in PR #9125, the Git Integration sub-category moved into Branches & Change Control as a nested sub-category. The pages inside Git Integration weren't rewritten — only their sidebar position changed (and their containing folder, since hub+spokes uses `docs/<feature>/`). That's allowed when the doc says so.

## After merge to `demo/groups-diataxis-example`

The feature PR merges into the consolidated parent branch (`demo/groups-diataxis-example`). Subsequent feature migrations branch off the updated parent so they pick up cumulative changes.

## End-of-revamp cleanup (out of scope for this skill)

When all feature migrations land in `demo/groups-diataxis-example` and the team is ready to ship to production:

- Delete legacy `topics/<slug>.mdx` and `guides/<slug>.mdx` files
- Update inbound cross-links in other docs to point at new paths (use each `redirects-pending/*.yml` file's `cross_links_to_update` section for the inventory)
- Install `@docusaurus/plugin-client-redirects` and add redirect entries (aggregate from each `redirects-pending/*.yml`'s `redirects` section)
- Single-pass content audit
- Single Navigation Map / Confluence update reflecting final state
