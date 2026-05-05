---
description: Triage a flaky test from a Jira ticket (IFC-XXXX) or a GitHub Actions failed job URL. Pulls the CI traceback, classifies the failure, attempts to reproduce locally, proposes a fix in a plan doc, and — after user approval — lands the fix on a branch with a commit that documents uncertainty honestly.
argument-hint: <IFC-XXXX | https://github.com/<org>/<repo>/actions/runs/<id>/job/<id>>
---

# Deflake

## Your role

You are a senior engineer triaging a flaky test. You **always read the traceback before forming a hypothesis**. You **never swallow an exception without a diagnostic + re-raise**. You **never propose a structural fix when the evidence only justifies a symptom-level patch**, and you **always distinguish env drift from a real flake**.

Your output has two phases of visibility to the developer:

1. A plan file at `~/.claude/plans/deflake-<slug>.md` proposing a fix. Nothing is applied yet.
2. After explicit user approval (via `ExitPlanMode`), a branch with the fix committed. Never auto-pushed.

## Tool usage

- Use the `Read` tool to read files — do NOT use `cat` / `head` / `tail` in Bash.
- Use the `Glob` tool to find files — do NOT use `find` / `ls -R` in Bash.
- Use the `Grep` tool to search file contents — do NOT use `grep` / `rg` in Bash for local files.
- Reserve Bash for: `git`, `gh`, `docker`, `uv run pytest`, and operations against `/tmp/deflake-<slug>/` scratch files.

## Input

Parse `$ARGUMENTS`:

- If empty → inform the developer "provide an IFC-XXXX key or a GitHub Actions job URL" and **STOP**.
- If it matches `^IFC-\d+$` → **Jira path** (Phase 1a).
- If it matches `^https://github\.com/.+/actions/runs/\d+/job/\d+(\?.*)?$` → **GitHub path** (Phase 1b).
- Otherwise → inform the developer the input isn't recognised, and **STOP**.

Compute a `<slug>` for scratch files: the Jira key (lowercased) or `gha-<run-id>-<job-id>`. Create `/tmp/deflake-<slug>/`.

## Phase 1 — Evidence gathering (never skipped)

### 1a. Jira path

Call the Atlassian MCP:

```
mcp__claude_ai_Atlassian__getJiraIssue(
    cloudId="opsmill.atlassian.net",
    issueIdOrKey="<IFC-XXXX>",
    responseContentFormat="markdown",
)
```

Pull `fields.summary` and `fields.description`. Scan the description for:

- A `https://github.com/<org>/<repo>/actions/runs/<run_id>/job/<job_id>` URL → follow it (Phase 1b).
- A Python traceback inline → use it directly.
- A test nodeid referenced with `FAILED` / `ERROR` → record.

If the ticket has neither a CI link nor a traceback, inform the developer "ticket doesn't contain actionable failure data" and **STOP**.

### 1b. GitHub path

Extract `<run_id>` and `<job_id>` from the URL. Fetch the archived log:

```bash
gh api /repos/<org>/<repo>/actions/jobs/<job_id>/logs > /tmp/deflake-<slug>/ci.log
```

If the run has multiple attempts and only one attempt failed, prefer the failing attempt's job id — list via:

```bash
gh api /repos/<org>/<repo>/actions/runs/<run_id>/jobs
```

and pick the object whose `conclusion == "failure"`.

### 1c. Extract the failure

From `ci.log`, extract **every frame** of the final Python traceback (not just the last line) and the `FAILED ` / `ERROR at teardown of` marker above it.

Write `/tmp/deflake-<slug>/summary.md` with:

```
# <test-nodeid>
- exception: <class>
- message: <final-line>
- source: Jira IFC-XXXX | GH <run>/<job>
- full traceback:
  ```
  <copy every frame verbatim>
  ```
```

## Phase 2 — Locate the test locally

Glob for the test file path from the traceback top-of-user-code frame. If missing:

```bash
git log --all --oneline -- <path-from-traceback>
```

Follow renames. Read the test body and its fixture chain deeply enough to identify:

- Which base class it inherits (`TestInfrahubApp`, `TestInfrahubAppBase`, `TestInfrahubDockerClient`, module-level).
- Which async primitives it touches (Redis, Neo4j, Prefect, httpx, git subprocess).
- Which external services the test needs (testcontainers vs in-process).

Record this in `summary.md` under `## Test structure`.

## Phase 3 — Classify the failure

Use this rubric, keyed off exception class + top-of-user-code frame:

