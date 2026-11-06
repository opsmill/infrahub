# Changelog — extension `opsmill`

Release history for the `opsmill` spec-kit extension (`extension.yml`).

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this artifact adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.4.0] - 2026-10-27

The current workflow runs on spec-kit 1.2, and still on 0.8.0 and later.
README: [Upgrading spec-kit to 1.2 or later](README.md#upgrading-spec-kit-to-12-or-later).

### Changed
- `extension.version` bumped `1.3.2` → `1.4.0`.
- `implement` reviews with the `pr-review-toolkit` Claude Code plugin when it is
  installed, else with `/code-review`, else with its built-in
  reviewer. The spec-kit `review` extension is no longer used: it does not
  install on spec-kit 1.x. The `REVIEW:` field of the status line now reads
  `plugin`, `command`, `fallback`, `none` or `n/a`, instead of `extension`,
  `fallback`, `none` or `n/a`. Shipped as a minor bump, as in 1.3.0, whose
  consumer audit found `auto` (updated here) to be the only reader of it.
- README: the `checkpoint` extension, which provides the
  `speckit-checkpoint-commit` skill that `prep`, `implement` and `auto` commit
  with, is listed with the other companions.
- `.extensionignore` also excludes `.github/` and `.git`, so the repo's CI files
  and, for a `--dev` install from a clone, its git history are not copied into
  `.specify/extensions/opsmill/`.

### Fixed
- `summary` and `qa` find `check-prerequisites.sh` again on Spec Kit 1.2, which
  resolves a command's script path from the extension directory.

## [1.3.2] - 2026-10-23

### Added
- `.extensionignore` excludes `presets/` from the installed extension. A tag
  archive holds the whole repo, so `specify extension add` copied the presets
  into `.specify/extensions/opsmill/`, where spec-kit never reads them.

### Fixed
- README: installs pin a release tag instead of `main`. The preset installs
  used `specify preset add --from … --subdir`, an option no spec-kit release
  has; they now install with `--dev` from a clone of the tag.
- README: the `critique` and `review` companion extensions move from Requires
  to an optional section, since `prep`, `auto`, and `implement` fall back to a
  built-in pass without them.

### Changed
- `extension.version` bumped `1.3.1` → `1.3.2`.

## [1.3.1] - 2026-10-23

### Fixed
- `extract`: knowledge and guideline source markers now point to the archived
  spec path (`specs/archive/<spec-name>`), matching the ADR rule, so references
  no longer break after Phase 4 archives the spec. The Knowledge updates
  section gains a "create a new one if needed" branch, for parity with
  Guidelines updates (opsmill/opsmill-speckit#10).

### Changed
- `extension.version` bumped `1.3.0` → `1.3.1`.

## [1.3.0] - 2026-09-12

### Added
- **Companion-extension fallbacks.** `implement` Phase 0 now resolves a
  review provider (`REVIEW_MODE`), and `prep` Phase 3 resolves a critique
  provider (`CRITIQUE_MODE`), by running a literal shell check for
  `.specify/extensions/<id>/` and the installer's `.specify/extensions/.registry`
  record — both installer-written and harness-independent. When a companion
  extension is missing, the phase runs a reduced built-in reviewer/critic in a
  clean-context subagent instead of silently skipping the gate. Where no
  subagent dispatch exists either, the mode is `none` and the run says so.
- A half-installed extension (files on disk, command never registered)
  downgrades at invocation time: if `speckit-review-run` / `speckit-critique-run`
  cannot be invoked, the phase drops to the fallback branch and reports the mode
  that actually ran, rather than reporting `extension` for a pass that did not
  happen.
- `implement` Phase 7 §5 now opens with a required `Review mode:` line, and
  §6 must record any non-`extension` mode as an autonomous decision.
- `implement` gains a review blocking rule: `REVIEW_MODE: none` marks the run
  `INCOMPLETE` and makes "install the review extension and re-run the review"
  the first next step, mirroring the existing local-pass-evidence rule.
- `auto` Completion must now state the `CRITIQUE` and `REVIEW` coverage of the
  run, leading with it when either gate was degraded.
- README: companion extensions documented as soft dependencies, plus a
  Troubleshooting section covering the upstream `review` install failure on
  spec-kit 1.0.x (opsmill/opsmill-speckit#16) and the `REVIEW: none` state.

### Changed
- `extension.version` bumped `1.2.0` → `1.3.0` (opsmill/opsmill-speckit#17).
- **Status-line contract — field order changed.** `prep` now emits a `CRITIQUE:`
  field and `implement` a `REVIEW:` field, both inserted **before** `REASON:`:
  - `STATUS: <READY|BLOCKED> | SPEC_DIR: <path> | CRITIQUE: <extension|fallback|none|n/a> | REASON: <...>`
  - `STATUS: <DONE|INCOMPLETE|BLOCKED> | SPEC_DIR: <path> | REVIEW: <extension|fallback|none|n/a> | REASON: <...>`

  `STATUS` and `SPEC_DIR` keep their position and meaning, but `REASON` moves
  from the third field to the fourth, so anything reading it by index needs
  updating. Shipped as a minor bump rather than a major one (review call on
  opsmill/opsmill-speckit#17) because the consumer audit found no such reader:
  `auto` in this extension (updated here) is the only parser, `infrahub-speckit`
  does not read these lines at all — it ships three route commands and no status
  parsing — and an org-wide code search for `SPEC_DIR` returns only vendored
  copies of this extension.

## [1.2.0] - 2026-08-19

### Added
- `speckit.opsmill.qa` — produces a manual QA checklist at
  `FEATURE_DIR/qa-checklist.md` that walks a human tester through
  verifying the just-implemented feature (scope, prerequisites, setup,
  test scenarios, edge cases, teardown, sign-off). Manual / user-facing
  only; automated test suites are intentionally out of scope. Not wired
  to any hook by default — run it manually, or re-wire it at
  `after_implement` on the consumer side (snippet in README)
  (opsmill/opsmill-speckit#5).
- `tags` gains `qa` for registry discoverability.
- README: the `critique` and `review` companion extensions, whose
  `speckit-critique-run` and `speckit-review-run` skills `prep`, `auto` and
  `implement` invoke, are listed under Requires with install commands
  (opsmill/opsmill-speckit#9).

### Changed
- `extension.version` bumped `1.1.0` → `1.2.0`.
- `extension.description` updated to cover the QA checklist command.

### Fixed
- `retrospect`: the issue-creation skill reference follows the skill renames
  in opsmill-skills, first `create-issue` → `creating-issues`
  (opsmill/opsmill-speckit#8), then `creating-issues` →
  `opsmill-dev-creating-issues` (opsmill/opsmill-speckit#11).

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
- `extract` writes ADRs in the MADR layout used by infrahub and infrahub-mcp:
  file `nnnn-kebab-case-title.md` (4 digits, no `adr-` prefix, previously
  `adr-NNN-title.md`) and heading `# N. <Title>` (previously `# ADR-NNN:`)
  (opsmill/opsmill-speckit#6).

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
