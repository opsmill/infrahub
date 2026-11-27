---
name: opsmill-product-writing-infrahub-docs
description: >-
  Writes, restructures, and migrates Infrahub docs feature, solution, and section pages,
  in the Infrahub main repo or in any other OpsMill docs repo (infrahub-sync, python-sdk,
  infrahub-ansible).
  TRIGGER when: the user asks to "create docs for X", "update the IPAM docs", "migrate
  Profiles", "write the hub for [feature]", "start the [section] migration", or any request
  to write or restructure Infrahub feature, solution, or docs-section content.
  DO NOT TRIGGER when: the work is voice/tone-only review of existing prose (use
  opsmill-product-auditing-voice); writing or revising release notes (use
  opsmill-product-writing-release-notes); generic Diátaxis docs unrelated to Infrahub; or generating
  README files, docs-overview pages, or product messaging briefs (separate skills outside this plugin).
compatibility: >-
  Delegates branch discipline, commit, and PR creation to the
  `opsmill-product-commit` and `opsmill-product-pr` skills (and transitively `opsmill-product-monitoring-pull-requests`). Docs
  build/lint (`uv run invoke docs.lint`, Vale) assume the Infrahub docs repo; other repos fall
  back to their own commands.
metadata:
  version: 0.6.1
  author: OpsMill
---

# Infrahub Docs

Writes, restructures, or updates Infrahub docs feature pages. **Propose one pull request covering the whole scope of the work** and confirm it with the user — see [Step 1](rules/02-workflow/step-1-preflight.md). Branch discipline and PR creation are delegated to the opsmill-product `commit` / `pr` skills (see [Step 11](rules/02-workflow/step-11-lint-commit-push.md)), so this skill never opens a PR by hand.

The skill defaults to the **Infrahub main repo** (`opsmill/infrahub`). In any other repository it works out the equivalent paths by reading the repository rather than asking the user ([Step 0.5](rules/02-workflow/step-0.5-detect-repo.md)).

## Required reads

A rule only applies when it is in your context. Each step file names the rule files it depends on, so an agent that never opens a step never learns which rules that step needed. This table lists them up front. Read every file in a row before the phase in that row starts. The smaller-update column is the minimum for every use case; the other two columns add to it.

