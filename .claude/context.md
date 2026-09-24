---
docs:
  - "dev/**"
  - "**/AGENTS.md"
also_logged:
  - ".agents/**"
working_files:
  - "dev/specs/**"
  - "dev/spec-kit/**"
  - ".specify/**"
skill_dirs:
  - "dev/skills"
skip_dirs:
  - "python_sdk"
---

# Context plugin layout

Where this repository keeps agent guidance, for the `context` plugin (`/plugin install context@infrahub`).
The keys are described in `.agents/plugins/context/README.md`.

Globs match repo-relative paths after symlinks resolve, so a Read of `.claude/rules/x.md` is recorded as
`.agents/rules/x.md`. A `.claude/context.local.md` with the same frontmatter replaces whole keys for you
alone; `**/*.local.*` keeps it out of git.
