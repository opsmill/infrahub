---
description: "Reconcile implementation drift by updating the feature's own spec, plan, and tasks"
argument-hint: "specs/###-feature-name [--spec-only|--plan-only|--tasks-only] <gap report>"
handoffs:
  - label: Implement Remediation
    agent: speckit.implement
    prompt: Execute the remediation tasks this run appended
    send: true
  - label: Review Plan
    agent: speckit.plan
    prompt: Review the architecture after the plan update
  - label: Check Convergence
    agent: speckit.converge
    prompt: Check the code against the updated artifacts
scripts:
  sh: ../../scripts/bash/check-prerequisites.sh --json --paths-only
  ps: ../../scripts/powershell/check-prerequisites.ps1 -Json -PathsOnly
  py: ../../scripts/python/check_prerequisites.py --json --paths-only
---
Act as the **Chief Software Architect** and **Implementation Auditor**.
A feature implementation has landed, but "artifact drift" has been discovered (e.g., missing routes, updated behavior, or unlinked UI). Your goal is to **reconcile** this drift by surgically amending the feature's own specification, plan, and task artifacts.

**Surgical means two things**: only the sections the gap report actually reaches are touched, and every word written traces to something in **Allowed Sources** below. Nothing is inferred from the shipped code beyond the one narrow lookup that section defines.

## User Input

```text
$ARGUMENTS
```

### Input Parsing

**This command reconciles exactly one feature per run.** There is no batch or range mode. To reconcile several features, run the command once per feature.

`$ARGUMENTS` names the feature, then optional scope modifiers, then a **Gap Report**: a natural language description of what is missing or changed in the implementation versus the documentation.

**Examples:**
- `specs/007-invoice-settings Backend + tests exist; React screen scaffolded. Users can't navigate to it. Need sidebar link + route.`
- `specs/007-invoice-settings --spec-only The /api/v1/settings endpoint now requires an 'org_id' header not in the original plan.`

**Grammar** — path, then modifiers, then prose:

1. **First token: the feature directory, required.** A path naming the feature to reconcile, which must resolve to **exactly one** existing directory under `REPO_ROOT`. A numeric prefix such as `specs/007` may expand to `specs/007-invoice-settings` when exactly one directory matches.

   **`specs/###-feature-name` is the usual shape, not the only legal one.** Spec Kit also produces timestamp directories (`specs/20260821-143000-invoice-settings`, from `--timestamp`), sequential numbers are **three digits at minimum rather than at most** (`specs/1000-…` is legitimate), an epic's sub-specs may be unprefixed (`specs/billing-invoices`), and `SPECIFY_FEATURE_DIRECTORY` can place a feature outside `specs/` altogether. **Resolution decides, not shape**: if the token resolves to one existing directory, it is the feature. Never reject a path for failing to look like `###-name`.
2. **Then: scope modifiers**, optional, recognised **only until the first non-flag token**:
   - `--spec-only` — update only `spec.md`
   - `--plan-only` — update only `plan.md`
   - `--tasks-only` — update only `tasks.md`
3. **Then: the gap report**, free text. From the first non-flag token onward everything is gap report, taken verbatim — including words that start with `--`, such as a report about a `--force` flag.

If **several** modifiers are supplied, the scope is their **union**: `--spec-only --tasks-only` updates both `spec.md` and `tasks.md` and nothing else.

**Trailing modifiers are still recognised**, because earlier versions of this command accepted only that form. The **trailing run of modifier tokens** — the unbroken sequence of them at the very end of the input, one or several — scopes the run exactly as leading ones do, and several combine into the same union: `…report text --spec-only --tasks-only` writes both files, as it did before this version. It is the *run* that must reach the end, not each modifier individually.

The leading position is canonical and unambiguous; the trailing one is a compatibility path and carries the ambiguity that motivated the change. When the report's own last words are **one of the three modifiers**, take the scoping reading — not "prefer" it, since a parser that hedges gives two agents two answers — and state the interpretation under `## Scoping`, so a user who meant it as prose can see it and re-quote. A trailing token that starts with `--` but is **not** one of the three (`--force`, say) is **prose**, never an error: rule 3's rejection is leading-position only.

**Only the middle is prose.** Both ends scope: the leading position per grammar rule 2, and the trailing run per this paragraph. A modifier is prose only when it sits **after the gap report has begun and before the trailing run** — `specs/001 fix the --spec-only screen` scopes nothing, while `specs/001 --spec-only fix the screen` scopes normally. When modifiers appear in **both** positions, the scope is the union of all of them, exactly as several modifiers in one position combine.

**Validate everything else.** The first four checks are textual and run before Step 0; the fifth needs `REPO_ROOT` and so runs as soon as 0.1 has resolved it, still ahead of every write. **No file is written when any of them fails** — a rejected invocation must leave the repository exactly as it found it.

1. **Empty input, or no feature at all.** If `$ARGUMENTS` is empty, **or the first token starts with `--`** (the feature path must come first, before any modifier), output `ERROR: No feature spec directory provided. Usage: __SPECKIT_COMMAND_RECONCILE_RUN__ specs/###-feature-name [--scope-modifier] [gap report]` and stop.
2. **More than one feature.** This check comes **before** the flag check, so a range or a second path gets the guidance below rather than a generic parse error. Reject when the input covers more than one feature. The checks key on **feature-shaped tokens**: a token containing a `specs/<segment>` path segment in any form (`specs/002-x`, `specs/001`, `../specs/002-x`, `/repo/specs/002-x`, `specs/20260821-143000-x`, `specs/billing-invoices`; a glob character may stand in for any of it, as in `specs/00*`), or a bare feature number or name such as `007` or `007-invoice-settings`. **Any `specs/` path counts, whatever the segment looks like**, which is what keeps the guard working for timestamp and unprefixed features, which the `###` form would miss entirely.

   **Two limits, both deliberate.** A `specs/` segment counts only when it is the **first** segment of the token or follows a directory-traversal prefix (`specs/x`, `./specs/x`, `../specs/x`, `/abs/path/specs/x`). A `specs/` sitting deeper inside an ordinary source path (`src/specs/openapi.yaml`, `docs/specs/api.md`) is **not** feature-shaped and never triggers this check, because those are the source paths a gap report is expected to name. And the guard is shape-based, so a second feature living outside `specs/` (via `SPECIFY_FEATURE_DIRECTORY`) is **invisible to it**. That is a known limit rather than a promise: rule 1 resolves the *first* token by resolution rather than shape, while this guard can only match text, and the two are not the same test.

   **Those two limits constrain the token, not its position in the input.** A feature-shaped `specs/` path counts **at any position**, prose included, which is what makes a gap report mentioning `specs/002-notifications` a second feature. A **bare** feature reference counts only in the **leading region** (the first token, any modifiers, and the token immediately following them, which is where a second feature would be written if one were meant), and only when it carries the full `###-name` form (`002-notifications`). Two things follow, and both are deliberate: a bare **number** alone (`002`) counts only **beside a range marker whose other side is a feature reference** (the `008` in `specs/001 thru 008`), and a gap report that **opens** with a number is therefore safe (`specs/001-task-manager 404 errors now appear on the digest route`). Keying on the `###-name` form rather than on position alone is what makes that possible: the region has to include the first gap report token to catch `specs/001-task-manager 002-notifications …`, so the form is what separates a second feature from an ordinary opening word: digits inside later prose (`handle 404 errors`, `max 500 items`, `3 screens are unreachable`) are gap report, and so is ordinary punctuation (`double-checked?`, `billing/invoicing`, `*emphasis*`):
   - two or more feature-shaped tokens
   - a glob character (`*` or `?`) **inside a feature-shaped token** (`specs/00*`, `0??-export`)
   - a **word** range marker — `thru`, `through`, or `to` — appearing as a whole token between two feature references (`specs/001 thru specs/008`, `specs/001 thru 008`)
   - a `..` **separating two feature references inside a single token** (`specs/001..specs/008`, `001..008`)

   A word marker only counts as a whole token, never as part of a directory name, so `specs/003-import-to-csv` and `specs/012-through-put` are legitimate single features. A `..` only counts when it sits between two feature references, so the leading `../` of a relative path such as `../specs/001-foo` is not a range. On a match, output:
   ```
   ERROR: This command reconciles one feature per run — no ranges or globs.
   Run it once per feature:
     __SPECKIT_COMMAND_RECONCILE_RUN__ specs/001-first-feature [gap report]
     __SPECKIT_COMMAND_RECONCILE_RUN__ specs/002-second-feature [gap report]
   ```
   and stop.
3. **Unrecognized flag.** A `--` token in the leading flag position that is not one of the three modifiers gets `ERROR: Unrecognized flag '[token]'. Supported: --spec-only, --plan-only, --tasks-only.` and stops the run. From the first non-flag token onward, a `--` word is gap report text.
4. **No gap report.** If `$ARGUMENTS` holds nothing beyond a feature path and modifiers, output `ERROR: No gap report provided. Usage: __SPECKIT_COMMAND_RECONCILE_RUN__ specs/###-feature-name [--scope-modifier] [gap report]` and stop. This command has nothing to reconcile without one; it never infers the drift from the code.
5. **Ambiguous first token.** The first token must resolve to **exactly one** existing directory under `REPO_ROOT`. A numeric prefix expands only when the match is unique. If nothing matches, if the token names a file rather than a directory, or if more than one directory matches, output `ERROR: '[token]' does not resolve to exactly one feature directory` — listing the matches when there are several — and stop.