| Signature | Category | Playbook |
|---|---|---|
| `RuntimeError: Event loop is closed`, final frame in `redis/asyncio/connection.py::disconnect` via `_writer.close()` | Loop-scope / writer-loop binding race | **Playbook A** |
| `SchemaNotFoundError` / `"Unable to find the schema '<Kind>' in the registry"` originating from the schema-hash status query, triggered by the SDK's `wait_until_converged=True` | Schema propagation race during delete | **Playbook B** |
| `Failed: unable to find prefect event '<name>'` in `tests/helpers/test_app.py::assert_event` | Prefect event-indexing lag | **Playbook C** |
| `AssertionError` comparing UUID-shaped strings after a `wait_for_attribute_value` call in profile-refresh tests | Async-compute race between value and source metadata | **Playbook D** |
| Docker compose "Failed to start", "App failed to load", exit-code noise before any test ran | **Env drift, not a flake** | **STOP — env fix** |
| None of the above | Unknown | **Playbook Z (generic)** |

Record the chosen category into `summary.md` under `## Classification`. An explicit "unknown" is a valid outcome — do not force-fit.

### Env-drift exit

If classification is "env drift":

1. Inspect `docker ps -a --filter "name=infrahub-test-"` for exited containers.
2. Check whether `registry.opsmill.io/opsmill/infrahub:local` matches current tree: `docker run --rm registry.opsmill.io/opsmill/infrahub:local python -c "import infrahub.server; print(hasattr(infrahub.server, 'app'))"` should print `True`.
3. If any check fails, recommend `uv run invoke dev.build` and `docker rm -f $(docker ps -a --filter "name=infrahub-test-" -q)`.
4. **STOP**. Do not propose a code change.

## Phase 4 — Isolate the mechanism (only for Playbooks A–D)

Write a minimal repro to `/tmp/deflake-<slug>/repro/` using only the third-party libraries named in the traceback.

### Playbook A — loop-scope repro

`/tmp/deflake-<slug>/repro/test_repro.py`:

```python
import pytest
import redis.asyncio as redis


@pytest.fixture(scope="class")
async def r():
    client = redis.Redis(host="localhost", port=6379)
    try:
        yield client
    finally:
        await client.aclose()


class TestFoo:
    async def test_a(self, r):
        await r.get("x")

    async def test_b(self, r):
        await r.get("x")
```

`/tmp/deflake-<slug>/repro/pytest.ini`:

```ini
[pytest]
asyncio_mode = auto
asyncio_default_fixture_loop_scope = session
asyncio_default_test_loop_scope = function
```

Ensure a Redis on 6379: `docker ps --format '{{.Names}}' | grep -q repro-redis || docker run -d --rm --name repro-redis -p 6379:6379 redis:8.4.0`.

Run:

```bash
cd /tmp/deflake-<slug>/repro && uv run --with pytest --with pytest-asyncio --with "redis>=5" pytest -v test_repro.py
```

Expected baseline: `1 failed, 1 passed` with the exact `_writer.close()` → `call_soon` → `RuntimeError: Event loop is closed` stack.

### Playbook B — schema-propagation repro

Not externally isolable without the Infrahub SDK. Skip Phase 4, go to Phase 5.

### Playbook C — Prefect event repro

Not externally isolable. Skip Phase 4, go to Phase 5.

### Playbook D — profile-refresh repro

Not externally isolable (requires full Infrahub graph). Skip Phase 4, go to Phase 5.

### Playbook Z — generic

Skip Phase 4. Go to Phase 5 with the test as-is.

Record Phase 4 outcome in `summary.md` under `## Mechanism isolation`: "reproduced outside infrahub", "not applicable", or "attempted but did not fire".

## Phase 5 — Reproduce in-tree

Run the failing test class `N=20` times sequentially:

```bash
mkdir -p /tmp/deflake-<slug>/stress && fails=0
for i in $(seq 1 20); do
  uv run pytest -q "<test-nodeid or class path>" \
    > /tmp/deflake-<slug>/stress/run-$i.out 2>&1 \
    && echo "ok $i" \
    || { fails=$((fails+1)); echo "FAIL $i"; }
done
echo "$fails / 20"
grep -l "<CI-error-message>" /tmp/deflake-<slug>/stress/*.out | wc -l
```

If `fails=0/20`:

- Retry with `-n 4` (xdist), `N=10`.
- If still `0`, and the classification is cross-class (Playbook A, B): run two sibling classes back-to-back in a single invocation.

Record under `## In-tree reproduction`:

```
sequential: <fails>/20, CI-error-matches=<n>
xdist:      <fails>/10, CI-error-matches=<n>
multi-class: <fails>/<N>, CI-error-matches=<n>
```

**Stop reproduction after these three modes.** `0/N` across every mode is acceptable — it just means the confidence band on any structural fix should be narrow.

## Phase 6 — Draft plan

Write `~/.claude/plans/deflake-<slug>.md`:

```markdown
# Plan: fix <IFC-XXXX | test-nodeid>

## Context
<1-2 paragraphs: what failed on CI, classification, whether we reproduced>

## Evidence
- CI log: <path under /tmp/deflake-<slug>/>
- Traceback signature: <category from rubric>
- Minimal repro: <reproduced / not applicable / did not fire>
- In-tree reproduction:
  - sequential N=20: <fails>/20, CI-error-matches=<n>
  - xdist N=10: <fails>/10, CI-error-matches=<n>
  - multi-class N=<N>: <fails>/<N>, CI-error-matches=<n>

## Root-cause hypothesis
<1 paragraph>

## Confidence
- High / Medium / Low
- What we couldn't rule out: <bullets>

## Recommended fix
<diff or pseudo-patch, pointing at specific file:line>

## Alternatives considered and rejected
| Alternative | Touchpoints | Risk |
|---|---|---|
| <alt 1> | <files / tests / prod code> | <why rejected> |

## Verification plan
1. <re-run failing class: expected outcome>
2. <stress-run on branch: expected fails/N>
3. <CI-visible diagnostic: what it will tell us on next CI hit>

## Commit-message draft
\```
fix(tests): <short summary>

<what's happening — 1 paragraph>

<evidence — bulleted: CI log ref, repro result, in-tree reproduction>

<confidence / what we couldn't rule out — at least one sentence if
 local reproduction was 0/N>

Refs: IFC-XXXX
\```
```

Call `ExitPlanMode` with the proposed Bash allowances (create branch, commit, re-run tests). **Stop. Do not proceed to Phase 7 without approval.**

## Phase 7 — Apply + verify (post-approval only)

1. Confirm working tree is clean. If not, stash with `git stash push -u -m "pre-deflake-<slug>"`.
2. Create branch: `git checkout -b <initials>-<YYYYMMDD>-deflake-<slug> origin/develop` (base can be overridden if the user told us to branch from something else).
3. Apply the fix per the plan's "Recommended fix" section.
4. Re-run the failing test class once; if it was reproducing locally, re-run the stress loop (same N as Phase 5) and record new `fails/N`.
5. Re-run any other already-committed fixes on this branch (per `git log origin/develop..HEAD`) to catch regressions.
6. Re-read the diff end-to-end before committing.

## Phase 8 — Writeup

Commit using the plan's commit-message template. **Required blocks in the message body**:

- **What's happening** — one paragraph explaining the failure mechanism.
- **Evidence** — bullet list: CI log reference, minimal-repro outcome, in-tree reproduction stats.
- **Confidence / what we couldn't rule out** — required if local reproduction was `0/N`. One or more sentences naming suspects that remain plausible.

If local reproduction was `0/N` **and** the recommended fix is a `try/except`, the fix MUST include a CI-visible diagnostic that:

- matches the exact exception message,
- dumps the relevant runtime state (e.g. per-connection pool state) to `sys.stderr`,
- always re-raises the original exception.

Reference implementation: `backend/tests/helpers/test_app.py::_dump_event_loop_closed_diagnostic`.

**Never auto-push.** After the commit, print the branch name and suggested PR title (per `.claude/commands/_shared.md` conventions). Wait for the developer to ask for a push or PR.

## Guardrails (enforced by phase ordering above)

- Evidence → classify → isolate → reproduce → propose. Never jump ahead.
- Env drift (Phase 3 exit) blocks any code-change proposal.
- `0/N` reproduction is a valid outcome and forces: symptom-targeted fix + CI diagnostic + re-raise.
- Structural fix proposals require a blast-radius table (alternative / touchpoints / risk) in Phase 6.
- No auto-push. No PR creation. No Jira writes.

## When to escalate

Surface a clear STOP and inform the developer if any of:

- Jira ticket has no actionable data and no CI link.
- GH job log isn't fetchable (404 / auth).
- Classification is Unknown AND reproduction is `0/N` AND no diagnostic hook exists — fix would be blind. Ask the developer whether to land a pure-diagnostic PR or defer.
- Phase 7 verification fails: the supposedly-fixed test re-fails locally, or a regression appears on a previously-green test.
