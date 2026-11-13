---
description: Produce a manual QA checklist that walks a human tester through verifying the just-implemented feature, written next to spec.md / plan.md in the active feature directory.
scripts:
  sh: ../../scripts/bash/check-prerequisites.sh --json --paths-only
  ps: ../../scripts/powershell/check-prerequisites.ps1 -Json -PathsOnly
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

Supported argument: `--force` to overwrite an existing `qa-checklist.md`
without prompting. Any other free-form text is treated as additional
scope guidance (for example: `focus on the CLI surface`, or
`skip the GraphQL queries`) and should bias the checklist accordingly.

## Goal

After the implementation phase of a spec-kit feature, produce a single
markdown document at `FEATURE_DIR/qa-checklist.md` that a human can
follow, step-by-step, to verify the feature works. The audience is a
teammate (or future-you) running the feature **the way a customer
would** — through the same surface customers touch (CLI, running
service, UI, public SDK, docs page). They need concrete,
copy-pasteable instructions — not a description of what the feature
does.

The checklist is **manual and customer-facing**. It does not run the
automated test suite, does not assert on internal state, and does not
include unit-test or integration-test invocations. Those belong in
`tasks.md`, CI, and `git log`. Snippets that import the project's
public, documented SDK or library are fine — they *are* the customer
surface for SDK-shaped features.

## Customer Frame

Test the feature **the way a customer would actually use it.** The
right surface depends on what kind of product the feature ships into:

| Product type | Customer surface |
|---|---|
| CLI tool / binary | The shipped command, its flags, its stdout/stderr/exit code |
| Service (SaaS / self-hosted) | Config files an operator edits, the running service's HTTP / GraphQL / gRPC API, UI flows, the logs and metrics it surfaces |
| Library / SDK | The public, documented import path — code a customer would write against the exported API |
| Code generator / template | The generated output, run from the user-facing entry point |
| Docs / examples | The rendered page or the runnable snippet |

**Writing code is fine — even necessary — when the customer is a
developer using a library or SDK.** A snippet that imports the
published top-level package and calls its public methods is exactly
the experience you ship. What is not fine is reaching past the public
API into internal modules, private helpers, test fixtures, or config
classes that the project does not document as part of its surface.

A useful test before emitting a step: *would I be comfortable
publishing this snippet verbatim in the feature's README, docs, or
release notes?* If yes, it is customer-shaped. If publishing it would
feel wrong because it touches internals, the step is implementation
testing, not QA.

## Operating Constraints

**STRICTLY ADDITIVE.** Do not modify `spec.md`, `plan.md`, `tasks.md`,
`research.md`, `data-model.md`, `contracts/`, or any source files. The
only file this command writes is `FEATURE_DIR/qa-checklist.md`.

**CUSTOMER SURFACES, NOT IMPLEMENTATION.** Every step must exercise
the feature through something a customer would publicly use. Decide
which product type the feature ships into (table above), then pick the
matching surface. Acceptable:

- A shipped CLI subcommand or binary (with the exact flags).
- A public HTTP / GraphQL / gRPC request against a *running* service
  (exact URL, method, body, expected response shape).
- A UI page or flow (with the exact navigation path and visible cues).
- A configuration file the operator edits, plus the user-visible
  signals that follow (logs from the running service, metrics, a
  status endpoint, observable behavior change in a public API).
- The public, documented import path of a library / SDK — using the
  same package and symbols the docs tell customers to use.
- A rendered docs page or a documented, runnable example.

Not customer surfaces:

- Private / internal modules, classes, helpers, validators, or
  fixtures that the project does not document as user-facing.
- `pytest` / `vitest` / `cargo test` wrappers presented as scenarios —
  CI runs those.
- Source-tree inspection ("open the file and confirm X is exported")
  — that is code review, not QA.

**Two worked examples.**

*Example A — a config flag on a self-hosted service `myapp`.* Customer
surface = config file + running service. Not customer-shaped:

```bash
# Touches Settings class — not in the published surface.
python -c "from myapp.config import Settings; print(Settings().new_flag)"
```

Customer-shaped:

1. Set `new_flag = true` in `myapp.toml`.
2. Restart: `docker compose restart myapp`.
3. Hit a public endpoint that reflects the flag:
   `curl -s localhost:8080/api/status | jq .new_flag` → `true`.

*Example B — a new `messages.batch.create()` method on a published
SDK.* Customer surface = the public import path. Customer-shaped:

```python
# The exact snippet a customer would copy from the docs.
from acme_sdk import Acme
client = Acme(api_key="...")
res = client.messages.batch.create(requests=[...])
print(res.id, res.status)
```

Both are valid QA. The difference is not "code vs. no code" — it is
whether the snippet uses a published, supported surface.