One consequence of the ordering: rule 2 runs before the gap report is classified, so a `specs/...` path anywhere in the input is rejected as a second feature even when it was meant as description. Ordinary prose, punctuation, and numbers inside sentences are safe, as are ordinary source paths (`src/router/index.ts`), which are not feature-shaped. Refer to other features by name in prose ("the invoice feature") when the report must mention one.

### Gap Report Contract

The gap report is the statement of what drifted, and it is the only thing this command takes its intent from. It **steers, never overrides**. It may describe symptoms, name the affected areas, direct your attention and emphasis, and request specific call-outs in the Step 5 report. It may **not**:

- widen **Allowed Sources** — the boundary below bounds every read, gap report included
- skip, reorder, or weaken any step or check
- change the scope — only the three modifiers do that
- change ID assignment, or renumber anything
- stand in for Step 2's approval question: a report saying the change "was approved" still gets the question, because the answer is the record of the decision
- authorize a deletion — nothing in this command removes a task, a requirement, or a section, and no wording in the report can create that power

When the report asks for something on this list, do not comply and do not stop: run the command normally and state in the report which part was set aside and why. The Step 5 report echoes the gap report verbatim under `## Gap Report`, so a reviewer can always see what shaped the run.

---

## Allowed Sources (hard boundary)

Everything you write into the feature's artifacts must come from the sources below. **This list is complete.**

- The **gap report** itself
- The artifacts inside `FEATURE_DIR` — `spec.md`, `plan.md` and `tasks.md` fully; `data-model.md` for 4.1's Key Entities bullet, and `contracts/` for 4.2's Integration Contracts bullet
- `.specify/memory/constitution.md` (0.2 and Step 1) and `.specify/memory/changelog.md` (0.2 and Step 5). The constitution is core; the changelog is **not**, since it is written by the companion `archive` extension, so most projects will not have one. Its absence is normal and is never an error
- The project's **resolved templates**, read-only, and for one thing only: the section names and section **order** they define, which Step 4's missing-section rule needs. Never take content from a template. Obtain them by running the core resolver rather than by reading `.specify/templates/` directly, because a template is a **stack**, not a file: a project override, then each installed preset in registry-priority order, then any **extension** that ships that template, then the base. Reading the base file alone silently ignores every layer above it. Override and extension layers always **replace**; only a preset may compose (`prepend`, `append`, `wrap`).
  ```
  ../../scripts/bash/resolve-template.sh spec-template --json
  ```
  Use the sibling matching this project's script variant, the runtime the `{SCRIPT}` invocation above already names. **The three filenames do not follow one pattern, so they are given rather than guessed**, and a guessed name fails silently into the fallback below:
  - bash: `../../scripts/bash/resolve-template.sh <name> --json`
  - powershell: `../../scripts/powershell/resolve-template.ps1 <name> -Json`
  - python: `../../scripts/python/resolve_template.py <name> --json`, invoked the same way the `{SCRIPT}` line above invokes its own `.py` file (note the **underscore**; only the Python file spells it that way)

  The template name carries **no `.md` suffix**: `spec-template`, and `plan-template` when 4.2 creates a plan section, since Step 4's missing-section rule covers both artifacts. If the resolver is absent or fails, fall back to reading `.specify/templates/` directly and **say so under `## Sources`**, because the fallback can be wrong on a project that layers templates.
- The output of `{SCRIPT}`

The step numbers above are **descriptive, not restrictive**. This list bounds *which files* you may take content from, never *which step* may read one.

**Path resolution is a separate, narrower permission.** 4.3 requires every remediation task to name an exact file path, and a gap report often describes a target ("the sidebar") rather than naming one. You may therefore read the **repository tree and its source files, read-only**, to resolve a described target to a real path, to confirm that a path you are about to write exists, and to confirm that the **directory** a newly created file will sit in exists. Take nothing else from them — no requirement, scenario, plan sentence, or acceptance criterion ever comes from source code, because the gap report is what states the drift and code cannot state its own intent.

**What a task may name is 4.3 rule 3's decision, and it is stated there and nowhere else.** This section bounds what you may *read*; when a path counts as derived and when a task is written without one lives in 4.3. It is deliberately not restated here — a rule written in two places is a rule that will eventually disagree with itself, which is how the two halves of this one came apart once already.

**Take content from nowhere else.** Not from git history, `git log`, `git show`, stashes, other branches, or any file that was deleted or renamed. Not from ad-hoc notes files. Not from an agent memory or session store. Not from another feature's spec directory. Not from a `bugs/` report: a bug report is not a gap report, and a bugfix extension's own patch step is the sanctioned channel for its amendments (see **Annotations left by other commands** in Step 1).

**This bounds content, not tooling.** Running `git status` or `git diff` to verify what you just wrote is fine. Reading git to *obtain* the drift, or to reconstruct an artifact's earlier contents, is not.

Report compliance under `## Sources` in Step 5.

---

## Step 0: Discovery & Setup (Gate)

### 0.1 Resolve Paths

Resolve paths **in this order** — each depends on the one before it, so do not reorder them.

**1. `REPO_ROOT`.** Run `{SCRIPT}` and take `REPO_ROOT` from its output.

- **If the script is missing**, stop and inform the user. It ships with Spec-Kit, so its absence means this is not an initialised Spec-Kit project.
- **If the script runs but exits non-zero**, commonly `Feature directory not found` on a checkout with no `.specify/feature.json`, this is **not** fatal. Its feature directory is not used anyway (see step 2). Recover `REPO_ROOT` in this order, and note which branch was taken in the Step 5 report:

  1. **`SPECIFY_INIT_DIR`, if it is set in the environment and the directory it names contains `.specify/`.** It is the explicit project selector: the core script checks it before anything else, and rejects it outright when that `.specify/` is missing, so apply the same test rather than trusting the variable. In a monorepo it is the only thing that says which member project is meant, and skipping it lands the run on a sibling project, which is worse than failing. When it is set but fails that test, say so in the report and fall through to the walk-up.
  2. Otherwise, resolve the first token of `$ARGUMENTS` against the **current working directory** and walk up to the nearest ancestor containing `.specify/`.

  Stop only if neither yields a directory.

**2. `FEATURE_DIR` — the argument always wins.** Resolve the first token **under `REPO_ROOT`**, not under the current working directory, even when step 1's fallback started from cwd — the walk-up has already established `REPO_ROOT` by then, and a run invoked from a subdirectory would otherwise reject a perfectly valid `specs/001-x`. Apply the **ambiguous first token** check from Input Parsing at this point.

**A token written relative to the cwd resolves to the same directory.** `../specs/001-x`, passed from a subdirectory, means the feature that `specs/001-x` names under `REPO_ROOT`; it does not mean a path outside the repository. Strip any leading `../` segments before resolving, and resolve what remains under `REPO_ROOT`. A first token that still points outside `REPO_ROOT` after that fails the ambiguous-first-token check like any other non-match.

Ignore whatever feature directory `{SCRIPT}` reports. It resolves the project's own state (`SPECIFY_FEATURE_DIRECTORY`, then `.specify/feature.json`) — whichever feature was last worked on, which is not necessarily the one that drifted. When the two differ, report both in Step 5, because this command rewrites three files in place and a user who passed the wrong path needs to see it.

**3. Remaining paths.**
- `FEATURE_SPEC` (`FEATURE_DIR/spec.md`)
- `IMPL_PLAN` (`FEATURE_DIR/plan.md`)
- `TASKS_FILE` (`FEATURE_DIR/tasks.md`)

Use absolute paths for all file operations.

**Validation**: Ensure `spec.md` and `plan.md` exist. If either is missing, stop with:
> ⚠️ Missing required files in `FEATURE_DIR`. Expected: spec.md, plan.md.
> Run `__SPECKIT_COMMAND_SPECIFY__` and `__SPECKIT_COMMAND_PLAN__` first.

**Step 0 is a gate and writes nothing**, including `TASKS_FILE`. 4.3 creates that file when it needs it.

### 0.2 Load Context

Read `FEATURE_SPEC`, `IMPL_PLAN`, and `TASKS_FILE` (the last one if it exists). **Read regardless of scope**: a modifier says what may be written, never what may be read.

Also read `.specify/memory/changelog.md` if it exists, and note whether this feature already has an entry in the Merged Features Log, and the date it was archived. Step 5 uses both.

Also read `.specify/memory/constitution.md` if it exists. Extract the MUST-level constraints from its Core Principles, Architecture Standards and Quality Gates.

**While reading it, note any stated spec-persistence model.** Spec Kit documents three, each a team's choice of how to maintain artifacts. This command amends a feature's artifacts in place, so the model the constitution states decides whether it may write at all:

- **Flow-back**: accepted discoveries are reflected in the existing artifacts. This is what this command does.
- **Living spec**: `spec.md` is the contract, and `plan.md` and `tasks.md` are brought into line with it, directly or through an extension. This command amends `spec.md` and reconciles the plan and tasks with it, which fits the model.
- **Flow-forward**: completed artifacts are **immutable**, and a change means a *new* feature directory. Amending them in place would break the team's governance, however correct the content.

The model is a team convention with no machine-readable signal, so **only a statement in the constitution counts**, and most constitutions will not have one. It must say affirmatively that the project uses the model: a sentence that names flow-forward only to reject it, or to describe it, does not count, and when you cannot tell, the model is not stated. **When the constitution states flow-forward, write nothing**, on every run, including one during delivery, because under that model any change goes into a new feature directory. Quote the sentence that stated it under `## Approval`. Ask no Step 2 question, treat every normalized item as withheld by the persistence model, and still print the report: every artifact shown as `No change (flow-forward)` in the Sync Impact Map, and the recommendation to capture the change in a new feature directory with `__SPECKIT_COMMAND_SPECIFY__` and deliver it through the normal loop. When the constitution states flow-back or living spec, or states no model, reconcile normally. Running this command is the team's choice to amend in place, so the command never infers a model and never treats one as the default.

**A rule is MUST-level only when it says so.** Those three headings say where to look, not that everything under them binds: a constitution often carries aspirations, rationale and house style beside its rules, and a section heading does not promote them. Extract a rule when it states an obligation in binding terms (`MUST`, `MUST NOT`, `is not allowed`, `never`); leave the rest, and take no finding from it. Reading every bullet under a heading as binding turns Step 1 into a survey and produces a finding on every run.

For each extracted rule, note which shape it takes, because Step 1 checks all three and a shape not recorded here is invisible later:

- it **forbids** something ("shared or unassigned active tasks are not allowed");
- it **requires a statement** from features meeting a condition ("every feature that stores user data MUST state its retention rule"), together with any location the rule names for that statement;
- it **requires an action** ("every dependency added MUST be approved by the security review board"): something to be *done* rather than written;
- or **both** of the last two, which one sentence often does. Record both halves; filing it under one loses the other.

---

## Step 1: Gap Normalization

Analyze the user's **Gap Report** and normalize it into structured remediation items.

Classify only; Step 4 owns which artifact each category is written to.

| Category | Typical Issues |
|----------|----------------|
| **Wiring & Navigation** | Missing routes, menu items, sidebar links. Two clauses, both below: something shipped that a user cannot reach, **or** a routing surface that ships undeclared |
| **Contracts** | API field mismatches, missing headers |
| **Requirements** | Shipped code adds, drops or redefines a capability |
| **Behavior** | Implementation behaves differently than planned |
| **Data Model** | New or changed entity, field, or validation rule |
| **Outcomes & Assumptions** | A measurable target or a stated assumption no longer holds |
| **Test Coverage** | New wiring/navigation without verification |
| **Logic/UX** | Success toasts missing, error handling gaps |

**The Wiring & Navigation boundary decides whether a test is mandatory, so it is defined rather than illustrated.** 4.3 rule 4 makes an integration test compulsory for this category and optional for every other, so the classification changes what lands on disk and cannot rest on which of the examples above a drift resembles.

**Two things put a drift in this category, and either one is enough.**

1. **Something that exists cannot be reached.** The capability is present in the shipped code and a user cannot get to it: no route, no link, a screen or control that never renders, a control rendered but wired to nothing.
2. **A routing surface ships and the plan that lists routing surfaces omits it.** A route, endpoint or navigation entry that ships and that `plan.md` leaves out of the section where it records such things is unverified routing, which is the thing this category exists to force a test for. It does not matter that a user can reach it today; nothing records that it should stay reachable.

   **Clause 2 needs a plan that declares routes at all.** It compares a shipped surface against the plan section that holds routing surfaces, whatever the project calls it. A plan carrying no such section declares no route anywhere, so its silence says nothing about this drift in particular, and 4.2 is explicit that a plan without one is the ordinary case rather than a deficient one. On such a plan clause 2 cannot fire: classify by clause 1 and by what the drift is, so a header or payload change to an endpoint that already ships stays **Contracts**. Where the drift is itself what first gives the plan a routing surface to record, 4.2 creates the section under the missing-section rule, and clause 2 governs every later run against that plan.

It is **not** Wiring & Navigation when the capability is simply absent and no routing surface is involved: a field the form never had, a rule never implemented, a message never written. Those are Requirements, Behavior or Logic/UX, because there is nothing to reach and nothing routing to verify.

Three worked cases, because this is where careful readers split:

- *"The export button is on screen but its handler was never bound"*: the control exists and reaches nothing. **Wiring & Navigation** by clause 1; the integration test is mandatory.
- *"We shipped `POST /api/v1/exports`, which the plan never mentions"*: reachable today, undeclared in the artifacts. **Wiring & Navigation** by clause 2; the integration test is mandatory.
- *"Invoices need a currency field, which was never specified"*: the field does not exist and no route is involved. **Requirements**; no test is compelled, though one may still be written.

**When you genuinely cannot decide, classify it as Wiring & Navigation.** An unnecessary integration test costs one task; a missing one costs the verification this category exists to guarantee.

### 1.1 Constitution Check (three shapes)

A MUST rule can fail in more than one way, matching the three records from 0.2. **Check only the rules the normalized remediation items actually reach** — this is a surgical command, and a constitution rule the drift never touches is not its business. That bound is what keeps this a check rather than a project-wide audit.

**What a gap report's "route" denotes, since constitution rules turn on it.** A rule about routes fires on what the report says shipped, not on what you can picture shipping. Read it this way:

- A report naming a path (`/api/v1/settings`, `GET /settings`) names **that** route, and its kind is whatever the path says it is.
- A report saying a **backend, API or endpoint** exists, without naming a path, states that an **API route shipped whose path the report does not give**. The condition of an API-route rule is met; the path is not available to write.

**A rule bounded to a *new* route needs the report to say the route is new.** Many constitution rules read "any **new** API route MUST ...". Their condition is met only where the report states the route shipped with the work being reconciled: "the backend now exists", "the endpoint was added after the plan was written". A report that merely *mentions* a route while describing something else about it does not make it new, so "the API accepts a second `owner_id`" is a payload change on a route that already shipped, and a new-route rule is not reached by it. Where the report leaves it genuinely open whether the route is new, treat it as new and say so under `## Defaults Applied`, since an unnecessary declaration is cheaper than a route that ships undeclared.
- A report naming a **screen, page, link or navigation entry** states a **client** route. It is not an API route, and an API-route rule is not triggered by it alone.
- A report describing both halves ("backend and tests exist, the screen is unreachable") states **both**: an API route whose path is unnamed, and a client route.

This is a reading rule, not an inference licence. It decides which rules a report reaches; it never supplies a path, and where the path is unnamed the statement half of any rule demanding one stays unmet, because the report did not give it.

1. **Conflict** — a remediation item would write content contradicting a MUST rule. Flag it CRITICAL:
   ```
   🔴 CONSTITUTION CONFLICT: [remediation item] conflicts with [Principle N / Architecture Standard / Quality Gate]: "[rule text]"
   → Raised in Step 2; an unresolved conflict withholds this item only.
   ```
2. **Unmet obligation** — a rule requires a statement, the drift meets its condition, and no statement exists in the feature's own artifacts (or not in the location the rule names, when it names one). Nothing contradicts anything here; the required content is simply absent, and it is exactly as binding:
   ```
   🔴 CONSTITUTION OBLIGATION UNMET: [Principle N / ...]: "[rule text]"
     Triggered by: [what this drift does that meets the rule's condition]
     Missing:      [the statement the rule requires, and whether it is absent everywhere or only from the named location]
   → Raised in Step 2. This never withholds anything.
   ```
   **An obligation this run's own amendment satisfies is not unmet.** Where the gap report itself supplies the required content and Step 4 will write it into the location the rule names, the rule is met by that amendment: do not flag it, and do not ask about it. A constitution rule saying "any new API route MUST be declared in the plan's Routing & Navigation section", against a drift reporting a route the plan lacks, describes exactly the edit 4.2 is about to make — flagging it would raise a mandatory question about the work in progress. Judge shape 2 against the **end state this run will produce**, not against the artifacts as they stand at 1.1. Decide it here, now — this finding feeds Step 2's always-ask questions, so it cannot be deferred to a later step. This is the same escape hatch shape 3 carries, and it exists for the same reason.

   **Never write the missing statement yourself** in every other case. The gap report states what the implementation does, not what the author intends a rule to say, and a rule asking for a judgment the report does not make — a retention period, a threshold, a policy — is unmet however obviously it is missing. The legitimate remedy there is a remediation task directing the author to make the statement, which 4.3 writes like any other task — **unless `tasks.md` is out of scope**, in which case write nothing and name the un-written task under `## Scoping`, exactly as 4.3 rule 4 does for the mandatory integration test. A scope modifier is never overridden to satisfy an obligation.

   The line between the two has **two** conditions, and both must hold: the gap report already contains the answer, **and** this run will actually write it where the rule names. It does for "the digest endpoint was added after the plan was written" at full scope; it does not for "state your retention rule", and it does not when a scope modifier keeps the run out of the artifact the rule names — an obligation whose location is out of scope stays unmet, because nothing will satisfy it this run.

   **A `NEEDS CLARIFICATION` marker never satisfies an obligation.** Where 4.2 writes a routing entry whose path the report never named, the entry records the drift but leaves the required value blank, so the first condition fails: the gap report did not contain the answer. The obligation **stays unmet** and is raised, even though this run wrote into the very section the rule names. A placeholder is not a declaration, and treating it as one would let every rule demanding a value be closed by an entry that supplies none. This is the same conclusion 1.1's reading rule reaches from the other direction, where the path is unnamed the statement half stays unmet, and the two must not be allowed to disagree.