All paths are under `rules/`. Use case names are the ones from [Use cases](#use-cases).

| Phase, and the point to have read it by | Smaller update (and every use case) | New feature docs: also read | Reorganization: also read |
|---|---|---|---|
| **Start**: before the Step 0 gate | `01-principles/gate-discipline.md`, `02-workflow/step-0-triage.md`, `02-workflow/step-0.5-detect-repo.md` | | |
| **Research**: before the Step 2 and Step 2.7 gates | `02-workflow/step-1-preflight.md`, `02-workflow/step-2-audit.md`, `02-workflow/step-2.7-content-audit.md` (for a smaller update, the lightweight pass that file describes; not needed for a [purely mechanical fix](#what-the-smaller-update-shortcut-covers)), `04-infrahub/domain-lifecycles.md`, `01-principles/no-customer-pii.md`, `01-principles/corrections-ledger.md`. When the user gave you an outline or a recommendations doc: `02-workflow/step-2.5-spec-review.md` | | `03-patterns/section-wide-migration.md`, when more than one feature moves |
| **Plan**: before the Step 3 gate | `02-workflow/step-3-outline.md`, `04-infrahub/docs-navigation-map.md`, `01-principles/product-terminology.md`. When the page introduces a capability (an overview or hub page): `03-patterns/overview-page-content.md`. When the page is a "which of these do I use" page: `03-patterns/comparison-page.md` | `03-patterns/decision-rules.md`, `03-patterns/overview-page-content.md`, the file for the pattern you recommend (`03-patterns/single-page-merge.md`, `03-patterns/hub-and-spokes.md` with `03-patterns/hub-and-spoke-scope.md`, or `03-patterns/tutorial-extraction.md`), and `01-principles/tutorial-shape-test.md` when a tutorial is in scope | `03-patterns/decision-rules.md`, the file for the pattern you recommend (`03-patterns/single-page-merge.md`, `03-patterns/hub-and-spokes.md` with `03-patterns/hub-and-spoke-scope.md`, or `03-patterns/tutorial-extraction.md`), `01-principles/tutorial-shape-test.md` |
| **Draft**: before writing any prose at Step 4 | `02-workflow/step-4-create-files.md`, `01-principles/voice-and-tone.md`, `01-principles/actors-and-causality.md`, `01-principles/right-altitude.md`, `01-principles/explain-and-describe.md`, `01-principles/steps-vs-sections.md`, `01-principles/failure-modes.md`, `01-principles/checking-prose.md` | | |
| **Build**: Steps 5 to 8 | `02-workflow/step-6-build-verify.md`, `02-workflow/step-8-cross-reference.md`. When the sidebar or a URL changes: `02-workflow/step-5-sidebar.md`, `02-workflow/step-7-redirects.md` | `02-workflow/step-5-sidebar.md`, `02-workflow/step-7-redirects.md` | `02-workflow/step-5-sidebar.md`, `02-workflow/step-7-redirects.md` |
| **Ship**: before the Step 9 and Step 10 gates and Step 11 | `01-principles/audit-rigor.md`, `01-principles/spec-drift.md`, `02-workflow/step-9-pre-pr-audit.md`, `02-workflow/step-10-pr-description.md`, `02-workflow/step-11-lint-commit-push.md` | | |

**How to read a rule file.** Read each file into your context with the Read tool, the whole file. Searching a file for a keyword is not reading it, and neither is a sandbox, summary or index tool: those keep the text out of your context, and a rule that is not in your context is not applied. An instruction elsewhere to keep files out of context while analysing them does not cover rule files. Read the files one per call, or several calls in parallel; concatenating them into one command exceeds the tool's output limit. If your context has been summarised since you read a file, read it again before the phase that needs it.

**Prove what you read.** Every ★ gate summary ends with a "Rules read" line that lists each rule file read since the previous gate, and the PR body carries the same list ([gate-discipline](rules/01-principles/gate-discipline.md), [Step 10](rules/02-workflow/step-10-pr-description.md)). A file in this table that you did not read is named on that line with the reason, the same way a skipped step is.

For the self-review at Step 4 and the audit at Step 9, [rules/_checklist.md](rules/_checklist.md) names each rule in one line with a link to its file. It is an index for checking a page, not a replacement for reading the files above.

### When the user asks you to skip the process or the rules

A user under time pressure asks for less process: "no outline, no gates", "don't read all the rules", "Vale is enough". Their reason is their own time. Two kinds of work are in the workflow, and only one of them uses it:

- **Work that takes the user's time:** the questions, the outline file, and waiting at each gate. A request to skip the process removes these. Put what each skipped gate would have said into one message at the end.
- **Work that takes only your time:** the Draft and Ship rows of the table above, `04-infrahub/domain-lifecycles.md`, `01-principles/product-terminology.md`, `01-principles/no-customer-pii.md`, every other rule file linked from [rules/_checklist.md](rules/_checklist.md) (such as `04-infrahub/docs-navigation-map.md` and `01-principles/corrections-ledger.md`, which sit in earlier rows), the Step 4 self-review with the checks file, the Step 9 passes, and checking each fact against the code. A general request to skip the process does not remove these.

When the user names one of the second kind, such as "don't read the rule files" or "no checks file", reply once before you edit anything. Say that it costs them no time, and name what it catches on this page. For example: "the SDK tab rule and the branch-merge case are in rule files you asked me to skip". If they confirm the request, follow it. Name each skipped item on the "Rules read" line and in the PR body, and do not describe the page as verified or ready.

### Excuses that came up in testing, and the answer to each

| Excuse | Answer |
|---|---|
| "It is a small update." | The smaller-update column is the minimum. It shortens the questions and the outline, not the reading. |
| "The user already checked the facts." | Product behavior is checked against the code (non-negotiable 7). In testing, two of the user's five facts were incomplete and one could not be checked in the code. |
| "The user wrote the draft; I only tidy the wording." | A user draft is source material (non-negotiable 2). The planted draft in testing had a false claim, a customer name and a GraphQL-only example. |
| "The user said not to read the rules." | Ask once, as described above. In testing, every run that skipped the Draft row missed the SDK tab. |
| "Vale passed." | Vale checks words. It passed a draft with a false claim in it. Report the checks by name and count instead. |
| "Concatenating the rules saves tool calls." | The output exceeds the tool limit and is saved to a file you then have to open. Read one file per call. |
| "It works with `infrahubctl`, so it works with Git integration." | Each interface needs its own source. In testing this produced a false sentence in three runs. |

## Non-negotiables, in every repo and every use case

These are constraints, not judgment calls. Each is expanded in its own file. They are repeated here
because they are the ones most often skipped, and skipping any of them silently is the failure:

1. **The numbered workflow and its ★ gates run in every repository.** Working in a different repository changes paths and tooling, nothing else. A step that has no equivalent here is skipped **by name, with the reason**, at the time and in the pull request description — never silently.
2. **User-provided draft content is source material, not finished docs.** It goes through the audit, the benchmark, and the voice rules like everything else; the deliverable is a revision with recommendations, never a paste-through. ([Step 0](rules/02-workflow/step-0-triage.md), "Classify what the user handed you")
3. **Thin input is a finding to report, not a constraint to absorb.** If all you have is code or a PR, say what the docs will therefore lack and what would fill the gap — before drafting, and again as open issues in the PR description. Undisclosed minimal docs are never acceptable. ([Step 0](rules/02-workflow/step-0-triage.md), [Step 2.7](rules/02-workflow/step-2.7-content-audit.md))
4. **Source material does not set the scope of a page.** A brief, blog post, transcript, existing page or PR description decides what you were handed, never what the page has to cover. Confident, well-organised material is the greater risk: nothing about it prompts you to look further, so its blind spots pass silently into the page. Establish scope from the code and from the domain's operations, then use the source material for framing. This is distinct from requirement 2, which governs how such material is treated; this one governs what it is allowed to leave out. ([domain-lifecycles](rules/04-infrahub/domain-lifecycles.md), [Step 2.7](rules/02-workflow/step-2.7-content-audit.md))
5. **User corrections survive rewrites.** Keep the [corrections ledger](rules/01-principles/corrections-ledger.md); re-check it after every restructure and once more at the pre-PR audit.
6. **No customer or personal data reaches the docs or the pull request.** Customer and prospect names, people, quotes from calls, and real environment data stay out of the prose, the code samples, the screenshots, the commits and the PR body. Generalise to the pattern instead. Content that legitimately names a customer needs the customer's written approval, which is not yours to assume. ([no-customer-pii](rules/01-principles/no-customer-pii.md), checked at [Step 9](rules/02-workflow/step-9-pre-pr-audit.md))
7. **Product behavior is verified against the source.** Arguments, defaults, limits, UI labels,
   commands, schema identifiers and code examples come from the code or the docs, never from
   memory. Content never invents product behavior.
8. **Builds, links and lint either pass or are reported as unavailable, by name.** A check that
   could not run is said to have not run.
9. **Established Infrahub terminology is preserved** where a synonym changes the meaning
   ([product-terminology](rules/01-principles/product-terminology.md)).

## Editorial standard

Everything about voice, structure, examples, paragraph shape, section openings and explanatory depth
is judgment. There is no sentence template to satisfy.

Write for experienced technical practitioners. Orient the reader before implementation detail, make
product behavior concrete, explain the decisions the reader has to make, and take examples from
recognizable network and infrastructure work. The rules behind that sentence are
[right-altitude](rules/01-principles/right-altitude.md) (what a page or a section opens with, and how
specific a named situation has to be), [explain-and-describe](rules/01-principles/explain-and-describe.md)
(how much explanation a page carries), [actors-and-causality](rules/01-principles/actors-and-causality.md)
(what the reader controls and what Infrahub does on its own) and
[voice-and-tone](rules/01-principles/voice-and-tone.md) (the register); the workflow steps link them
where they apply.

**Do not turn any of that into a mandatory sentence pattern.** A definition, a capability statement,
a reader action, a statement of product behavior and a practical rule can all be the right opening,
depending on what the section is doing. The one fixed rule is that a page does not open with the word
"use" ([right-altitude](rules/01-principles/right-altitude.md)).

## Write to the user in plain English

Everything you write for a person — chat replies, the outline, gate summaries, the PR description —
follows the same register as the docs.

A reply or a gate summary has four slots: what changed; why it matters to the reader of the page;
what was checked — each check by name and method, and each of the two prose walks by its count and
the path of the list ([checking-prose](rules/01-principles/checking-prose.md)); and the questions
only the user can answer. A gate summary also ends with the "Rules read" line
([gate-discipline](rules/01-principles/gate-discipline.md)); a list of file names is not narration. Use literal verbs. Use the product's own terms. Give a `file:line` reference for
any claim about product behavior.

Narration is anything outside those four slots — how you came to look, what you tried first, how
confident you felt. Leave it out, along with figurative verbs and sentences that would be equally
true of any piece of work. Naming a check with its method and count is the third slot, not
narration. This is the failure mode, from a real gate summary:

> ❌ "a reader reaches for this when the current state cannot explain the present"

Nothing reaches for anything, and the sentence carries no information. What it should have said:

> ✅ "Use a timestamp when the value you need has changed since."

Name things the way the user would. "This is a smaller update to the IPAM page" tells them what is
happening; "this is Use Case 1" tells them a number from a file they have not read. The same goes for
the workflow's internal vocabulary — step numbers, gate names and quadrant labels are yours, not
theirs.

For the PR description specifically, [Step 10](rules/02-workflow/step-10-pr-description.md) has the
full rule and a worked reference.

**The target voice is well-regarded OSS docs (FastAPI, uv, Stripe, Tailwind, Docusaurus) — not the existing Infrahub docs as-they-stand.** Existing Infrahub docs are calibration material for section structure and product vocabulary, but they are not the ceiling for voice. The [voice-and-tone](rules/01-principles/voice-and-tone.md) rule has the full mental-model check and failure-mode list. It applies in every repo.

## Use cases

The triage step at the start of the workflow picks which one applies.

1. **Smaller updates and feature improvements** — an existing docs page needs an addition, a fix, or a refresh (new attribute, new example, updated screenshot, prose cleanup). Voice and style rules apply. The audit still reads the whole page and the outline still runs, at a few lines rather than a document — the scope of the change is agreed at [Step 3](rules/02-workflow/step-3-outline.md), not assumed from the label. Structural change is not ruled out here; it is proposed there.
2. **New feature docs from scratch** — a feature or solution has no existing docs and needs them created. The skill recommends where the content goes, what shape it takes (single-page-merge / hub+spokes / tutorial extraction), and what overview / how-to / best-practices / tutorial content to include. Outline gets user approval before drafting.
3. **Reorganizing or migrating existing docs** — existing pages move to a different structure. Review what is there, recommend a pattern, get it agreed, then migrate. If the user supplies a structural outline, check it and add recommendations rather than producing a competing one — but **draft prose is not an outline**; see "Classify what the user handed you" in [Step 0](rules/02-workflow/step-0-triage.md).

The user says which of the three they want in their own words; you decide which applies after reading what they gave you. A brand-new page, or work whose only source is a pull request or the code, is **new feature docs** even when it sounds small. A **smaller update** needs very little material from the user and should not be slowed down by asking for it.

**Call them by name when you talk to the user, not by number.** They are a "smaller update or improvement", "new feature docs", and "reorganizing existing docs". The numbering is internal routing; what the user needs to confirm is whether this is an improvement to existing docs or something new.

### What the smaller-update shortcut covers

This is the one statement of the rule; the step files link here.

- **It shortens** the questions you ask the user and the length of the outline.
- **It never shortens** the reading. The [required reads](#required-reads) for a smaller update apply in full.
- **It never skips** the Step 4 self-review, the checks file with the subject and verb walks, the Step 9 audit, or the Step 10 PR body.
- **Each ★ gate is still its own message.** A short gate is still a gate.
- **One exception, set by [Step 2.7](rules/02-workflow/step-2.7-content-audit.md):** a purely mechanical fix, such as a typo or a renamed flag, skips Step 2.7 and its gate. Say so at the Step 2 gate. You do not need to read `step-2.7-content-audit.md` for it or name it as not read.

## Reference precedent

The docs themselves are the reference. Read the real pages rather than a description of them.

For **structure** — how a hub and its child pages divide up — the Groups feature is the clearest example:

- `docs/docs/groups/overview.mdx` — the hub
- `docs/docs/groups/*.mdx` — the child pages, one per task
- `docs/docs/academy/tutorials/groups.mdx` — the tutorial kept separate from the feature pages

For **what belongs on the page you are writing**, [overview-page-content](rules/03-patterns/overview-page-content.md) has a table matching the kind of page to the existing page that solves that problem best.

> **Do not use Groups or Profiles to calibrate voice.** The voice rules have changed since those pages were written. For voice, read the most recently merged feature pages in `docs/docs/`.

For a **section-wide restructure**, ask the user whether an agreed structure already exists — a document, a ticket, or a decision recorded somewhere. If it does, treat it as the approved structure and check it at [Step 2.5](rules/02-workflow/step-2.5-spec-review.md). If it does not, produce the outline yourself at [Step 3](rules/02-workflow/step-3-outline.md) and get it agreed before drafting.

## Material to ask for

Show this list once and ask for whatever exists — do not walk through it item by item. Come back with specific questions when research turns up a gap ([Step 0](rules/02-workflow/step-0-triage.md)).

- **Feature, solution, or section name** (e.g. "Profiles", "IPAM", "Resource Manager", "Branches & Change Control section")
- **The kind of work** — smaller update, new feature, or reorganization (the skill triages this at Step 0 if the user doesn't specify)
- **An existing outline or agreed structure** — a document, a ticket, or a few lines pasted in; it does not have to be formal
- **Source code repository or branch** — the feature's slice of the repo. Authoritative for product facts.
- **Existing docs** — current docs pages on the feature, related sections, or feature pages in adjacent products. Used for tone calibration and to identify what already exists.
- **Messaging brief, JPD card, spec-kit artifacts (`spec.md`, `plan.md`, `tasks.md`), or blog posts**
- **Optional notes** — anything else the user wants to flag.

For an update to a page whose framing already exists, this list is unnecessary — ask which page, what changes, and where the content comes from, then start.

Thin *conceptual* input is a subtler failure — the mechanics are supplied (config keys, API, the steps to enable it) but the why/when/best-practices layer is not. The skill was originally built assuming that layer would be provided; it often isn't, especially for net-new features. [Step 2.7](rules/02-workflow/step-2.7-content-audit.md) catches this during Phase 1, by reading comparable open-source docs and either proposing additions you can source or asking the user to supply what's missing — before the outline, not after a draft exists.

## Inputs the skill derives (Infrahub main defaults)

- The existing pages for the feature, under `docs/docs/<feature>/`
- Sidebar location in `docs/sidebars.ts`
- Inbound links from other pages (via grep)

For other repos these get resolved at [Step 0.5](rules/02-workflow/step-0.5-detect-repo.md).

## Workflow

Use TodoWrite to track. Stop and confirm with the user at every ★ gate, one gate per message, and end each gate summary with the "Rules read" line. See [gate-discipline](rules/01-principles/gate-discipline.md) for the meta-rule, and [Required reads](#required-reads) for what each phase needs.

The steps run in three phases. **All research happens before the plan, and the plan is agreed before anything is written.** Reading comparable docs is research, not a late audit — a page rewritten because nobody looked at how NetBox or Kubernetes solved the same problem is the expensive version of this step.

### Phase 1 — Research (nothing is drafted yet)

| Step | Gate | Purpose |
|---|---|---|
| [0 — Triage](rules/02-workflow/step-0-triage.md) | ★ | Pick use case, gather inputs, classify what the user handed you |
| [0.5 — Locate things in this repo](rules/02-workflow/step-0.5-detect-repo.md) | | Infrahub-main defaults, or detect the equivalents by reading the repository |
| [1 — Pre-flight](rules/02-workflow/step-1-preflight.md) | | Branch, clean tree, baseline build |
| [2 — Review existing content](rules/02-workflow/step-2-audit.md) | ★ | Read the source pages and the neighbours; find inbound links; read the exemplars closest to the page you're writing |
| [2.5 — Spec review](rules/02-workflow/step-2.5-spec-review.md) | ★ | When a recommendations doc exists, check it against the skill rules |
| [2.7 — Review comparable docs](rules/02-workflow/step-2.7-content-audit.md) | ★ | Read how comparable products solve the same problem; verify facts against code; produce the gap list — what you can source, and what needs an answer |

### Phase 2 — Plan

| Step | Gate | Purpose |
|---|---|---|
| [3 — Outline](rules/02-workflow/step-3-outline.md) | ★ | Recommend pattern + outline, built from everything in Phase 1 and agreed before drafting |

### Phase 3 — Build and ship

| Step | Gate | Purpose |
|---|---|---|
| [4 — Create files](rules/02-workflow/step-4-create-files.md) | | Draft per the agreed outline |
| [5 — Update sidebar](rules/02-workflow/step-5-sidebar.md) | | `sidebars.ts` or repo equivalent |
| [6 — Build + verify](rules/02-workflow/step-6-build-verify.md) | | Build passes; visually check |
| [7 — Redirects](rules/02-workflow/step-7-redirects.md) | | Infrahub-main only; skip if no mechanism |
| [8 — Cross-reference scan](rules/02-workflow/step-8-cross-reference.md) | | Find inbound references, fix or defer |
| [9 — Pre-PR audit](rules/02-workflow/step-9-pre-pr-audit.md) | ★ | Read-through audit before opening the PR |
| [10 — PR description](rules/02-workflow/step-10-pr-description.md) | ★ | Draft the docs PR body (reviewer-attention list) — handed to the `pr` skill at Step 11 |
| [11 — Lint, then delegate PR](rules/02-workflow/step-11-lint-commit-push.md) | | Docs lint (Vale + markdownlint + word check), then hand the Step-10 body to opsmill-product `commit` / `pr` (branch discipline, CI monitoring) |

If you find yourself looking at a comparable product's docs while drafting or reviewing, Phase 1 was not finished. Stop, complete the research, and take what you find back to the outline. Restructuring a page that is already written takes several rounds of revision; changing an outline takes one message.

## Drafts live in files, not in chat

**Every draft this skill produces — the outline at Step 3 and the page content at Step 4 — is written to a file before the user sees it, and the rules are applied to the file.** Chat carries the summary, the decisions, and the questions. It never carries the draft.

This is not a preference about formatting. Every safeguard in the workflow is attached to a file: the self-review pass in [Step 4](rules/02-workflow/step-4-create-files.md), the [corrections-ledger](rules/01-principles/corrections-ledger.md) re-check after a restructure, the build at [Step 6](rules/02-workflow/step-6-build-verify.md), the lint at [Step 11](rules/02-workflow/step-11-lint-commit-push.md). Prose pasted into chat reaches the user having passed through none of them, and the failure is silent — the draft looks finished, so nothing signals that the checks were skipped.

It applies to every revision, not only the first. A rewrite asked for in conversation goes into the file, is audited there, and is then shown. "Here are three options for this opening paragraph" is a fine chat message; three paragraphs of unaudited page prose is not.

| Deliverable | Where it goes |
|---|---|
| Outline or plan | A file. In Infrahub main, `dev/specs/docs/<slug>.md` — create the directory if it does not exist, and leave it uncommitted unless the user asks for it. Use a Notion page instead when other people review it before drafting starts. |
| Page content | The real `.mdx` file, on a branch, so it renders in the preview and the build checks its links |
| The subject and verb walks from [checking-prose](rules/01-principles/checking-prose.md) | One file beside the outline, `dev/specs/docs/<slug>.checks.md`, left uncommitted; the report cites each walk by count and path |
| Options, questions, rationale, and a summary of what changed | Chat |

## The rules

Every rule file, with a one-line description of what it covers, is indexed in
[rules/_sections.md](rules/_sections.md). That index is the single list — it carries all four groups
(`01-principles/` repo-agnostic, `02-workflow/` the numbered steps, `03-patterns/` structural
patterns, `04-infrahub/` Infrahub-specific reference) and it is kept in step with the files.

When each file has to be read is set by the [Required reads](#required-reads) table. Two of them are
often skipped because no step file opens with them:

- [docs-navigation-map](rules/04-infrahub/docs-navigation-map.md) — **before producing an outline at
  Step 3**, or validating one at Step 2.5.
- [domain-lifecycles](rules/04-infrahub/domain-lifecycles.md) — **at Step 2.7**, before the outline
  fixes what a page covers.
