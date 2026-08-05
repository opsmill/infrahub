# Investigation

These are the shared investigation steps for bug analysis.
Read this file when directed by your main prompt.

## Read prior findings

Fetch the full comment history of the issue before anything else:

```bash
gh issue view <number> --comments
```

- If a previous analysis exists and was **refuted downstream** (by the test-writer,
  the reviewer, or a human), treat that mechanism as disproven. Do NOT restate it.
  Your analysis must either identify a different root cause or conclude
  NOT REPRODUCIBLE (see below).
- If the issue carries `state/needs-human-test` or `state/not-reproducible`, read the
  comment that set it and reconcile your analysis with that evidence.

## Issue clarity check

Verify the issue has enough information to work with:

| Required | Description |
|----------|-------------|
| **Clear problem statement** | Can you understand what the bug actually is? |
| **Reproduction path** | Are there steps to reproduce, OR can you infer them from the description? |
| **Expected vs actual** | Is it clear what should happen vs what happens? |

Rate the clarity:

- **CLEAR**: intent, reproduction scenario, and expected behavior are understandable (even if some details like affected release are missing).
- **UNCLEAR**: the intent and reproduction scenario are not understandable.

If the bug is UNCLEAR, **STOP** here and escalate as described in your main prompt.

## Environment provenance check

If the report names a version, revision, commit SHA, or image digest, verify it before
trusting any observation in the report:

1. Resolve the reported revision to a commit: `git log -1 <sha>`.
2. Check where it sits: `git merge-base --is-ancestor <sha> origin/develop` (and `origin/stable`).
3. Verify the described feature/UI **exists at that revision**: `git ls-tree <sha> -- <path>`
   and `git grep <pattern> <sha> -- <path>` for the components the reproduction steps use.
4. If an **image digest** is reported, inspect its labels NOW, even if you do not need
   them yet -- moving tags (`develop`, `stable`) get garbage-collected and the digest may
   be gone within weeks, taking the only ground truth about the build with it:

   ```bash
   docker buildx imagetools inspect registry.opsmill.io/opsmill/infrahub@<digest> \
     --format '{{json .Image.Config.Labels}}'
   ```

   Record the label output (or "digest no longer available") in the analysis. If the
   labels' revision disagrees with the revision stated in the report, say so explicitly --
   the labels win.

Rate the provenance:

- **CONSISTENT**: the reported build contains the code the reproduction steps exercise.
- **INCONSISTENT**: the reported build cannot have produced the described observations
  (for example, the UI element in the steps does not exist at that revision).
- **UNKNOWN**: no environment information was provided.

An INCONSISTENT environment does not end the analysis -- the defect may still exist on
current code -- but it means the report's observations and suspected locations carry
little weight and everything must be re-derived from the current revision.

## Investigate the codebase

1. Read root `AGENTS.md` and `dev/documentation-architecture.md` in order to determine which code packages are related to the issue. Then:
   - If you can determine the code package related to the bug, rate the code identification step as RESOLVED.
   - If you cannot determine the code package related to the bug, rate the code identification step as EXPLORATION REQUIRED, and explore the code base.

2. Read the relevant source files in the affected area to understand the current behavior.

3. Treat reporter-provided hypotheses ("suspected location", "likely candidates",
   "implementing PR") as **data to confirm or refute**, never as conclusions. Verify them
   independently and look beyond the named files -- the reporter's pointer is wrong often
   enough that an analysis confined to it is not an analysis.

4. For **frontend bugs**, trace the full data path segment by segment and name each
   segment explicitly, for example: component state -> form submit -> URL/state
   serialization -> API layer -> GraphQL document/variables. Identify which segment
   breaks. Do not stop at the component the reporter pointed at: a value that is correct
   in the component can still be lost in a later segment, and vice versa.

5. Identify the most likely root cause(s) -- point to specific files and lines.
   - If you **cannot** identify a root cause after exploration, **STOP** and escalate
     as described in your main prompt.

## Verify the root cause

A named mechanism is a hypothesis until it survives this section.