If the feature truly has **no** customer surface (pure refactor,
internal helper that is not re-exported, generator that produces no
visible change), say so in **Scope** and ship a minimal smoke
checklist (build still succeeds, nearest user-visible flow still
works, docs still render). Do not reach for internals to fill space.

**ONE FILE, IDEMPOTENT.** Re-running in the same feature directory
should produce a comparable checklist, not a diff of checklists. If
`qa-checklist.md` already exists, ask before overwriting unless
`--force` was passed.

## Outline

1. **Resolve the feature directory.** Run `{SCRIPT}` from repo root and
   parse `FEATURE_DIR` from the JSON output. All paths must be
   absolute.

   - If `FEATURE_DIR` is missing, empty, or the resolved directory does
     not exist, **fail fast** with:
     `No feature directory resolved from current branch — /speckit.opsmill.qa requires an active feature branch.`
     Suggest the user switch to a feature branch and re-run.

2. **Check for an existing checklist.**

   - If `FEATURE_DIR/qa-checklist.md` exists and `--force` was not
     passed, print the existing path and ask the user whether to
     overwrite, append a timestamped variant, or abort. Default is
     abort.
   - If `--force` was passed, overwrite without prompting but mention
     it in the final report.

3. **Gather context**, in this order of preference:

   a. `FEATURE_DIR/spec.md` — primary source for user-visible behavior,
      acceptance criteria, and scope.
   b. `FEATURE_DIR/plan.md` — entry points, surfaces touched (CLI,
      GraphQL, REST, UI, generators).
   c. `FEATURE_DIR/tasks.md` — what was actually built (use this to
      ensure the checklist matches reality, not the original spec).
   d. `FEATURE_DIR/quickstart.md` if present — re-use any setup steps
      verbatim rather than re-inventing them.
   e. `FEATURE_DIR/contracts/` if present — to identify exact endpoint
      names, mutation names, query names to exercise.
   f. The live conversation context for any clarifications or scope
      shifts that happened during implementation but did not make it
      back into `spec.md`.

   Do **not** read large swaths of source code. Do **not** generate
   diffs. The checklist is anchored to user-visible surfaces, not
   internals.

4. **Identify the customer surfaces to exercise.** From the gathered
   context, list the customer-facing entry points the feature touches.
   Common surfaces include:

   - CLI commands (with the exact invocation).
   - HTTP / GraphQL / gRPC endpoints (with method + path or operation
     name).
   - UI pages, modals, or flows (with the exact navigation path).
   - Public SDK / library import paths — the exact top-level symbols a
     customer would `import` and the calls they would write.
   - Configuration knobs the operator sets (file or env var) and the
     observable signal that follows (log line, metric, status
     endpoint, API response).
   - Generated outputs and rendered docs pages.

   If the feature is purely internal (refactor, private helper that is
   not re-exported, generator with no visible change) and has **no**
   customer surface, the checklist must say so explicitly in the
   **Scope** section and contain at most a smoke-test scenario (the
   nearest user-visible flow still works, build still succeeds, docs
   still render).

