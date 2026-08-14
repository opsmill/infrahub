---
name: harvesting-review
description: >-
  Mines a pull request's review threads for lessons that generalize beyond that PR, reconstructs each against the actual code before deciding, checks whether it is already codified, and routes the genuinely-new, durable ones into Infrahub's internal documentation — `dev/knowledge/`, `dev/guides/`, `dev/guidelines/`, the `AGENTS.md` files, and `.agents/rules/` — proposing edits first and applying only with the user's approval. TRIGGER when: the user wants to turn PR review feedback into durable conventions, guidelines, or rules; capture recurring reviewer comments as internal documentation; or check whether review lessons are reflected in the knowledge/guides/guidelines/AGENTS.md/rules layer. DO NOT TRIGGER when: sweeping a feature's changes for documentation coverage across all layers → use `audit-docs`; extracting knowledge from completed spec directories → `speckit-opsmill-extract`; only replying to or resolving review threads → normal git/gh flow.
argument-hint: <PR number (#1234), branch name, or empty for the current branch's PR>
compatibility: Requires the Infrahub repository checked out and the `gh` CLI authenticated for PR/review access.
metadata:
  version: 0.8.0
  author: OpsMill
---

# Harvest Review Lessons

## User Input

```text
$ARGUMENTS
```

## What this does

Reviewers repeat themselves — the same idiom, naming, and layering nits recur PR after PR because
each lesson lived in a thread and died there. This skill reads a PR's review comments, keeps the ones
that **generalize into a rule a future author should follow**, investigates each against the actual
code before deciding, checks whether it is **already documented**, and proposes the smallest edit to
the right internal-doc file.

It also prunes as it goes: every run adds lessons, so nothing else stops the internal-doc layer from
growing forever if additions are the only thing that ever happens. §5 sweeps the destinations for the
staleness the docs already know how to name — a citation that's rotted, a defect note the code has
since fixed, an old narrow rule a newer one now generalizes — and folds the fix into the same PR. This
is not a separate cleanup pass; it runs every time, driven by what this run's review evidence turns up
against what previous runs wrote.

Counterpart to `audit-docs`: that sweeps a feature's *changes* for coverage; this starts from the
*review threads*.

## ⚠️ Refine, don't accrete — this outranks every other rule here

**A harvest that only adds has made the repo worse, however good each individual rule is.** The
internal-doc layer is context every teammate's agent pays to load; the routing rules below ("edit
before create", "strengthen before duplicate") stop duplicate *rules*, not growth. Nothing else in
this skill removes a single line, so it has to be you, on every lesson you apply:

1. **Measure before appending.** `wc -l` the target file and compare it against its size range in
   `dev/guidelines/repository-organization.md` (guidelines: 100-400 lines; knowledge: 200-400). A file
   at or over its range gets **compressed or split, never extended**. A split or move repoints every
   inbound reference in the same edit — grep the old path and section anchors across `dev/`, `docs/`,
   the `AGENTS.md` files, **and `.agents/skills`/`.agents/commands`**: skills and commands route by
   file path too, and a stale route sends every future agent to a file that no longer carries the
   content.
2. **Cut what the new rule supersedes.** Weaker, stale, or now-duplicated prose in that file goes in
   the same edit. Rewrite the section around the new rule instead of bolting it on the end.
3. **Report added/removed line counts** when you finish. Zero deletions means you accreted rather than
   refined — say that plainly instead of presenting it as a win.
4. **Raise the bar as the file grows.** "True but rarely needed" loses to keeping the doc readable. The
   best outcome of a harvest is often a *shorter* doc that now states the rule sharply.

Write every edit in the house style — `dev/guidelines/documentation.md`, *Writing Style → For Internal
Docs*: rule first, plain words, no padding, a few lines plus one example. Read that section before the
first edit.

## Internal documentation (where lessons go)

| Destination | What lives there | Cost / bar |
|-------------|------------------|------------|
| `.agents/rules/*.md` | Terse, imperative `always/never` rules, **auto-injected into every agent turn** | Highest bar — every rule costs tokens on every turn. Reserve for high-frequency, high-value discipline. Edit an existing rule before adding a file. |
| `dev/guidelines/**` | The fuller coding standard, consulted while writing code, with ✅/❌ examples | Home for idioms, style, testing practice. |
| `dev/knowledge/**` | How the system actually works — technical reference | When the lesson is an *explanation* a future dev needs (a constraint, an invariant, a non-obvious mechanism), not a do/don't. |
| `dev/guides/**` | How to do X — task-oriented guides and their checklists | When the lesson belongs in a step or a pre-submit checklist for a recurring task. |
| root `AGENTS.md` | Repo-wide facts, style, boundaries (Always Do / Ask First / Never Do), navigation | For *what to do / ask-first / where things live* — not code idioms. |
| `**/*/AGENTS.md` | Area-specific agent instructions and component maps | For area-scoped behavioural facts. |

Source of truth is `.agents/` — `.claude/rules`, `.claude/skills`, `.claude/commands` are symlinks
to it, so you edit `.agents/**` once and both harnesses see it.

## Workflow

### 1. Gather scope

Resolve `$ARGUMENTS` to a PR:

- **A PR number** (`#1234` or `1234`) — audit that PR.
- **A branch name** — resolve to its open PR (`gh pr view <branch>`).
- **Empty** — the current branch's PR (`gh pr view`). If none exists, ask.

Pull the raw material:

```bash
gh pr view <n> --json title,body,headRefName,commits
gh api repos/opsmill/infrahub/pulls/<n>/comments --paginate \
  -q '.[] | "--- \(.user.login) on \(.path):\(.line // .original_line)\n\(.body)\n"'
```

Read **resolved and unresolved** threads — a resolved thread whose lesson never made it into an
internal doc is exactly the gap this skill exists to catch. Prioritise **human** reviewers, but do
**not** filter by author: a bot comment (cubic, coderabbit) runs through the same step-3 investigation
as a human one and is kept when the code confirms its rule is durable — several of the most reusable
lessons arrive this way. Never sweep "all bot comments" into a PR-local bucket; when a bot-sourced
lesson survives, flag its origin and hold its promotion to a lower-confidence bar. Also skim the
**"addressed-by" commit messages** — they often state the lesson more crisply than the thread.

### 2. Extract & abstract candidate lessons

For each comment, abstract it to the underlying rule — **promote the rule, not the reviewer's
wording**. The line the reviewer touched is the symptom; the rule is the disease — a comment fixing one
call site usually points at a convention that spans many. Keep a candidate only if it passes all three:

1. **Generalizes** — applies beyond these lines (a convention, idiom, or architectural principle).
2. **Actionable as an imperative** — you can phrase it as "do X / don't do Y" an author follows next time.
3. **Would prevent a repeat comment** — a future reviewer would flag the same thing again if it isn't written down.

A fourth check bounds the other end: the rule must be **Infrahub-specific or a non-obvious gotcha**.
Universal programming hygiene every competent author already applies — "keep comments near the code",
"name things clearly", "write tests" — is not worth the per-turn token cost of a rule or guideline; set
it aside like any other non-lesson.

Everything obviously PR-local — a real bug, a typo — is set aside now. Borderline cases are *not*
judged yet; they go through the investigation, which is what tells you whether they generalize.

### 3. Investigate each candidate — the trail (do this BEFORE any decision)

For **every** surviving candidate, work the trail and write it down before reaching any verdict — **no
verdict, no home, no edit until it clears this step**; it is the one most easily skipped. A comment is a
symptom, not an instruction: read literally, a terse
"avoid X, use Y" can look like a sweeping refactor when the durable rule is small and local. You tell
them apart by reading the code, and by reading the correction that actually landed.

**a. Reconstruct before → after, then verify the claim.** Read the code the reviewer saw (the
*before*) **and** the correction that actually landed — the commit(s) pushed after the comment (the
*after*). The correction is the ground truth of the lesson; the comment only prompted it. A thread with
no landed change is unresolved or a no-op — flag it, do not invent a fix. Then verify: is the reviewer
technically right, and is the suggested alternative a real drop-in? Grep for real usages of the
alternative elsewhere in the repo (the method/pattern) and confirm it behaves the same. A lesson built
on an unverified claim — or on a correction that never landed — is worse than no lesson.

**b. Interpret the intent — what is the reviewer actually asking?** Separate:
- a **local code-style preference for new code** ("reach for the injected accessor here") from a
  **codebase-wide lifecycle change** (deprecate / migrate everything);
- **directional** guidance ("we'll delete this someday") from an **actionable request for this PR**;
- the **precise boundary** — which exact calls the rule covers and which it does not.

**c. Size the scope of the naive reading.** Ask what acting on the *literal* comment would cost. If it
implies a sweeping refactor (hundreds of call sites), a deprecation, or a migration, that is a strong
signal you have **mis-read it** — the durable rule is almost always the smaller "in new code, prefer X"
form. Name the over-scoped reading you are ruling out; that record is what stops the next person from
over-scoping too.

**d. Derive the precise rule — and its root cause.** Only now write the one-sentence imperative, scoped
exactly as the investigation showed, including any explicit carve-outs. Then name the **root cause**:
*why would an agent have proposed the rejected shape in the first place?* — a missing or violated
convention, a reflexive idiom (`or ""`, `default=str`), a copied legacy template, a misread
requirement. The root cause is what tells you whether writing the rule down would actually prevent the
repeat.

The investigation can also **demote** a candidate: if verifying shows the suggestion doesn't
generalize, is already the universal pattern, or was reviewer error, it becomes a "not a lesson" with
the reason recorded. Judge "generalizes" by whether the *underlying idiom or preference* recurs across
the codebase, **not by the size of the local fix** — a one-line defensive or idiomatic change
(`.get(key, default)` when reading untyped/external data, a naming or import convention, a preferred
accessor) is still a durable styleguide rule.

**Never demote a lesson on the assumption a linter or type-checker already enforces it — and do not run
those tools to decide.** A human reviewer having to raise it is itself evidence the tool did *not*
catch it. Typing and annotation corrections in particular (a missing `| None`, an over-narrow or
over-wide hint) are durable style rules: route them to `dev/guidelines/backend/python.md` (the *Type
Hints* section), never drop them as "standard Python".

Worked shape — the trail on the commonest case, a terse "avoid `X`, use `Y`":
- *Before → after:* read the code at the comment and the commit that landed the fix; if nothing landed, flag it and stop.
- *Verify:* open `Y`, confirm it exposes the same method/return as `X`, and grep for existing `Y` usages to prove it is an established drop-in.
- *Intent:* a style preference for new code, or migrate everything? Directional ("we'll drop `X` someday") or actionable now?
- *Scope:* count `X`'s call sites — a literal reading that means touching hundreds is a mis-read; name it, and note any spot where `X` legitimately stays.
- *Rule + root cause:* the smallest scoped imperative with its carve-out, and why an agent would have reached for `X` in the first place.

### 4. Check existing coverage, then route (dedup)

For each investigated lesson, grep the internal-doc layer for the rule:

```bash
grep -rin "<keyword>" .agents/rules/ dev/guidelines/ dev/knowledge/ dev/guides/ \
  AGENTS.md backend/AGENTS.md frontend/app/AGENTS.md
```

**A grep hit is not coverage until you read it.** Before you call a rule "already covered" — whether to
report it as *covered-but-flagged* or to demote it as "already codified, not a lesson" — open the
matched file at that line, confirm it states *this* rule and not an adjacent one, and cite the exact
`file:line`. A keyword that merely co-occurs (an enum-default rule is *not* covered by a
dependency-injection rule that happens to mention enums) is a coincidental match, not coverage.

A reviewer flagged this, so the verdicts are not a pass/fail of the docs — they are:

- **Missing** — the rule is written nowhere → propose the smallest addition in the most-specific home.
  If the only reason to write it down is a specific defect in the code *today* ("X is currently
  hand-duplicated", "Y isn't fixed yet"), it is not documentation — it will read as false the moment
  someone fixes it, and nothing revisits it. Phrase it as a forward-looking convention that stays true
  regardless of whether this exact instance ever gets fixed ("when adding a value generated this way,
  derive the fields rather than hand-listing them"), or drop it and suggest filing a GitHub issue
  instead of writing it into `dev/knowledge`/`dev/guidelines`. The same test applies when the root
  cause is a fragile *pattern* rather than a defect: if the honest fix is to stop writing the pattern,
  the lesson is the rule steering to the plain alternative, not a section teaching authors to survive
  it. A survival guide entrenches what it documents.
- **Covered but ineffective** — the rule *is* written, yet a reviewer still had to flag it. **This is a
  finding, not a relief** — there is deliberately no "covered and fine" verdict, because a documented
  rule a reviewer still had to raise is evidence the coverage is too weak, not proof it works. Report it
  prominently, never as "the layer works". Diagnose *why it didn't land* and propose how to make the
  **existing** doc land — do not add a duplicate rule. Pick the diagnosis:
  - **too abstract / no worked example** — states the principle but not the concrete case the author
    needed. The clearest signal: the reviewer had to describe the shape themselves (the class to build,
    the collaborators to inject, the method to call). If a reviewer has to draw the construction, the
    section is too abstract → add the ✅/❌ worked example that turns the flagged anti-pattern into the
    pattern.
  - **not discoverable** — the rule is in the *right* topical doc, but nothing pulled that doc into
    context when the author needed it. The fix is almost always **two coordinated edits, not a move**
    (the 1A+1B fix):
    - **1A — fix the load-trigger.** Add or upgrade the doc's entry in the router/index (the relevant
      `AGENTS.md` list) so it says *when* to load the doc — the triggering task or symptom — not just
      what it covers. A doc absent from that list, or listed with a topic-only description ("Query
      patterns"), never gets loaded; most "covered but ignored" rules fail here. Keep the entry to one
      or two sentences and rewrite rather than append: the router is a scannable index, and an entry
      that swells into a paragraph stops being read. Name the trigger and topic, never the rule's
      mechanics — a symbol name copied into the index rots the moment it is renamed (write
      "workflow-name conventions", not "reference names via `SomeClass.name`").
    - **1B — strengthen the rule in place.** Promote it out of any niche section into a prominent home
      and add the carve-out — but leave it in its topically-correct doc.

    Never relocate a domain rule (schema, DB, events, async-tasks…) into a general style guide because
    that doc is read more often: the topically-wrong home is *less* trustworthy, not more discoverable.
    The router entry is the discoverability mechanism, so fix the load-trigger, not the location.
  - **mis-homed** — the rule genuinely sits in the wrong topical doc, or belongs in a task's pre-submit
    checklist → move it to the most-specific correct home (or add the checklist line), then apply 1A so
    that home is actually loadable.
  - **stale / contradicted** — the doc no longer matches the code, so authors discount it → correct it.

  **Scope is not an alibi for the docs.** "Too much for this PR", "out of scope", or an existing-code
  carve-out are reasons not to change *code now* — they never exempt the *documentation* from being made
  more concrete. Before you lean on such a carve-out, check it applies: an existing-code exemption
  protects *pre-existing* code, not new code written in the old style (verify in the diff). Concluding
  "covered, correctly scoped, no edit" is the rationalization this step exists to prevent — reach for it
  only when the existing section already contains the concrete example the reviewer was forced to
  supply.
- **Not applicable** — the grep match was coincidental, or the comment was not actually a violation of
  the rule (a question, a one-off) → demote to Not a lesson, with the reason.

Routing rule of thumb: **most-specific existing home wins; edit before create; strengthen before
duplicate; fix the load-trigger before relocating; `.agents/rules` only for a true `always/never` that
must fire while coding.** Confirm the target file exists (`ls`/grep it, match sibling naming) before you
route a lesson there — never invent a plausible-looking path. Also check the topic still lives in `dev/`
at all: changelog conventions, for one, moved out to the `creating-changelog-entries` skill. When an
existing skill or command already owns the workflow a lesson touches (`creating-changelog-entries`,
`pre-ci`, or `pruning-residues` from the org skills plugin — not vendored in this repo but available to
agents running with it), route the edit into that skill and leave at most a pointer
in `dev/` — the same rule stated in two homes drifts apart.

### 5. Sweep for rot (prune before you add)

Every run of this skill only adds. Nothing else revisits what a previous run wrote, so the layer
grows monotonically — a doc entry that was true and useful the week it landed can quietly become
stale, redundant, or wrong, and stays in place forever unless a run like this one checks it. Do this
sweep every time, not as an occasional separate cleanup — it is cheap (a handful of greps, not a
re-read of every doc) and it is what keeps "harvested" from becoming a synonym for "bloated."

**a. Mechanical staleness grep.** Across the destination layer (`dev/guidelines/`, `dev/knowledge/`,
`dev/guides/`, `.agents/rules/`, `AGENTS.md`, area `AGENTS.md` files), grep for the anti-patterns the
docs already forbid — a rule existing but nobody enforcing it against older content is exactly the
"covered but ineffective" failure mode, aimed backward instead of at this PR:

```bash
grep -rnoE '(PR #[0-9]+|#[0-9]{4,6}\b)' dev/guidelines dev/knowledge dev/guides .agents/rules AGENTS.md */AGENTS.md
grep -rnoE '[A-Za-z0-9_/-]+\.(py|ts|tsx):[0-9]+(-[0-9]+)?' dev/guidelines dev/knowledge dev/guides .agents/rules
grep -rniE '(known gap|currently (broken|hand-duplicated|unfixed)|not yet fixed|for now,? (this|it))' \
  dev/guidelines dev/knowledge dev/guides .agents/rules
```

A hit outside this run's own new edits is debt from an earlier run (or from a doc written outside
this skill). For each:

- **A stale citation** (PR/issue number, spec file, line number) — drop the citation, keep the
  underlying behavior description the sentence was making. Don't touch surrounding prose beyond that.
- **A defect-snapshot note** ("known gap: X is currently...") — check the current code. If the defect
  is fixed, delete the note; it is now simply false. If still unfixed, either reframe it as a
  forward-looking convention (per the guardrail in §4) or drop it and flag it as a candidate GitHub
  issue instead of documentation.

**b. Supersession check.** When a lesson from *this* run generalizes something an earlier run wrote
narrowly — the same idiom, now with a second, broader instance — edit the earlier entry in place
(broaden its scope, replace its single example with the more general one) rather than leaving both.
Two entries saying almost the same thing at different generality levels is worse than one that's
right, because a future reader can no longer tell which one is current.

**c. Fix every hit now — a punch list is not pruning.** Each hit from (a) is a one-line mechanical
edit: drop the citation and keep the prose, or delete a defect note once the code confirms the fix.
A "found but left in place" list costs the same context as the rot it describes, and nobody comes
back for it. While at the line, check that the claim the citation was attached to still holds — a
dead citation often rides alongside a renamed method or a drifted line reference. Stay on the
codified anti-patterns; this is not a second `audit-docs` run. The only unresolved entries "Pruned
or consolidated" may carry are genuine calls for the user: file a GitHub issue for a real unfixed
defect, or flag a section needing a fuller rewrite than a sweep should attempt inline.

### 6. Report

Present the findings (format below) and stop. **Do not edit yet** — internal-doc files shape every
teammate's agent, so the blast radius is the whole team.

### 7. Apply (opt-in)

Ask which to apply: **all / cherry-pick / none**. Only then edit, following the §4 routing (edit an
existing section before adding one; keep `.agents/rules` lean) and the §5 pruning findings.

**Now apply *Refine, don't accrete* (top of this file)** — measure the file against its size range, cut
what the new rule supersedes, report the line counts. The investigation trail, the reviewer quotes, and
the ticket and PR numbers belong in this report and in the commit message, never in the doc text —
sweeping exactly that residue out of an artifact is what `pruning-residues` (org skills plugin, not
vendored here) does, so run it over the final diff when the plugin is loaded. A lesson that needs three paragraphs to state has not
been narrowed enough — go back to §3d. Match any
example code to `.agents/rules/code-doc-style.md` (no ticket/issue IDs, no naming specific callers).
**Never resolve review threads** — reply if useful, but resolution is the human reviewer's call. After
applying, run:

```bash
uv run invoke docs.lint
```

## Report format

```markdown
## Review-Lessons Report — PR #<n>

### Scope
<!-- PR, branch, how many threads read (resolved + unresolved) -->
<!-- After applying: lines added/removed per file, each file's size vs its range, what was cut. Zero
     deletions is a finding about this harvest, not a detail to omit. -->

### Existing coverage to strengthen (Covered but still flagged)

The rule already exists, yet a reviewer had to raise it — so the coverage is not landing. **This is the
highest-value output of the harvest, so it leads the report; when it is empty, open with "New rules to
add" instead.** For each:
- **Lesson** + **Source** (reviewer + quoted comment)
- **Already at**: the exact existing `file:line`, confirmed to be the same rule, not a keyword co-occurrence
- **Why it didn't land**: too abstract / not discoverable / mis-homed / missing from checklist / stale
- **Proposed edit**: how to make the *existing* coverage land — the concrete example to add, the
  load-trigger/relocation edit, or the checklist line. Not a duplicate rule.

### New rules to add (Missing)

For each:
- **Lesson**: the precise, scoped imperative (one sentence)
- **Source**: reviewer + quoted comment (and the addressing commit, if any)
- **Investigation**: the trail — (a) before → after (the code the reviewer saw vs. the correction that
  landed, citing the commit) and the claim verified in code (cite the files checked), (b) reviewer
  intent, (c) scope + the over-scoped reading ruled out
- **Root cause**: why an agent would have proposed the rejected shape — what writing the rule prevents
- **Home**: exact file (+ section) to create
- **Proposed edit**: the concrete text to add, already written in the house style (§6)

### Not Lessons (PR-local or demoted after investigation)
<!-- One-off fixes, bugs, and design calls that do NOT generalize — and candidates the investigation
     demoted (unverified claim, coincidental grep match, reviewer error, a question, or universal advice
     with no Infrahub-specific edge). Say why, briefly. Every lesson is grounded in a real comment; none
     is invented, and promoting every comment to a rule is as useless as missing the real ones. -->

### Pruned or consolidated (from the §5 sweep)
<!-- Debt from earlier runs, already fixed in this PR's diff — a hit reported without an edit is a bug
     in this run: stale citations dropped, defect notes deleted or reframed, narrow entries merged into
     the general one. For each: file:line, what was there, why it changed. Label the rare genuine user
     call (file an issue / fuller rewrite needed) "Needs a decision". Say "none found" when the sweep
     is clean. -->
```