3. **Action-requiring** — the rule asks for something to be *done*. This command reads artifacts and cannot inspect a codebase, a test run, or a CI result, so it can never establish that the action happened, and never that it did not. **Report it as unverified under `## Outstanding Items`; never flag it and never ask about it.** A claim is not a verification: a plan saying nothing, a plan claiming "tests for both routes", and a Testing Strategy whose list omits one route are all equally unverified. The one exception is an artifact **explicitly stating the action was skipped** ("no tests for this route yet"), which is ordinary content contradicting a rule and goes through shape 1.

   Where the drift itself closes such a rule, the remediation task is the right output — a **Wiring & Navigation** gap under a "routes MUST have tests" rule already produces the mandatory integration test of 4.3.

**Your judgment belongs in deciding whether a rule's condition is met, not in deciding whether a qualifying finding is worth raising.** Once a conflict or an obligation qualifies, it goes to Step 2 and the user decides; under a flow-forward constitution (0.2), where nothing is asked or written, record it as moot under `## Constitution Compliance` instead. An argument for why a finding is too minor to raise is an answer to the Step 2 question, not a reason to skip it.

**The feature's own `## Constitution Check` is input, not a verdict.** A `plan.md` usually carries one. Read it, and quote it in the Step 2 question when it bears on the answer, but **never close a finding on it alone**: it records what the author believed at planning time, before the work was done, and re-checking that belief against what actually shipped is the reason this check exists. "No violations" in a plan is evidence about intent, not a finding.

**But distinguish a verdict from a statement of fact.** What that rule bars is treating the author's *opinion about compliance* as the answer. It does not bar the section from containing content a rule actually asks for. Where a MUST rule requires the feature to **state or record something**, and the Constitution Check is where the feature states it, that statement satisfies the obligation like any other. The test is what the sentence does: **"we checked and it is fine" is a verdict and closes nothing; "here is what we changed and why" is the record the rule demanded.**

### 1.2 Annotations left by other commands

This command is not the only writer of these three files. A bugfix extension patches them, and a requirement-change command retires and supersedes entries in them. Both leave markers behind, and both are recording a decision somebody already made. **A marker is never an invitation to reopen the decision it records**: the amendment goes elsewhere, and the marker is reported rather than edited.

(The markers below are unrelated to the `## Revisions` notes this command writes in Step 4. Those are this command's own record of what it synced; these are somebody else's record of what they decided.)

**Bugfix markers.** A bugfix extension (the community `bugfix` extension, for instance) patches the same three files this command edits. Read its markers as follows, so a reconciliation never undoes a patch:

- Text struck through with `~~...~~` counts as **superseded by a patch** when a `**Bugfix**:` marker or a live replacement wording sits in or beside the same entry. Treat the replacement as the current text. **Never restore struck wording while amending an entry**, and never carry it into a new one.
- `**Bugfix**: [DATE] — [BUG-NNN] ...` lines are patch metadata, not requirement text. Leave them in place; do not amend them and do not treat them as the entry's content.
- A task annotated `(reopened — BUG-NNN)` is **incomplete**, whatever its checkbox shows. It is therefore not "completed work" for the never-edit rule in Step 4 — but do not edit or repurpose it either, because it belongs to a bugfix cycle in progress. Append the remediation task and name the overlap under `## Outstanding Items`.
- Struck text with neither a marker nor a replacement is not a patch artifact you can interpret. Leave it exactly as it stands and name it under `## Outstanding Items`.

**Retirement and supersession markers.** A command that changes a requirement rather than reconciling one marks entries `RETIRED`, `SUPERSEDED by [ID]`, or `CANCELLED` instead of deleting them, precisely so the history stays readable. Where an artifact carries such markers, read them as follows. Where it carries none, which is every project that has never run such a command, this paragraph applies to nothing and changes no behaviour.

**What counts as a marker**, stated as precisely as the bugfix markers above, because these rules can suppress an amendment entirely. A marker is the bare word `RETIRED`, `CANCELLED`, or `SUPERSEDED by [ID]`, **upper-case**, appearing in the entry's own line or in a parenthetical or trailing clause attached to it, so `**RETIRED** — reason`, `(CANCELLED — reason)`, `SUPERSEDED by FR-021` are all markers. Two things are **not** markers and change nothing: the same words in lower or mixed case, and any occurrence inside the entry's descriptive prose rather than attached to the entry as an annotation ("the job retires stale sessions" is requirement text). When you cannot tell an annotation from prose, treat it as **prose** and name the ambiguity under `## Outstanding Items`, because a false marker silently drops an amendment, while a missed one merely leaves an entry to be amended normally.

- A requirement, scenario or criterion marked **`RETIRED`** is a decision that the capability is gone. It is never amended and never revived, not even when the gap report describes drift that appears to reach it: reviving it would silently reverse the retirement. Reconcile the drift against a live entry if one exists, otherwise add a new one, and name the retired entry under `## Outstanding Items` so the author can see what the report seemed to be pointing at.
- An entry marked **`SUPERSEDED by [ID]`** is not the target; the entry that `[ID]` names is. Resolve it by the citation ladder and amend that one, then **name the superseded entry under `## Outstanding Items`**, as the retirement bullet above requires for its own marker: the report appeared to reach that entry and the amendment went elsewhere, which the author needs to see. When `[ID]` resolves to nothing, amend neither, and name the pair there instead; guessing which entry inherited the meaning is exactly the judgment a superseded marker exists to remove.
- A task marked **`CANCELLED`** is neither completed work nor available work. Do not edit it and do not repurpose it. It **still counts** when finding the highest `T###`, because a cancelled ID is retired, never reused. Append the remediation task and name the overlap under `## Outstanding Items`.

**Open Convergence tasks.** `__SPECKIT_COMMAND_CONVERGE__` appends tasks under `## Phase N: Convergence` that trace to an entry, such as `per FR-007 (contradicts)`. A task is **open** when its checkbox is unchecked and it is not marked `CANCELLED`. When an open Convergence task traces to an entry that this run amends, or that the revision note under this run's slug already names on its `Items:` line (an earlier run amended it, and a re-run that writes nothing must still warn), that task was written against the old intent, and `__SPECKIT_COMMAND_IMPLEMENT__` would carry it out. Never edit it, never close it and never repurpose it: the Convergence phase is converge's ledger. Name each such task under `## Outstanding Items` with the entry it traces to, and say in `## Next Step` that the team should resolve or close it before running implement.

---

## Step 2: Clarify (At Most Once; Max 5 Questions)

If the gap report is ambiguous (e.g., "the button doesn't work" without saying which button), ask targeted questions. Ask **only questions that materially change scope or correctness**, and ask none of them if everything is unambiguous. **The step itself is never skipped**, because the approval question below is always asked; the one exception is a constitution that states flow-forward (0.2), where the run writes nothing and asks nothing.

**Both sentences above govern discretionary questions only.** The **always-ask** questions below are exempt from the materiality filter: their value is the record of the user's decision, so "the answer would not change what gets written" is never a reason to drop one.

**Always ask for approval of the drift, first.** This command records decisions the team has accepted. It never decides on its own that the shipped code is right, because a drift nobody accepted means the artifacts still state the intended behaviour and the code is what should change. List every normalized item from Step 1, numbered, and ask, as one question, which of them the team approves reconciling into the artifacts. Say what approving means for each kind of item: for a change in behaviour, that the shipped behaviour is now the intended one; for missing work (something unreachable, unwired or untested), that the artifacts should record the gap and remediation tasks should be added. The legal answers are **approve all**, **approve some** (naming which, by number or by name), and **approve none**. An item the answer does not clearly name is not approved; say so under `## Approval`.

**The approval question is the first question of Step 2's single round**, not a round of its own: print it first, then the constitution and discretionary questions, and wait once. Approval covers each item **as the same round's discretionary answers resolve it**: the user answers both together, so a clarification never withdraws an approval: no clarification answer can leave an item out. (An unresolved conflict and a flow-forward constitution still withhold items, as below.) When a clarification splits an item, every part keeps the item's approval. When it merges items, content that came from an item the approval answer left out stays withheld.