5. **Compose the checklist.** Use exactly this structure:

   ````markdown
   # QA Checklist — <feature title from spec.md>

   **Generated**: <YYYY-MM-DD HH:MM local>
   **Feature**: <FEATURE_DIR relative path>
   **Source**: speckit.opsmill.qa

   ## Scope

   <One short paragraph: what the tester is verifying, and what is
   intentionally out of scope. Lift terminology from spec.md.>

   ## Prerequisites

   <Concrete environment requirements as a bullet list. Pull from
   plan.md / quickstart.md if available. Examples:>

   - [ ] Working copy is on branch `<branch-name>` with the
     implementation merged or rebased.
   - [ ] `uv sync --all-groups --all-extras` (or the project's
     install command) has completed cleanly.
   - [ ] Services running: <e.g., `docker compose up infrahub`>.
   - [ ] Environment variables set: <list with example values>.

   ## Setup

   <Numbered commands to bring the system to a known-good starting
   state. Each command on its own line in a fenced block. Reference
   files by absolute path or by the repo-root-relative path the user
   would actually type.>

   <**Prefer the project's documented dev-environment entry points** —
   `invoke <task>`, `just <task>`, `make <target>`, `task <name>`,
   `npm run <script>`, or whatever this project ships — over raw
   `docker compose` / `kubectl` / service binaries. Discover them
   from project conventions in this order:>

   - <`AGENTS.md`, `CLAUDE.md`, `README.md`, `CONTRIBUTING.md` at
     repo root for an explicit "run locally" / "dev setup" section.>
   - <Project memory: feedback memories about the dev environment.>
   - <Task runner manifests: `tasks/` or `tasks.py` (invoke),
     `justfile`, `Makefile`, `Taskfile.yml`, `package.json` scripts.>
   - <The feature's own `quickstart.md` / `plan.md` if it names
     specific commands.>

   <Fall back to raw `docker compose` / `kubectl` only if no project
   wrapper covers the scenario.>

   ```bash
   <command 1>
   <command 2>
   ```

   ## Test Scenarios

   <One H3 per scenario. **2–5 scenarios** is the sweet spot — each
   one must exercise a *different* user-visible surface or a
   *different* acceptance criterion. If you find yourself writing
   variants of the same step against the same surface, collapse them
   into one scenario and move the variants to **Edge Cases**. Inside
   each scenario:>

   ### 1. <Scenario name — what the tester is checking>

   **What this verifies**: <One sentence, in user terms.>

   **Steps**:

   - [ ] Run: `<exact command, or click path, or HTTP call>`
   - [ ] Observe: <exact output, screen state, or response shape>
   - [ ] Then: `<next step>`
   - [ ] Confirm: <final assertion in user-visible terms>

   **Expected result**: <One or two sentences describing what success
   looks like. Be specific — exit code, status code, field value,
   visible UI element.>

   ### 2. <next scenario>

   ...

   ## Edge Cases

   <Bullet checklist for boundary conditions worth a manual poke. Each
   item is a one-liner with the input and the expected behavior.
   Examples:>

   - [ ] Empty input: `<command with --foo ""` → expect <behavior>.
   - [ ] Duplicate name: re-running creates no second copy; the
     existing record is updated.
   - [ ] Permission denied: as a read-only user, the mutation returns
     <error code> with message containing `<substring>`.

   ## Teardown

   <Commands to return the system to its pre-test state. If none are
   needed, say so explicitly: "No teardown required — all changes are
   scoped to <ephemeral location>." Otherwise:>

   ```bash
   <cleanup commands>
   ```

   ## Sign-off

   - [ ] All scenarios above pass.
   - [ ] No unexpected output, warnings, or errors observed.
   - [ ] Tester: ______________________  Date: __________
   ````

6. **Write the file.**

   - Path: `FEATURE_DIR/qa-checklist.md`.
   - If the user chose "append a timestamped variant" in step 2, use
     `FEATURE_DIR/qa-checklist-YYYY-MM-DD-HHMM.md` instead.
   - Do not create any other files. Do not create a `tests/`
     subdirectory.

7. **Print the resolved path** as the final message, plus a one-line
   reminder that this checklist is intentionally manual / user-facing
   and does not replace the automated test suite.

## Quality Bar

A teammate who has never seen the feature should, after under 10
minutes with this checklist, be able to:

- Stand up whatever a customer would stand up (the service, an SDK
  install, a CLI binary, a docs preview).
- Exercise the feature exactly as a customer would — through its
  shipped, documented surface.
- Decide for themselves whether the feature behaves as `spec.md`
  promises.

If any checklist item reaches into private modules, internal helpers,
test fixtures, or symbols that do not appear in the public docs / SDK
reference, rewrite it to use the customer surface or drop it.
**Hard cap: 150 lines of markdown total.** Aim for ~100. If you go
over, the answer is fewer scenarios, not denser ones.

## Behavior Rules

- **Never modify `spec.md`, `plan.md`, `tasks.md`, or source files.**
  The checklist is purely additive.
- **Public-API code is fine; internal symbols are not.** A snippet
  that imports the project's published top-level package and calls
  documented public methods is a valid QA step — that is the customer
  surface for SDK-shaped features. Steps that reach past the public
  API into internal modules, private packages (`_foo`, `.internal`),
  undocumented config classes, or test fixtures are not. See
  "Customer Frame" and "Customer surfaces, not implementation" in
  Operating Constraints.
- If no customer surface exists, say so plainly in **Scope** and ship
  a minimal smoke-test checklist rather than fabricating scenarios by
  reaching into internals.
- Prefer commands and inputs that already appear in `quickstart.md` or
  `tasks.md` over inventing new ones — the tester should not need to
  reverse-engineer setup.
- **Use the project's documented dev-environment wrappers** (`invoke`,
  `just`, `make`, `task`, `npm run`, etc.) over raw `docker compose` /
  `kubectl` / service binaries. Discover them from `AGENTS.md`,
  `CLAUDE.md`, README, project memory, or the task-runner manifests
  before defaulting to raw container commands.
- Do not include automated test invocations (`pytest`, `vitest`,
  `cargo test`, etc.) as scenarios. Those are out of scope for this
  command.
- For single quotes in bash args, use escape syntax: e.g.
  `'I'\''m Groot'` (or double-quote if possible: `"I'm Groot"`).
