# Simplified lifecycle validation

## Local evidence

The helper has 12 passing behavioral tests. The review-required routing regression failed before
the fix, then the full suite passed. [Test output](evidence/simplified-tests.txt) records the exact
command, runtime, timestamp and every test. [Independent review](review-report.md) records scope,
findings and resolution. No live lifecycle writes or Slack notifications were performed.

Actionlint 1.7.12 passes with the existing workflow-scoped exception for intentional false guards.
Zizmor passes. Syntax, YAML, Ruff, format, type checks, both lockfiles, main lint, frontend
Biome/Knip/Betterer, documentation lint and generated documentation validation pass.
Documentation lint reports 30 pre-existing warnings, no errors. YAML was run with the generated
nested testcontainers virtual environment temporarily outside the repository and restored afterward.
External shellcheck is unavailable; actionlint was run with -shellcheck=.

The default testcontainers command fails before collection on macOS psutil.cpu_freq metadata.
With an external plugin returning None only for unavailable CPU-frequency metadata, all plugins
remain enabled and the suite passes: 10 passed, 2 skipped. No repository workaround was added.

## Historical dry checks

On September 29, the simplified collector/renderer replayed the complete September 28 read-only
capture locally: 117 PRs, 11 approval exemptions, five bot exemptions, 16 proposed exemption-label
additions, zero removals, and zero lifecycle writes. It needed 227 simulated REST reads and 112
simulated GraphQL reads. This is historical fixture evidence, not a current GitHub scan.
The temporary raw capture is no longer available, and private API response bodies were never committed.
The later routing correction changes displayed next actors, not those inventory or exemption counts.

A local hash-checked fixture of pinned actions/stale processor methods passed 12 native-configuration
assertions: fresh warning after 60 days; no warning at 59; legacy stale label does not authorize
immediate closure; no closure at 13 days; closure after 15 inactive days; activity removes stale;
each of keep-open/approval/bot labels exempts; issues stay untouched; debug mode suppresses warning
and closure writes. These were fixture API calls, not hosted action execution. Temporary fixture
files have expired. The old custom engine's 51-reminder/12-warning counts do not describe this design.

## Remaining rollout work

Select and inspect a dedicated marked dashboard issue, create label definitions, validate the native
action and token/cache behavior in an authorized isolated environment, and review backlog proposals.
Configure native Slack reminders only after selecting the channel, teams and cadence. None of these
settings were activated by this implementation. A separate reviewed change must enable publishing
and native cleanup; debug-only also remains true.