1. **Attempt the cheapest available observation.** You are required to attempt at least
   one; pick the cheapest that can show the defect:
   - Run the existing tests that cover the affected code
     (`uv run pytest <path> -x -q`, `cd frontend/app && pnpm run test <path>`).
   - Exercise the suspect function directly: a scratch pytest/vitest file, a
     `node -e`/`python -c` one-liner for pure functions, or a scratch script.
     Scratch files must never be committed.
   - Frontend components can be driven for real in vitest browser mode -- render the
     component, interact, and read the value that comes out.
2. **Falsification pass.** Before writing the analysis, actively try to refute your own
   mechanism:
   - Verify the language/library semantics you rely on (for example: `new Date(dateObj)`
     copies the timestamp; a TypeScript `as` cast has no runtime effect).
   - Walk **both** branches of any conditional your mechanism depends on and confirm the
     bad branch is reachable with the reported inputs.
   - If the mechanism only fails under conditions you cannot produce, it is not the
     root cause -- keep looking.
3. Record the **Reproduction status** in the analysis:
   - **OBSERVED**: you saw the wrong behavior happen (failing scratch test, script
     output, test run). Include the evidence.
   - **INFERRED**: the mechanism is reasoned but was not observed. You MUST state the
     exact observation that would confirm it -- this becomes the test-writer's first task.
     INFERRED is acceptable when observation requires infrastructure you do not have
     (a running stack, external services), not when you skipped the attempt.

### NOT REPRODUCIBLE is a successful outcome

If your best mechanism fails the falsification pass and no observation shows the defect
at the current revision, the correct verdict is **NOT REPRODUCIBLE** -- not a
lower-confidence root cause. Producing a plausible-sounding mechanism for a defect that
is not there sends the whole downstream pipeline (test-writer, fixer, reviewer) chasing
a ghost; ruling the defect out is exactly as valuable as finding it.

A NOT REPRODUCIBLE analysis must include:

- each pipeline segment you verified and how (test run, scratch script, code walk),
- the environment provenance verdict,
- what observation, if any, remains unverified (for example: needs a full running stack),
- a recommendation: close, re-test on a current build, or escalate the unverified segment.

Escalate as described in your main prompt.

## Fix strategy

Formulate a fix strategy. This is NOT the exact code -- it is the recommended approach:

- **Approach:** What should the fixer do and where? Reference existing functions/methods
  that should be reused rather than reimplemented.
- **Scope:** Which files/functions need changes? How large should the change be?
- **Do NOT:** List common wrong approaches (e.g., adding a guard clause when the real
  fix is a missing validation, creating new abstractions when an existing one should be reused).

## Analysis template

Write the analysis output using this structure (replace all `<placeholders>`):

````markdown
## Root cause analysis for #<issue_number>

**Issue:** <issue title>
**Based on:** `<commit SHA of origin/stable>`
**Bug clarity:** CLEAR
**Environment provenance:** CONSISTENT | INCONSISTENT | UNKNOWN
**Code identification:** RESOLVED | EXPLORATION REQUIRED
**Reproduction status:** OBSERVED | INFERRED

### Root cause
<one-sentence summary>

### Affected files
- `path/to/file.ext` -- line X: <why this is the culprit>

### Explanation
<detailed reasoning>

### Verification
<OBSERVED: the evidence -- test/script output showing the wrong behavior.
INFERRED: the exact observation that would confirm the mechanism, and why it could
not be performed here.>

## Fix strategy

**Approach:** <recommended fix approach -- explain WHAT to do and WHERE, not the exact code>

**Scope:** <which files/functions should need changes, and roughly how large the change should be>

**Do NOT:**
- <guardrail 1 -- common wrong approach to avoid>
- <guardrail 2 -- unnecessary refactoring to avoid>

## Notes for downstream steps
<edge cases, risks, or constraints the test-writer and fixer should know about>
````

For a NOT REPRODUCIBLE verdict, use this structure instead:

````markdown
## Root cause analysis for #<issue_number>

**Issue:** <issue title>
**Based on:** `<commit SHA of origin/stable>`
**Bug clarity:** CLEAR
**Environment provenance:** CONSISTENT | INCONSISTENT | UNKNOWN
**Verdict:** NOT REPRODUCIBLE

### What was checked
- <segment or mechanism> -- <how it was verified: test run, scratch script, code walk>

### Remaining unverified
<observations that would require infrastructure not available here, or "none">

### Recommendation
<close | re-test on a current build | escalate the unverified segment>
````