- An item the answer does not include is **withheld**, exactly like an item with an unresolved conflict (below): written nowhere, and given its disposition under `## Approval` (it is not listed again as withheld or outstanding under `## Constitution Compliance` or `## Outstanding Items`; a moot finding on it and the Next Step may still name it) with the recommendation to run `__SPECKIT_COMMAND_CONVERGE__`, which checks the code against the artifacts as they stand.
- Approval never overrides a conflict: an approved item whose conflict stays unresolved is still withheld.
- A constitution finding on an item that is not approved is moot. Record it as moot under `## Constitution Compliance`, whatever answer its own question received.
- **Approve none** is a valid outcome, not an error: the run writes nothing at all, including the retroactive `## Revisions` heading of Step 4, and still prints the report, with every artifact shown as `No change (all items withheld)` in the Sync Impact Map.

**Always ask** about the CRITICAL findings from 1.1. Ask **conflicts and obligations as separate questions**, bundling all of each category into one, because the two take different answers: an obligation may be closed as an accepted gap and a conflict may not.

- **Conflict question.** Legal options: **declare it not actually a conflict** (the rule does not say what it appeared to say, or the item does not do what it appeared to do), which clears the flag and writes the item normally; **revise the gap report and re-run**; or **leave it unresolved**. "Write it anyway" is **not** an option. Only the first option keeps the item on this run — revising and re-running withholds it now exactly as leaving it unresolved does, and the difference is only what the user intends to do next. Say so, so nobody is left believing the item lands this time.
- **Obligation question.** Legal options: **record it as an accepted gap**; **add a remediation task** directing the author to make the statement (subject to 1.1's scope carve-out); or **declare the obligation not triggered** because the condition is not actually met. Under every option the drift's own content is reconciled normally.

Use this format and **wait for answers**:

```markdown
## Question [N]: [Topic]
**Context**: [Relevant implementation detail, and the rule text when the question is a constitution finding]
**Decision Needed**: [1 sentence]
**Suggested Answers**: [Table with Option A/B/C]

**Your choice**: _[Wait for user response]_
```

**What an unresolved conflict does.** It **withholds that item and only that item**: the conflicting remediation item is written into no artifact, generates no task, and is named in the report under `## Constitution Compliance` and `## Outstanding Items` with the recommendation to resolve it and re-run. Every other item in the gap report is reconciled normally and the run completes. **Nothing in Steps 2 to 5 aborts a run**; withholding is the only way an item is left out, and an unmet obligation never causes it. An item the approval answer leaves out is withheld the same way, but its disposition is reported under `## Approval` only, with the converge recommendation in place of the resolve-and-re-run one.

**Rules:**
- Max 5 questions total: the approval question, at most one conflict question and one obligation question, and the rest for discretionary ones. Bundle discretionary questions into one; if the budget is spent, report them under `## Outstanding Items` rather than dropping an always-ask question to make room.
- Max 3 unresolved `NEEDS CLARIFICATION` markers in output — beyond that, pick reasonable defaults and note them under `## Defaults Applied`.

---

## Step 3: Impact Map

Before making any edits, produce a brief impact map. It is the user's preview of this run, so it must promise only what the run will actually do: mark any artifact a scope modifier excluded as `Skipped (out of scope)`, any artifact an earlier run already reconciled under this slug as `No change (already applied)`, every artifact as `No change (all items withheld)` when the approval answer left everything out, and every artifact as `No change (flow-forward)` when the constitution states flow-forward (0.2). Derive the slug per Step 4 before producing this map.

This table's rows are **artifacts**. An item withheld by an unresolved conflict, by the Step 2 approval answer, or by a flow-forward constitution (0.2) is not an artifact and has no row here; it is recorded in the Targets table below, whose shape that section defines.

```markdown
### Sync Impact Map
| Artifact | Changes | Tasks Generated |
|----------|---------|-----------------|
| `spec.md` | Amend Acceptance Scenario under User Story 2, add Edge Case | None |
| `plan.md` | Add Route `/settings`, update API contract | None |
| `tasks.md` | Append remediation tasks | T045, T046, T047 |
```

**Then the target table.** It records *which existing item each amendment will land on* before any edit, rather than leaving that choice implicit in the writing — the same choice made twice can otherwise come out two different ways. Identify each target by the **citation ladder** defined in Step 4.

**One row per target.** A target is one entry in one artifact this run **considered writing**, so a remediation item takes as many rows as it has targets: two entries in `spec.md` and one in `plan.md` is three rows. This is finer than "one row per artifact" because the table exists to preview *each amendment decision*, and an item that touches routing, contracts and testing in one plan has made three of them. **Every row carries exactly one action**, which is the point of the unit, and it is what makes the counts below reproducible.

**Five actions exist, and each row takes exactly one.** The list is closed: every row in the table is one of these, and `None` is as real an action as the other four, and it is what the `Z` count counts.

| Action | When | Artifact / Target cells |
|---|---|---|
| `Amend` | the row changes the text of an **existing entry** | entry named, by the citation ladder |
| `Add` | the row creates a **new entry** | artifact named; target is the section it lands in plus `*new*`, or `*new*` alone when the section is itself new |
| `Skipped` | a scope modifier excluded the artifact this target sits in | both named, so `## Scoping` can say what was left out |
| `Withheld` | an unresolved 1.1 conflict withheld the item, the Step 2 approval answer left it out, or the constitution states flow-forward (0.2) | both `—` |
| `None` | the item reaches no target at all | both `—` |

**`Add` and `Amend` are separated by the entry, not by the section.** A new bullet, requirement or route inside a section that already exists is still a **new entry**, so it is `Add`; the section being old changes nothing. `Amend` is only for a row that rewrites an entry the citation ladder can already name. This is the distinction the counts turn on, and reading "the section exists, so it is an amendment" is what makes two runs publish different numbers for identical edits.

Two items take **exactly one row regardless of how much they would have touched**, because nothing about them is being previewed: an item **withheld** by a conflict, by the approval answer or by a flow-forward constitution, and an item that reaches **no target at all**.

**`tasks.md` takes no rows here.** This table previews which existing entry an amendment lands on; a remediation task is always new and has no entry to preview, and the Sync Impact Map above already names every task this run will generate. An item whose only output is a task therefore has no row, and is **not** counted as reaching no target, since it reached one, just not one this table previews. When that happens, say so on a **second line directly below the counts line**, beginning `note:`. That line is the only free text permitted there, and the counts line itself always keeps its fixed shape.

```markdown
### Targets
| # | Item (from the gap report) | Category | Artifact | Target | Action |
|---|---------------------------|----------|----------|--------|--------|
| 1 | Export runs but nothing links to it | Wiring & Navigation | `plan.md` | Project Structure → *new* | Add |
| 2 | Export runs but nothing links to it | Wiring & Navigation | `plan.md` | Technical Context → "Target Platform" | Amend |
| 3 | Export runs but nothing links to it | Wiring & Navigation | `spec.md` | FR-014 | Amend |
| 4 | Locale header now required | Contracts | `spec.md` | Functional Requirements → *new* | Add |
| 5 | Locale header now required | Contracts | `plan.md` | Technical Context → "Primary Dependencies" | Amend |
```

Rows 1 and 2 are the same item in the same artifact, landing on two different entries. That is the ordinary case — a new endpoint usually touches routing, contracts and testing together — and it is why the unit is the target rather than the artifact.

Row 1 is the case the rule above decides: the plan's `Project Structure` section exists but has no entry for this path, so the row **creates** an entry and is `Add`, with the section named beside `*new*`. Row 2 is the contrast: the `Target Platform` entry already exists and its text changes, so it is `Amend`. Row 4 is `Add` in a section that also already exists, which is why its target cell names that section too. **Every `Add` row names its section unless the section is itself new**; there is no bare-`*new*` form for an entry landing in a section that exists.

**This example is illustrative, not a template.** Its section names come from a stock `plan-template`; a project that added `Routing & Navigation`, `Integration Contracts` or `Testing Strategy` routes the same drift into those instead, per 4.2. Never copy these rows as targets: the drift in front of you decides them.

**State the counts** below the table. Every count except the first is in **rows**, so there is one unit boundary and it is stated once. This line is printed **twice per run, by design**: here as the preview, and again in Step 5 as the outcome. They are not a duplicate: a difference between them *is* the divergence Step 5 has to report, and a run whose two lines disagree without saying why has hidden the one thing the preview exists to expose:

```
normalized items: M (items) — the rest count rows: targets R; amend K; add N; skipped S; withheld W; no target Z
```

`K + N + S + W + Z = R` exactly. `M` counts items and is never added to any of them; it can be larger than the row count (items whose only output is a remediation task, which take no row at all) or smaller (one item with many targets), and neither is an error. **An item reaching no target is not one of those cases**: it takes exactly one `None` row, so it leaves `M` and `R` in step. A zero must be legible as "examined and found nothing to amend", never as "did not look", because an artifact left unchanged is a finding about the drift, not an absence of work.

**`M` is a judgment, so state it rather than only printing it.** How finely a report splits into items is not decidable from the text: "the board lets two people co-own a task **and** the API accepts a second `owner_id`" is one drift or two, and either reading is defensible. The row counts are reproducible because their unit is fixed; `M` is not, and no rule here can make it so. Where a report's sentence could reasonably split, **say under `## Defaults Applied` how you counted and why**, so a reader comparing two runs sees a stated choice instead of an unexplained difference. A run that splits differently from another run is not wrong; a run that leaves the reader guessing which it did is.

Step 4 writes exactly this table. Where Step 4 discovers **at write time** that a target previewed as `Amend` is not viable after all, it adds a new entry instead and names the divergence in the report; that is a preview that turned out wrong, and it is not the same thing as the `None` row above, which records an item that reached no target when the preview was made.

---

## Step 4: Reconciliation (Surgical Edits)

**Constraint**: Operate strictly in place. Do not create branches, switch branches, or run feature-creation scripts. All edits target existing files in `FEATURE_DIR`.

**Scope**: skip any artifact excluded by a scope modifier, and name it in the Sync Impact Report. Out of scope means **not written**, never not read. This rule governs 4.1, 4.2 and 4.3 alike.

**Withheld items are written nowhere.** An item whose 1.1 conflict went unresolved, or that the Step 2 approval answer left out, and every item when the constitution states flow-forward (0.2), is skipped by 4.1, 4.2 and 4.3 alike, exactly as if the gap report had not named it, and appears in the report instead.

**The citation ladder.** Wherever this command has to identify an existing item — in the Step 3 target table, in a revision note, in the report — name it by its **ID** (`FR-014`, `SC-003`, `T045`); if it has none, by its **quoted heading or opening phrase** (`"Card declined mid-checkout"`); and only if no stable phrase exists, by its file alone. **A bare section name is never acceptable** (`Edge Cases` names a section, not an item, so it identifies nothing).

**Idempotency — the key is a slug**, a short hyphenated name for the drift being fixed (`settings-nav-link`). Derive it from the gap report, but first read the `[Sync: ...]` tags already in `TASKS_FILE` and the revision notes already in `spec.md` and `plan.md`: **if one of them names the same drift, reuse that slug rather than minting a new one.** A refined report describing the same problem must produce the same key, otherwise the whole mechanism misses in the one case it exists for. The date is metadata, never part of the match.

**Idempotency is judged per artifact, not per run.** Scope modifiers mean a slug can be present in `tasks.md` while `spec.md` has never been touched under it, so check the artifact you are about to write rather than another on its behalf.

When the slug is already present in the artifact you are writing, update what that earlier run wrote, since the revision note's `Items:` line names exactly which entries those were, rather than appending beside it. **The `Items:` line is a record of what *was* amended, not an instruction about where to amend now.** When an entry it names has since been marked `SUPERSEDED by [ID]` or `RETIRED`, 1.2 wins: follow the marker to the live entry, amend that, and extend the `Items:` line to name it. Never strike the historical entry out of the line, and never revive it.

**Update an earlier run's entry only where the current gap report changes what it says.** A judgment the earlier run made that this report does not touch, such as a task path it could not resolve, a placement or a wording, is not revisited on a re-run, and no discretionary question is asked about it. That is what keeps the same report, run twice, from changing anything the second time.

Two limits on "update":

- **Never edit a task marked `[X]` or `[x]`.** `__SPECKIT_COMMAND_IMPLEMENT__` marks completed work that way, and rewriting a finished task silently changes the record of what was done. If the refined report changes such a task, leave it and append a new one describing the remaining work, unless a later open task already carries this slug and covers that work, in which case it was appended on an earlier run and nothing more is needed. A task annotated `(reopened — BUG-NNN)` is not completed work (1.2), but it is not yours to edit either.
- Never delete a task an earlier run created. If the refined report drops it, leave it in place and say so in the report; removing work items is the user's call.

A re-run that finds everything already applied is a valid outcome. Report it and change nothing.

**A section the drift reaches but the artifact lacks** is created, in the position the project's own template puts it, so `## Assumptions` goes after the Success Criteria **section**, matching `spec-template`'s order, and after that section's content rather than immediately after its heading line. **This rule covers `plan.md` as well as `spec.md`**; resolve `plan-template` for a plan section exactly as `spec-template` is resolved for a spec one. Templates are readable for exactly this, per Allowed Sources, and that section also states **how** to read one: through the resolver, so a preset that reorders the sections is honoured rather than silently overridden by the base file.

**When the artifact renames its sections, map by role, not by name.** 4.1 already requires following the project's own headings, so a spec whose Success Criteria section is called `## How We'll Know It Works` puts the new section **after that section's content, before the next heading of equal or higher level** — after the section, never immediately after its heading line, which would nest the new section inside it. Match on what a section is *for*, never on its wording. When no section in the artifact plays the role the template's neighbour plays, append the new section at the end of the file and say so in the report, so the placement is a stated choice rather than a silent one.

Name every section created this way in the report — a new heading in someone's spec should never be a surprise.

**Revision notes.** Their place and form are fixed, because later runs **read** them: the slug match above depends on finding one an earlier run wrote, and the `Items:` line is what makes a re-run amend the right entries instead of guessing from prose.

```markdown
## Revisions

### Revision: Implementation Sync 2026-08-14 [Sync: settings-nav-link]
- Reason: [Summary of drift reconciled]
- Items: [each entry this run amended or added, by the citation ladder]
- Approved: [the approval behind these items: "approve all", or the approved items by name; never an item that was not approved]
```

The date and the slug above are **filled in, not copied**: write the ISO date bare, with no surrounding brackets. Only `[Sync: ...]` keeps its brackets, because they are part of the tag this command matches on. The three bracketed lines below the heading are placeholders to replace.

**The `Approved:` line is the record of the team's decision**, and it is what makes the note more than a log of edits. It names approved items only: a withheld item is written nowhere, and that includes this line, so under a partial approval it lists the approved items rather than quoting the answer. Like the date, it records the first approval for the slug: a re-run under the same slug extends it only when the same run writes to an entry under this slug (a new entry on the `Items:` line, or a rewrite of one it already names, meaning a change to that entry's text; re-applying identical text is not a write), by appending `; YYYY-MM-DD: ` and the approval behind the entries this run added or rewrote, and never rewrites the text already there, so a re-run that changes nothing leaves no diff. A note written before this line existed gains it the first time this command amends that note, starting with `YYYY-MM-DD: ` and this run's date, since the note's heading carries an earlier run's date and the approval is this run's.

**That form governs a note this run writes fresh, and nothing else.** An earlier note carrying a bracketed date (`### Revision: Implementation Sync [2026-08-11] …`) keeps its heading line **byte for byte** when this run amends it, brackets included. Amending such a note means changing its `Reason:`, `Items:` and `Approved:` lines only. Normalising the date would edit a line the rule directly below forbids rewriting, and would do it for appearance rather than for content, so a re-run that changes nothing would still produce a diff.

- **The notes live under a single `## Revisions` heading at the bottom of `spec.md` and `plan.md`**, created on first use, with each run's note a `### Revision: ...` entry inside it. The heading level matters: an unhosted `###` block appended to the bottom of a file renders as a **subsection of whatever section happens to be last** — `## Assumptions` in a spec, `## Constitution Check` in a plan — which is the opposite of "at the bottom", and makes the note read as part of a section it has nothing to do with.
- **Where an artifact already carries bare `### Revision:` entries at the bottom** with no `## Revisions` heading above them, written before this rule existed, **add the heading above them** when this run writes or amends a note in that artifact; a run that writes no note there leaves the file untouched. This is the one retroactive edit this command makes, and it is permitted because it moves no note, changes no note's text and changes no date — it only stops every future note from nesting inside the last section. Say so in the report.
- Consecutive notes read **newest last**, so they read in run order.
- **Never rewrite an earlier note**, with one exception: the note carrying **this run's slug**, which is amended in place rather than duplicated. Its date records the first sync for that slug and is never updated, so a re-run that changes nothing leaves no diff.
- Where the artifact already carries revision notes in some other place or form (an older `## Revision History` section, trailing comment lines), **leave them exactly where they are**, start this block anyway, and name the split under `## Outstanding Items` so a reader knows to look in both. **Bare `### Revision:` entries at the bottom are not "some other form"**: the rule directly above owns them, and adding the heading is what happens. This bullet covers everything else.
- `tasks.md` gets no revision note: the `[Sync: ...]` tag on each task is the equivalent record. The tag does not carry the approval, so a task's approval is on disk only through a `spec.md` or `plan.md` note under the same slug. When this run writes tasks and no such note exists or is written (a `--tasks-only` run, or an item whose only output is a task), the printed `## Approval` section is the only record: say so under `## Scoping`.

### 4.1 Update Specification (`spec.md`)

**Detect the spec's actual section names and ID convention before editing, and follow what you find.** The sections below use the canonical names; a project may use its own.

**The header block above the first `##` heading is never edited.** Title, `**Feature Branch**`, `**Created**`, `**Status**` and `**Input**` are provenance, not content, and one of them carries load: in an epic, `**Input**` is where a sub-spec links back to its parent roadmap entry. Normalising a header you do not recognise breaks that link silently.

**Touch only the sections the gap report actually implicates.** This is a surgical amendment, not a spec rewrite.

- **Functional Requirements**: Amend the `FR-XXX` that states the changed capability, or add one continuing from the highest existing ID. Never reuse or renumber an existing ID. This is where behaviour drift belongs when it changes *what the system must do*, as opposed to how a scenario reads.
- **Acceptance Scenarios**: Amend an existing scenario, or add one, under the relevant `### User Story N`. Keep the Given/When/Then form the file already uses.
- **Edge Cases**: Add cases discovered during implementation, folding into an existing entry that describes the same failure mode rather than restating it.
- **Key Entities**: Add a new entity, or extend an existing one with new fields, rather than restating the entity.
- **Success Criteria**: Amend an `SC-XXX` whose target the shipped behaviour changed, or add one continuing from the highest existing ID.
- **Assumptions**: Correct an assumption the implementation invalidated, and add one the implementation now depends on.
- **User Scenarios**: Add a missing user story only when the drift is not covered by any existing one.
- **Revision Note**: **Only if one of the sections above was actually modified**, add or amend the note per the rules above. A spec this gap report did not touch gets no note.

### 4.2 Update Plan (`plan.md`)

**Detect the plan's actual section names before editing, and follow what you find**, exactly as 4.1 requires for the spec. The names below are the canonical ones and are **illustrative, not exhaustive**: a plan holds Summary, Technical Context, Project Structure, Configuration and others, and a drift that reaches one of those amends it like any other. What bounds this step is the drift, not this list.

**Touch only the sections the gap report actually implicates**, as in 4.1. A drift that reaches no plan section leaves this file alone entirely.

**Start from the sections a stock plan actually has.** The core `plan-template` ships `Summary`, `Technical Context`, `Constitution Check`, `Project Structure` and `Complexity Tracking`, and *not* the three names this step used to lead with. A plan that has none of those three is the ordinary case, not a deficient one, so reach for the existing sections first and create a new one only when the drift genuinely fits nowhere:

- **Technical Context**: contract, dependency and platform drift. In the stock template this is a **fixed `**Key**: value` block** (Language/Version, Primary Dependencies, Storage, Testing, Target Platform, Project Type, Performance Goals, Constraints, Scale/Scope), so an amendment changes the value of an existing key. Do not invent a key and do not append loose prose beneath it; drift with no matching key belongs elsewhere.
- **Project Structure**: new or moved files, modules and directories, including a route or component landing somewhere the plan does not list. This is where a path goes when no routing section exists.
- **Summary**: a change in approach the rest of the plan now reads against.
- **Complexity Tracking**: **gated**, since the template says to fill it only where the Constitution Check has violations that must be justified, and it is a violation table with fixed columns. A deviation belongs here only when it is a constitution deviation and can be written as a row. An ordinary implementation choice does not qualify.
- **Constitution Check**: only where a MUST rule requires the feature to *record* something and this is where the feature records it (see 1.1). Never to restate a verdict.

**Sections many projects add**, and which take the drift naturally when present, but which are created only under the missing-section rule, never assumed:

- **Routing & Navigation**: missing routes, endpoints, or UI wiring details.
- **Integration Contracts**: API schemas, request/response headers, or payloads.
- **Testing Strategy**: coverage for the newly identified gaps.

Where one of these is absent and the drift reaches it, prefer the stock section that plays the same role (a route belongs in `Project Structure` on a plan that has no routing section), and create a new section only when no existing one does. Creating three headings on a stock plan because this list names them is the failure this paragraph exists to prevent.

**Writing a routing entry whose path the report never named.** 1.1's reading rule says a gap report never supplies a path, so a drift can reach a routing section while naming no URL. Write the entry anyway, describing the surface in the report's own terms, and mark the path position with `[NEEDS CLARIFICATION: path not stated in the gap report]`. That is the same marker the rest of this command uses for a value it may not invent, it counts against the three-marker budget, and it leaves the author one thing to fill in. Do **not** invent a plausible path such as `/settings`, and do not silently omit the entry: the first writes a route nobody declared, and the second loses the drift.

- **Revision Note**: Add or amend a revision note if any section was modified, using the same rules as 4.1.

### 4.3 Update Tasks (`tasks.md`)
Create remediation tasks to close the drift.

If `TASKS_FILE` does not exist, create it now with a `## Remediation: Gaps` heading, and number from `T001`. Create it only at this point, and only if this step will actually write tasks into it.

**Task Formatting**:
`- [ ] T{NNN} [{story}] {action verb} {what} in {exact/file/path.ext} [Sync: slug]`

Use the user story tag the task belongs to; omit it for tasks landing in `## Remediation: Gaps`, which belong to no story. The `[Sync: ...]` tag is always appended and holds this run's slug and nothing else (for example `[Sync: settings-nav-link]`), so the same key appears in every artifact and it is everything after `Sync: `.

**Do not emit the `[P]` marker, and never strip it from a task you did not write.** In Spec-Kit it means "can run in parallel: different files, no dependencies", and `__SPECKIT_COMMAND_IMPLEMENT__` reads it to decide what to run together. A gap report cannot establish that a remediation is independent of the others, so omitting it on new tasks is always correct: they then run sequentially. Tasks written by `__SPECKIT_COMMAND_TASKS__` carry it legitimately, and removing it would change how they execute.

**Rules for Tasks**:
1. **Increment IDs**: Never reuse an ID and never renumber one. **Continue the allocation convention the file already uses** rather than assuming a dense sequence. Read the existing IDs and follow what you find:
   - **Dense and sequential** (`T001`, `T002`, `T003`), the common case: start from the highest `T###` plus one.
   - **Allocated in blocks** (`T1000`, `T1010`, … then `T2000`), a convention some projects adopt so an insertion never forces a renumber: take the next free slot **inside the block of the phase the task lands in**, not the global maximum, which would put the task inside a later phase's block. Two branches this leaves open, both decided here:
     - **A task landing in `## Remediation: Gaps` belongs to no phase and so has no block.** Open the next unused block above every block in use, and allocate inside it **starting at the block's own base**, at the file's existing stride. **Read the block size from the file rather than assuming one**: it is the interval between the bases already in use, so a file running `T1000`, `T2000` opens `T3000`, and one running `T100`, `T200` opens `T300`, not `T1000`. Assuming thousands on a file that allocates in hundreds skips every unused block in between and widens the IDs, which the width rule above forbids. Every remediation task on a block-allocated file takes this path, so it is the common case, not the edge one.
     - **A block with no free slot** takes the next unused block, by the same rule. Never spill into the following block, which belongs to another phase.

   Read the ID width from the file too. `T###` is the usual form, but nothing guarantees three digits, so match on `T` followed by digits rather than on exactly three of them, and write new IDs at the width the file already uses. Every ID present counts toward "highest", including tasks that are completed, reopened, or cancelled, because a retired ID is never handed out again.
2. **Phase Placement**: Place new tasks under the **existing** phase heading that covers the affected user story. Core `tasks.md` files write these as `## Phase N: User Story N - [Title] (Priority: PN)`. Match the heading that is already in the file; never invent a new one from the `[USn]` task tag, which is an inline marker and not a heading. If no existing phase fits, use the `## Remediation: Gaps` section at the end of the file, **creating it only if the file does not already have one**. An earlier run under a different slug may have created it; a second heading with the same name is never correct.

   **A `## Phase N: Convergence` heading is never a placement target.** `__SPECKIT_COMMAND_CONVERGE__` appends those sections and treats them as an append-only ledger of what it found; a remediation task written into one would read as convergence's own finding and would be indistinguishable from it on the next run. Skip such a heading when looking for a phase that fits, and fall through to `## Remediation: Gaps`.
3. **Exact Paths**: Every task MUST include an exact file path where the change is needed. The path comes from the gap report, from `plan.md`'s project structure, or from the read-only repository lookup **Allowed Sources** permits — in that order of preference, and never from invention.

   **A task that creates a file names the file it will create.** Most remediation edits an existing file, but a new test or a new module does not exist yet, and "confirm the path exists" cannot apply to it. Such a path is **derived, not invented, when the directory it sits in is one the plan's Project Structure declares or the repository already contains** — `tests/integration/navigation.test.ts` is derived when `tests/integration/` exists; `src/services/settings.py` is invented when nothing declares `src/services/`.

   When neither an existing file nor a declared directory gives a path, write the task naming its target without one and list it under `## Outstanding Items`.
4. **Mandatory Integration Test**: If you identified a **Wiring & Navigation** gap, you MUST add a task for an Integration Test to verify it — unless `tasks.md` is out of scope, in which case write nothing and name the omitted test under `## Scoping`.

---

## Step 5: Sync Impact Report

Output the final report. Use **absolute paths** for all file references.

```markdown
# Sync Impact Report

## Changed Files
[Only files this run actually wrote. Omit any that were skipped or unchanged; `## Scoping` accounts for those.]
| File (absolute path) | Change Summary |
|----------------------|----------------|
| `/absolute/path/to/spec.md` | Amended FR-014, one Acceptance Scenario |
| `/absolute/path/to/plan.md` | Updated Routing/Contracts |
| `/absolute/path/to/tasks.md` | Added [N] remediation tasks |

## Counts
[The counts line in the shape Step 3 defines. That section owns the format, and it is deliberately not restated here, because this template has now been left behind by a change to that line twice. These are the **outcome** counts, covering what was actually written, where Step 3's were the preview. When the two lines differ, print both and name what moved between them; when they match, say so in one clause. A zero here means examined and found nothing to amend.]

## Sources
[Confirm every change came only from the Allowed Sources. Declare the read-only repository lookup whenever it happened, naming what it resolved. Name anything you needed but could not find, and state that you did not reconstruct it or invent a path. If you consulted git to verify your own writes rather than to obtain content, say so here. When a section was created, say how the template was read: through the resolver, or by the direct-read fallback because the resolver was absent or failed.]

## Path Resolution
[`FEATURE_DIR` and how it was resolved. Note it when `{SCRIPT}` reported a different feature directory. When the script failed, name which 0.1 branch recovered `REPO_ROOT`: `SPECIFY_INIT_DIR`, or the walk-up from the argument. If `SPECIFY_INIT_DIR` was set but rejected for lacking `.specify/`, say that too. Otherwise "Resolved from argument".]

## Approval
[The Step 2 approval answer, quoted, then each normalized item with its disposition: approved, or withheld as not approved. For each item withheld as not approved, recommend `__SPECKIT_COMMAND_CONVERGE__`, which checks the code against the artifacts as they stand. Name any item the answer did not clearly name; it counts as not approved. Under flow-forward (0.2) the section takes a different form: quote the constitution sentence that states the model, say that no question was asked and every item was withheld by the persistence model, and recommend no converge here; the Next Step's specify bullet carries the routing. Apart from its `Withheld` row in the Targets table, this is the only place an item withheld as not approved is listed as withheld: `## Constitution Compliance` may name it only to record a finding on it as moot, and `## Next Step` only to carry its converge recommendation.]

## Constitution Compliance
[Every 1.1 finding with its disposition: the user's Step 2 answer, or why it is still unresolved. Name each withheld item, the rule it conflicts with, and the recommendation to resolve it and re-run. A finding the user closed ("not actually triggered", "accepted gap") belongs here too — a closed finding that appears nowhere is indistinguishable from one that was never raised. State plainly that an accepted gap is recorded nowhere but here, so a re-run will detect and ask again. Or "None".]

## Scoping
[Which artifacts were skipped due to scope modifiers, and which were left unchanged because an earlier run under this slug had already applied them. **For each skipped artifact, name what this drift would have written into it** — a skipped artifact is not "nothing happened", it is a known, named omission, and a reader who cannot see what was left out cannot decide whether to re-run. That includes any mandatory integration test not written, and any remediation task an obligation asked for that 1.1's carve-out suppressed. State the interpretation if the report's final words were one of the three modifiers. `REPO_ROOT` derivation belongs in `## Path Resolution`, not here.]

## New Remediation Tasks
[List the new tasks added, e.g.]
- **T045**: Add sidebar link in `src/components/Sidebar.tsx`
- **T046**: Update router in `src/router/index.ts`
- **T047**: Integration test: navigate to Settings in `tests/integration/navigation.test.ts`

[On a re-run, list what was already present and left unchanged, or "Already applied; no changes".]

## Outstanding Items
[Everything this run noticed and did not act on, in one place, in the section formerly called `Outstanding Decisions`, widened. Any item withheld by an unresolved constitution conflict, with the rule it conflicts with and the recommendation to resolve it and re-run. Any remaining `NEEDS CLARIFICATION` markers. Sections created because the artifact lacked them, and any section appended at the end of a file because no template position could be mapped. Tasks written without a path because none resolved. Struck-through text left as it stands because it had neither a Bugfix marker nor a replacement, and any overlap with a task reopened by a bugfix cycle. Any retired entry the gap report appeared to reach, any superseded entry the amendment was redirected away from (and the pair, where the named replacement could not be resolved), and any overlap with a cancelled task. Any open Convergence task that traces to an entry this run amended (1.2), with that entry. Any revision notes found in another place or form, with the split named. Each action-requiring constitution rule reported as unverified, with what would settle it. These are unverified, not violated. Any discretionary question the budget could not hold. Or "None".]

## Defaults Applied
[Any decision made with a reasonable default instead of asking, or "None"]

## Gap Report
[The gap report verbatim, and any part set aside because it asked for something the Gap Report Contract forbids, with the reason.]

## Next Step
[Recommend based on what changed. The first two bullets take precedence: under flow-forward print only the first (and the archive bullet when it applies); and when the second applies, print it before every bullet that recommends implement.]
- If the constitution states flow-forward → `__SPECKIT_COMMAND_SPECIFY__` to capture the change in a new feature directory, then deliver it through the normal loop. Recommend nothing else for the withheld items.
- If an open Convergence task traces to an entry this run amended or this slug's revision note names (1.2) → **first** resolve or close that task, and only then run any `__SPECKIT_COMMAND_IMPLEMENT__` recommended below; name the task here
- If remediation tasks were added → `__SPECKIT_COMMAND_IMPLEMENT__` to execute them, then `__SPECKIT_COMMAND_CONVERGE__` to check the code against the updated artifacts
- If an artifact changed and no remediation task was added → `__SPECKIT_COMMAND_CONVERGE__` to check the code against the updated artifacts
- If an item was withheld as not approved → `__SPECKIT_COMMAND_CONVERGE__` to check the code against the artifacts as they stand
- If at least one item was approved and no artifact changed because everything approved was already applied (whether or not something was also withheld) → `__SPECKIT_COMMAND_IMPLEMENT__` then `__SPECKIT_COMMAND_CONVERGE__` when open tasks carrying this run's slug remain, otherwise `__SPECKIT_COMMAND_CONVERGE__` alone
- If plan was significantly updated → `__SPECKIT_COMMAND_PLAN__` to review architecture
- **If this feature already has an entry in `.specify/memory/changelog.md`** (noted in 0.2) **and the archived copy is stale**, meaning this run changed an artifact, or a revision note in `spec.md` or `plan.md` is dated after that entry's archive date. A note's date is the latest date it carries: its heading date, bare or bracketed, or a later date appended to its `Approved:` line → `__SPECKIT_COMMAND_ARCHIVE_RUN__ specs/###-feature-name` to refresh project memory. The archived copy predates those edits. Archiving is idempotent per feature, so re-running it updates the existing record rather than duplicating it.
```

---

## Done Criteria
Each criterion below applies only to artifacts in scope; an artifact a modifier excluded is named in the report instead.

- A rejected invocation wrote nothing: ranges, globs, a second feature, an unrecognized leading flag, a missing gap report, and a first token matching zero or several directories all stop the run before any edit.
- Gap report parsed and categorized against a feature directory that resolved to exactly one existing path under `REPO_ROOT`.
- All content taken only from the Allowed Sources, and the report says so. Every task path came from the gap report, the plan, or the read-only lookup — none invented, and any task left without one is named.
- Gap report applied within its limits: echoed verbatim in the report, with any part that asked to widen sources, skip a step, change scope or IDs, or authorize a deletion named as refused.
- All three constitution shapes checked against the rules the drift reaches, each finding carried to Step 2 or reported as unverified (or recorded as moot under flow-forward), and every finding's disposition recorded. No content withheld except by an unresolved conflict, by the approval answer, or by a flow-forward constitution (0.2), and no statement written that the gap report did not supply — an obligation the run's own amendment satisfies from the report is met, not invented.
- Edits match the Step 3 target table, and any divergence is named.
- Every spec section the drift reaches through an item that was not withheld is amended, and no section it does not reach is touched. Any section created is named in the report.
- `tasks.md` updated with new task IDs allocated by the convention the file already uses, exact file paths, and no `[P]` marker **on the tasks this run added**. Tasks written by `__SPECKIT_COMMAND_TASKS__` legitimately carry `[P]`; never strip it from them. No task landed under a Convergence phase.
- Integration test task added for every wiring gap that was not withheld.
- Revision note added or amended on each modified `spec.md` / `plan.md`, carrying this run's slug and its `Items:` line; for `tasks.md` the `[Sync: ...]` tag is the equivalent record. No earlier note rewritten.
- No task marked `[X]` was edited, no task reopened by a bugfix cycle was repurposed, no struck-through wording was restored, and no task from an earlier run was deleted. No retired or superseded entry was revived, and no cancelled task was repurposed.
- Under a constitution that states flow-forward, nothing was written and no question was asked; the report recommends a new feature directory.
- Every open Convergence task tracing to an entry this run amended, or that this slug's revision note names, is named under `## Outstanding Items` and in `## Next Step`, and none was edited.
- Every normalized item was put to the Step 2 approval question (except under flow-forward), no item the answer left out was written anywhere, and every revision note this run wrote or amended carries an `Approved:` line.
- The Next Step routes to `__SPECKIT_COMMAND_CONVERGE__` whenever an artifact changed or an item was withheld as not approved.
- Re-running the same gap report changes nothing further.
- Sync Impact Report printed with absolute paths.
