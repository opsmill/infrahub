# Extraction Record

**Extracted on**: 2026-08-24
**Extracted by**: speckit.opsmill.extract

## ADRs Created

- `dev/adr/0020-experimental-flag-gates-pre-release-ui.md` (from R1)
- `dev/adr/0021-application-owned-theme-resolution.md` (from R3, generalising R4 and R7)

## Knowledge Updated

- `dev/knowledge/frontend/theming.md` (Content that carries its own colours — added the schema
  visualizer as a fourth surface)
- `dev/knowledge/backend/code-generation.md` (new section: keep generated GraphQL descriptions
  single-line)

## Guidelines Updated

None. One candidate was dropped during review — see below.

## Not extracted, and why

Most of `research.md` was either already written into `dev/knowledge/frontend/theming.md` during
implementation, or describes a design that did not ship. Recorded here so a later reader does not
mistake the research for the built system:

- **R5 — extend the preference store with a `theme` field.** Not implemented. `Preference` still
  carries only `date_format` and `timezone`; the theme lives in `localStorage`. The account-backed
  theme preference remains outstanding work.
- **R6 — an automated guard for hardcoded colours.** Half shipped. The token migration landed; the
  guard did not. `.betterer.ts` has only the TypeScript test and there is no lint rule, so SC-004's
  "standing property" is currently unenforced and the debt can return with the next branch.
- **R1, second half — the flag also makes dark the default.** Superseded during review of #10284.
  The default is now the desktop's `prefers-color-scheme`, with a Vite dev server the only override.
  R1 predicted this separation would happen when the flag is removed; it happened earlier.
- **R2, the three-step precedence with a `"system"` choice.** Never shipped. `ResolvedTheme` is
  `"light" | "dark"` and the pre-paint script reads only the resolved mirror.
- **R5's `Optional[X]` constraint.** Extracted first, then withdrawn: it is obsolete. The source
  comment it came from reads "until Python 3.14", and this project runs 3.14, where the two
  spellings are the same object. `StandardNode.guess_field_type` accepts both regardless
  (`annotation_origin in (Union, UnionType)`), covered by
  `backend/tests/unit/core/node/test_standard.py::test_guess_field_type_resolves_both_nullable_syntaxes`.
  The research had inverted the comment's meaning.
- **R2 / R4 / R7 mechanics, and R8.** Already in `dev/knowledge/frontend/theming.md`.
- `plan.md`, `tasks.md`, `quickstart.md`, `alignment-check.md`, `critiques/`, `checklists/` —
  execution artefacts, no durable knowledge.

`retrospective.md` in this directory records the context-management findings from the same work.

## Archive

Spec directory moved to `dev/specs/archive/infp-46-dark-theme-completion/` as a historical record.
