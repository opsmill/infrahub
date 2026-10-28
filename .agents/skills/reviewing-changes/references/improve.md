# Improve the rules and the index after each run

Propose each of these, and apply only with the user's approval:

- **A "Not violations" line** in a rule, for a finding declined because the rule did not mention
  the accepted pattern. When the declined pattern is debt rather than an accepted pattern,
  propose a cleanup task instead: a rule states the target, not exceptions for existing code.
- **A new rule line** in `.agents/rules/`, for what cubic or a reviewer caught that no rule states.
- **A `paths:` glob or a new rule file**, for each changed area that no rule's globs cover.
- **A better "load before" line** in an `AGENTS.md`, for each article a reviewer had to open on
  its own: say when that article applies, so the next agent is pointed to it.

Keep each `cubic.yaml` entry under 9,000 characters (`wc -m`); cubic drops everything past
10,000. A new rule file with new paths also goes in `cubic.yaml`; a new `dev/` article needs an
`AGENTS.md` line, or `repo-context.py --check-index` fails in CI.
