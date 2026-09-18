# Retrospective — INFP-46 dark theme completion

**Scope**: PR #10284 (`bab-dark-theme-app`), merged into `develop` as `39116e840` on 2026-08-21,
carrying the stacked PR #10295. Session covered CI triage, automated-review handling, the schema
visualizer submodule bump, and two late review changes: restoring the shared icon on the metadata
trigger, and defaulting the theme to the operating system's appearance.

## Findings

### Instructions / configuration gaps

**R1 — the frontend has two toolchains and only one is enforced.** Running `biome check --write`
against `frontend/packages/ui/src/index.ts` reformatted the whole file from 2-space/100-col to
tabs/80-col. Inside a git worktree there is no `biome.jsonc`, so biome walked up into the parent
checkout and applied that repo's root config. The package actually uses `oxfmt`/`oxlint`, as does
`frontend/packages/graph` — and neither tool is invoked anywhere in `.github/` or
`.pre-commit-config.yaml`, so both packages have been unchecked by CI since they were created.
Nothing would have caught the mangled file; it was found by reading the diff.

*Outcome*: the enforcement gap and the unify-or-not decision became issue #10390. The tooling
boundary is documented as part of that work.

**R2 — `docker-compose.yml` is generated but was not listed as such.** Its env block is rendered
from the backend settings; `update-compose-file-and-chart.yml` regenerates it with `-u` and
`ci.yml` validates it. Neither `AGENTS.md` nor `dev/knowledge/backend/code-generation.md` said so.
Two traps cost time: `release.gen-config-env` writes nothing without `--update-docker-file`
(the parameter defaults to `False`), and `release.validate-dockercomposeenv` regenerates then runs
`git diff --exit-code`, so it fails on an *uncommitted* regeneration exactly as on a stale one.
The same generation silently invalidated prose in `dev/knowledge/frontend/theming.md`, which
claimed the root compose file had no dark-theme passthrough after regeneration had added one.

*Outcome*: fixed in `AGENTS.md` and `code-generation.md`.

**R3 — stacked-PR CI semantics were undocumented, and produced a wrong claim.** Five E2E failures
on #10295 were recorded in the PR body as inherited from the base branch and pre-existing. They
were not: they were stale `bg-neutral-100` assertions already fixed on `develop` by `c9044c40a`
(#10287). #10284 looked green only because *its* merge ref merged `develop`; #10295, targeting
#10284, never saw the fix. Corrected by cherry-picking as `489d8091e`.

*Outcome*: a "Stacked PRs" section added to `dev/guidelines/git-workflow.md`.

### Documentation gaps

**R4 — component tests always run as a dev build.** The first test of the new OS-preference
default failed with `expected 'dark' to be 'light'`: vitest serves through Vite in dev mode, so
`import.meta.env.DEV` is `true` and the dev-server override always wins. This changed the test
design — branch coverage had to move into a pure `domain/rules/` function, leaving the component
test to prove wiring against a stated precondition.

*Outcome*: documented in `dev/guides/frontend/writing-component-tests.md`.

**R5 — a referential-stability test was vacuous.** A T041 test asserting memoized identity was
mutation-tested by deleting the `useMemo`; it still passed 5/5, because the React Compiler re-adds
the memoization. `dev/knowledge/frontend/react.md` documented the auto-memoization but not this
consequence. The test was removed and the task reworded to record the property as held by
compilation.

*Outcome*: caution added to `react.md`.

### Architectural friction

**R6 — branch context is lost on a transient refetch miss.** `BranchesProvider` navigates to `/`
as soon as one branches refetch omits the URL's `?branch=`, making a transiently-absent branch
indistinguishable from a deleted one. Two different E2E specs died on it in one CI run, one of
them API-side. Develop-origin, and expected to block develop's next full E2E run.

*Outcome*: issue #10389.

**R7 — no config field distinguishes an OpsMill-operated deployment from a customer one.** Raised
while deciding whether internal deployments should default to dark. `INFRAHUB_PRODUCTION` misfires
(the shipped compose defaults it to `false` on both services, and it only controls log format);
telemetry cannot answer it either, since every telemetry and analytics value is identical between
the shipped and dev compose files and the only identity in the payload is a per-install UUID.
Deliberately not pursued — the theme now follows the desktop for everyone, with a Vite dev server
as the only override.

### Mistakes and corrections

**R8 — an automated-review claim was endorsed without checking.** A Cubic comment reported a
missing mermaid dependency; the PR body declared `mermaid ^11` in two places. Five of thirteen
Cubic comments were factually wrong. Corrected in-session. Not pursued as a repo change.

**R9 — truncated tool output nearly produced a wrong conclusion.** A `git ls-files | grep` for
biome configs returned only the root one and omitted `frontend/app/biome.jsonc`. The second config
surfaced only because biome itself errored on the nested root. Recorded as a local note.

**R10 — `node` is absent from the shell tool's PATH**, because the version manager is activated
only in fish config. Recorded as a local note.

## Dispositions

| ID | Disposition | Outcome |
|----|-------------|---------|
| R1 | github-issue | #10390 — enforcement + the unify decision, with the tooling boundary documented there |
| R2 | docs | `AGENTS.md`, `dev/knowledge/backend/code-generation.md` |
| R3 | docs | `dev/guidelines/git-workflow.md` |
| R4 | docs | `dev/guides/frontend/writing-component-tests.md` |
| R5 | docs | `dev/knowledge/frontend/react.md` |
| R6 | github-issue | #10389 |
| R7 | none | Recorded here only; the theme no longer needs the distinction |
| R8 | none | Corrected in-session |
| R9, R10 | local-only | Session notes, not repo policy |

Already resolved during the session and carried in #10284: the stale passthrough claim in
`theming.md`, the `git grep -E` word-boundary bug in `quickstart.md`, and the shared-icon
regression on the metadata trigger.
