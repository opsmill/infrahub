# Phase 6: Improve the skill and the docs

Read this when phase 6 starts. The rules in `SKILL.md` still apply.

Run this after the phase-5 checkpoint, and again at teardown if implementation found more.

Read `STATE.md`, the `feedback/` files, `git log .design/<slug>/` and the conversation.
List each place where the run had to work around something, in one of these groups:

- **This skill**: a rule that was wrong, missing or ignored, a panel or notes bug, or a
  check the preflight missed. Fix it in `.agents/skills/design-jam/`.
- **A skill it invokes**: advice that did not fit Infrahub. Record it only; the `emil-*`
  skills are not in this repo.
- **Internal docs**: a frontend fact the run had to find in code because
  `frontend/app/AGENTS.md`, `dev/guidelines/frontend/` or `dev/knowledge/` does not say it.
  Follow `dev/guidelines/documentation.md` for where it goes.
- **`@infrahub/ui`**: already in the `Missing` list of `01-system.md`. Link it.

Write `06-improvements.md`: one line per finding, with its group and the proposed edit.
Apply only what the user approves, on a new branch from `develop`. The design branch is
never merged, so edits made there are lost. Open the PR with the repo's `pr` skill and add
its URL to the file. If there are no findings, write that in one line.
