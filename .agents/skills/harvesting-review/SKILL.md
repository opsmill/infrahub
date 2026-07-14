---
name: harvesting-review
description: >-
  Mines a pull request's review threads for lessons that generalize beyond that PR, investigates each one against the actual code before deciding anything, checks whether it is already codified, and routes the genuinely-new, durable ones into Infrahub's internal documentation — `dev/knowledge/`, `dev/guides/`, `dev/guidelines/`, the `AGENTS.md` files, and `.agents/rules/` — proposing edits first and applying only with the user's approval. TRIGGER when: the user wants to turn PR review feedback into durable conventions, guidelines, or rules; capture recurring reviewer comments as internal documentation; or check whether review lessons are reflected in the knowledge/guides/guidelines/AGENTS.md/rules layer. DO NOT TRIGGER when: sweeping a feature's changes for documentation coverage across all layers → use `audit-docs`; extracting knowledge from completed spec directories → `speckit-opsmill-extract`; distilling the current chat session rather than a PR into docs → `feedback`; only replying to or resolving review threads → normal git/gh flow.
argument-hint: <PR number (#1234), branch name, or empty for the current branch's PR>
compatibility: Requires the Infrahub repository checked out and the `gh` CLI authenticated for PR/review access.
metadata:
  version: 0.5.0
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
that **generalize into a rule a future author should follow**, **investigates each against the actual
code before deciding**, checks whether it is **already documented**, and proposes the smallest edit to
the right internal-doc file. It reports first; it edits only after you approve.

**Investigate before you decide.** A comment is a symptom, not an instruction. Read literally, a terse
"avoid X, use Y" can look like a sweeping refactor when the durable rule is small and local — you only
tell them apart by reading the code. No verdict, no home, no edit until a candidate has cleared step 3.

Counterpart to `audit-docs`: that sweeps a feature's *changes* for coverage; this starts from the
*review threads*.

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
internal doc is exactly the gap this skill exists to catch. Prioritise **human** reviewers; a bot
comment counts only when it reveals a durable convention, not a one-off drift in this PR. Also skim
the **"addressed-by" commit messages** — they often state the lesson more crisply than the thread.

### 2. Extract & abstract candidate lessons

For each comment, abstract it to the underlying rule. The line the reviewer touched is the symptom;
the rule is the disease — a comment fixing one call site usually points at a convention that spans
many. Keep a candidate only if it passes all three:

1. **Generalizes** — applies beyond these lines (a convention, idiom, or architectural principle).
2. **Actionable as an imperative** — you can phrase it as "do X / don't do Y" an author follows next time.
3. **Would prevent a repeat comment** — a future reviewer would flag the same thing again if it isn't written down.

Everything obviously PR-local — a real bug, a typo — is set aside now. Borderline cases are *not*
judged yet; they go through the investigation, which is what tells you whether they generalize.

### 3. Investigate each candidate — the trail of thinking (do this BEFORE any decision)

This is the heart of the skill and the step most easily skipped. For **every** surviving candidate,
work the trail and write it down. Do not shortcut to a verdict.

**a. Verify the claim against the code.** Is the reviewer technically right, and is the suggested
alternative a real drop-in? Read the touched code and the suggested replacement. Find real usages of
the alternative elsewhere in the repo (grep for the method/pattern) and confirm it returns the same
type / behaves the same. A lesson built on an unverified claim is worse than no lesson.

**b. Interpret the intent — what is the reviewer actually asking?** Separate:
- a **local code-style preference for new code** ("reach for the injected accessor here") from a
  **codebase-wide lifecycle change** (deprecate / migrate everything);
- **directional** guidance ("we'll delete this someday") from an **actionable request for this PR**;
- the **precise boundary** — which exact calls the rule covers and which it does not.

**c. Size the scope of the naive reading.** Ask what acting on the *literal* comment would cost. If
it implies a sweeping refactor (hundreds of call sites), a deprecation, or a migration, that is a
strong signal you have **mis-read it** — the durable rule is almost always the smaller "in new code,
prefer X" form. Name the over-scoped reading you are ruling out; that record is what stops the next
person from over-scoping too.

**d. Derive the precise rule.** Only now write the one-sentence imperative, scoped exactly as the
investigation showed — including any explicit carve-outs.

The investigation can also **demote** a candidate: if verifying shows the suggestion doesn't
generalize, is already the universal pattern, or was reviewer error, it becomes a "not a lesson"
with the reason recorded. But judge "generalizes" by whether the *underlying idiom or preference*
recurs across the codebase, **not by the size of the local fix**. A one-line defensive or idiomatic
change — `.get(key, default)` when reading untyped/external data, a naming or import convention, a
preferred accessor — is still a durable styleguide rule; "the fix was only one line here" is not
grounds to demote it.

The trail, generically, on a terse "avoid X, use Y":
- *Verify:* open the type behind `Y`, confirm it exposes the same method/return as `X`, and grep for existing `Y` usages to prove it is an established drop-in.
- *Intent:* a style preference for *new* code, or a request to migrate everything? Directional ("we'll drop `X` someday") or actionable now?
- *Scope:* count `X`'s call sites — if the literal reading means touching hundreds, that is a mis-read; name it and rule it out, and note any spot where `X` legitimately stays.
- *Rule:* the smallest scoped imperative, with the carve-out.

### 4. Check existing coverage, then route (dedup)

For each investigated lesson, grep the internal-doc layer for the rule:

```bash
grep -rin "<keyword>" .agents/rules/ dev/guidelines/ dev/knowledge/ dev/guides/ \
  AGENTS.md backend/AGENTS.md frontend/app/AGENTS.md
```

Now remember **why you are here**: a reviewer flagged this. So the verdicts are not a pass/fail of
the docs — they are:

- **Missing** — the rule is written nowhere → propose the smallest addition in the most-specific home.
- **Covered but ineffective** — the rule *is* written, yet a reviewer still had to flag it. **This is
  a finding, not a relief.** Report it prominently, never as "the layer works": if the docs had truly
  covered it, the comment would not exist. The existing doc failed to prevent the violation, so
  diagnose *why it didn't land* and propose how to make the **existing** doc land — do not add a
  duplicate rule. Pick the diagnosis:
  - **too abstract / no worked example** — states the principle but not the concrete case the author
    needed. **The clearest signal: the reviewer had to describe the shape themselves** (spelling out
    the class to build, the collaborators to inject, the method to call). If a reviewer has to draw
    the construction, the section is too abstract → add the ✅/❌ worked example that turns the flagged
    anti-pattern into the pattern;
  - **not discoverable** — the rule is in the *right* topical doc, but nothing pulled that doc into
    context when the author needed it. The fix is almost always **two coordinated edits, not a move**
    (call it the 1A+1B fix):
    - **1A — fix the load-trigger.** Add or upgrade the doc's entry in the router/index (the relevant
      `AGENTS.md` "Knowledge/Guides" list) so it says *when* to load it — the triggering task or
      symptom — not just *what* it covers. A `dev/knowledge`/`dev/guidelines` doc absent from that
      list, or listed with a topic-only description ("Query patterns"), never gets loaded. Most
      "covered but ignored" rules fail here: the trigger, not the rule, is missing.
      **Keep the entry to one or two sentences, and rewrite rather than append** — fold the *when*
      into the existing line, never bolt on another clause each harvest. The router is a scannable
      index, not a second copy of the rule; once an entry swells into a paragraph it stops being
      read, reopening the discoverability gap 1A exists to close. If the trigger can't be stated
      briefly, the doc's scope is too broad — that is not a licence for a longer entry.
      **Name the trigger and topic, not the rule's mechanics.** The entry says *when* to open the doc
      (the task, symptom, or stable API surface you'd be touching) and roughly what it covers — it must
      not bake in the specific method/attribute name, the do/don't, or the value the rule turns on.
      Those live in the doc; copying them into the index is the same "second copy" that rots the moment
      the symbol is renamed (e.g. write "workflow-name conventions", not "reference names via
      `SomeClass.name`").
    - **1B — strengthen the rule in place.** Promote it out of any niche section into a prominent home
      and add the carve-out — but leave it in its topically-correct doc.

    Do **not** relocate a domain rule (schema, DB, events, async-tasks…) into a general style/guide doc
    because that doc is read more often: a rule in the topically-wrong home is *less* trustworthy, not
    more discoverable. `.agents/rules/*` auto-injects every turn; guidelines/knowledge load only when
    the router points an agent at them, so the router entry *is* the discoverability mechanism;
  - **mis-homed** — the rule genuinely sits in the wrong topical doc, or belongs in a task's pre-submit
    checklist → move it to the most-specific correct home (or add the checklist line), then apply 1A so
    that home is actually loadable;
  - **stale / contradicted** — the doc no longer matches the code, so authors discount it → correct it.

  **Scope is not an alibi for the docs.** "Too much for this PR", "out of scope", or an
  "existing-code, don't-refactor" carve-out are reasons not to change *code now* — they never exempt
  the *documentation* from being made more concrete. Before you lean on such a carve-out, check it
  actually applies: an existing-code exemption protects *pre-existing* code, not new code written in
  the old style (verify in the diff whether the flagged code is new). Concluding "covered, correctly
  scoped, no edit" is the rationalization this step exists to prevent — reach for it only when the
  existing section already contains the concrete example the reviewer was forced to supply.
- **Not applicable** — the grep match was coincidental, or the comment was not actually a violation of
  the rule (a question, a one-off) → demote to Not a lesson, with the reason.

There is deliberately no "covered and fine" verdict: in a review harvest, a documented rule that a
reviewer still had to raise is evidence the coverage is too weak, not proof it works.

Routing rule of thumb: **most-specific existing home wins; edit before create; strengthen before
duplicate; fix the load-trigger before relocating; `.agents/rules` only for a true `always/never`
that must fire while coding.**

### 5. Report

Present the findings (format below) and stop. Do not edit yet.

### 6. Apply (opt-in)

Ask which to apply: **all / cherry-pick / none**. Only then edit. Prefer editing an existing section
over adding one; keep `.agents/rules` lean; match any example code to `.agents/rules/code-doc-style.md`
(no ticket IDs, no naming of specific callers). After applying, run:

```bash
uv run invoke docs.lint
```

## Report format

```markdown
## Review-Lessons Report — PR #<n>

### Scope
<!-- PR, branch, how many threads read (resolved + unresolved) -->

### Existing coverage to strengthen (Covered but still flagged)

The rule already exists, yet a reviewer had to raise it — so the coverage is not landing. **This is the
highest-value output of the harvest, so it leads the report; when it is empty, open with "New rules to
add" instead.** For each:
- **Lesson** + **Source** (reviewer + quoted comment)
- **Already at**: the exact existing file/section that supposedly covers it
- **Why it didn't land**: too abstract / not discoverable / mis-homed / missing from checklist / stale
- **Proposed edit**: how to make the *existing* coverage more accurate — the concrete example to add,
  the relocation/cross-link, or the checklist line. Not a duplicate rule.

### New rules to add (Missing)

For each:
- **Lesson**: the precise, scoped imperative (one sentence)
- **Source**: reviewer + quoted comment (and the addressing commit, if any)
- **Investigation**: the trail — (a) claim verified in code (cite the files checked),
  (b) reviewer intent, (c) scope + the over-scoped reading ruled out
- **Home**: exact file (+ section) to create
- **Proposed edit**: the concrete text to add

### Not Lessons (PR-local or demoted after investigation)
<!-- One-off fixes, bugs, and design calls that do NOT generalize — and candidates the investigation
     demoted (unverified claim, coincidental grep match, reviewer error, a question). Say why, briefly.
     Honesty here is the point: a harvest that promotes every comment to a rule is as useless as one
     that misses the real ones. -->
```

## Guardrails & red flags

- **Investigate before you decide.** No verdict, no home, no proposed edit until a candidate has been
  through step 3. If you are about to write a rule from a comment you have not verified in code, stop.
- **A literal reading that implies a big refactor is a mis-read.** Deprecation / migration / "touch
  hundreds of call sites" is almost never what a line-level review comment is asking. Find the small
  directional rule instead, and record the over-scoped reading you ruled out.
- **Report before editing.** Internal-doc files shape every teammate's agent — the blast radius is the
  whole team. Never edit before the user approves specific lessons.
- **"Already covered" is a finding, not a relief.** A reviewer flagging a rule that already exists is
  evidence the coverage isn't landing. Never report it as "the layer works"; lead with it, diagnose
  why it failed, and propose how to make the *existing* doc more accurate. Never add a duplicate rule.
- **Scope comments don't exempt the docs.** "Out of scope", "too much for this PR", and existing-code
  carve-outs govern whether to change *code now* — never whether a guideline should teach the pattern.
  If a reviewer had to describe the concrete shape, the section is too abstract: add the worked
  example. Do not use scope, or a carve-out you haven't confirmed applies, to conclude "no edit".
- **Edit before create; specific before general.** A new `.agents/rules` file clears the highest bar
  and needs a recurring, high-value `always/never` with no existing home.
- **A rule landing in a topically-wrong doc is a red flag — reconsider.** If your proposed home is a
  doc whose subject doesn't match the rule (a schema/DB rule going into a Python *style* guide), you
  have mis-diagnosed "not discoverable" as "mis-homed". Keep the rule in its correct home and fix the
  *load-trigger* instead — the 1A+1B fix in step 4.
- **"Too local to generalize" is a red flag — reconsider.** Before demoting a comment as one-off, ask
  whether the underlying idiom recurs elsewhere. Size of the diff ≠ scope of the rule; a one-line fix
  often encodes a general preference worth codifying.
- **Quote the reviewer, but promote the rule, not the wording.** Every lesson is grounded in a real
  comment; none is invented.
- **Respect `code-doc-style`** in any example code you add (no ticket/issue IDs, no naming callers).
- **Never resolve review threads** — reply if useful, but resolution is the human reviewer's call.
