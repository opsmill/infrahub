# Changelog — extension `opsmill`

Release history for the `opsmill` spec-kit extension (`extension.yml`).

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this artifact adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-06-19

### Added
- Three autonomous-workflow commands (authored from scratch, not lifts):
  - `speckit.opsmill.auto` — runs the full pipeline end-to-end (prep +
    implement) autonomously, stopping before extract.
  - `speckit.opsmill.prep` — runs the preparation phases
    (specify → plan → critique → tasks → spec/ask alignment check),
    stopping before implementation. Emits a machine-readable
    `STATUS: <READY|BLOCKED> | SPEC_DIR: … | REASON: …` final line so
    `auto` can detect failure and hand off the spec dir deterministically.
  - `speckit.opsmill.implement` — runs the implementation + review tail from
    an existing `tasks.md` in clean-context subagents, then emits a final
    report and a `STATUS: <DONE|INCOMPLETE|BLOCKED> | …` final line. Phase 0
    stop-conditions abort (rather than pause) when run under the autonomous
    parent.
- `tags` gains `auto`, `prep`, `implement`, `autonomous` for registry
  discoverability.

### Removed
- The `after_implement` → `speckit.opsmill.extract` hook. Extract is now an
  explicit manual follow-up the user runs after reviewing the implementation
  report; `auto` deliberately stops before it.

### Changed
- `extension.version` bumped `1.0.0` → `1.1.0`.
- `extension.description` updated to cover the autonomous end-to-end workflow.

## [1.0.0] - 2026-05-11

### Added
- Initial release. Single spec-kit extension (`id: opsmill`,
  `schema_version: "1.0"`, `requires.speckit_version: ">=0.8.0"`) providing:
  - `speckit.opsmill.extract` — knowledge / guidelines / ADR extraction
    from completed spec directories.
  - `speckit.opsmill.retrospect` — session retrospective with
    user-approved disposition routing.
  - `speckit.opsmill.summary` — flow-level session summary in the
    active feature directory.
- `requires.scripts: ["check-prerequisites.sh"]` declared (script is shipped
  by spec-kit core; not vendored here).
- Two opt-in hooks declared in `extension.yml` so the commands auto-prompt
  during the SDD flow:
  - `after_implement` → `speckit.opsmill.extract`
  - `after_taskstoissues` → `speckit.opsmill.summary`
  Both `optional: true`; users are prompted before each fires.

### Provenance
Command bodies are lifted from `opsmill/styrmin/.specify/extensions/`:
- `commands/extract.md` from `extract/commands/extract.md`. Single edit:
  line 255 self-reference `speckit.extract` rewritten to
  `speckit.opsmill.extract`.
- `commands/retrospect.md` from `retrospect/commands/retrospect.md`.
  Verbatim, no edits.
- `commands/summary.md` from `summary/commands/run.md` (renamed). Single
  edit: line 62 self-reference `/speckit.summary.run` rewritten to
  `/speckit.opsmill.summary`.

## Smoke test — 2026-05-11T18:05:00Z

- ZIP install: PASS — Created `/tmp/opsmill-speckit-smoke/opsmill-speckit-v1.0.0.zip` from committed HEAD; contents verified (1185 bytes extension.yml, all three command files).
- Three commands discovered: PASS — `specify extension list` output shows "OpsMill Speckit Workflow (v1.0.0)" with 3 commands enabled:
  - `speckit.opsmill.extract` — Extract knowledge, guidelines, and ADRs from completed spec directories into the project documentation system.
  - `speckit.opsmill.retrospect` — Run a session retrospective that surfaces context-management gaps and routes them to approved follow-up actions.
  - `speckit.opsmill.summary` — Produce a flow-level timeline of the current Claude Code session in the active feature directory.
- Discovery command used: `specify extension list`
- Command files verified in scratch project at `.specify/extensions/opsmill/commands/{extract,retrospect,summary}.md`.