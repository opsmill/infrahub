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
skip_dirs:
  - "python_sdk"
---

# Context plugin layout

Where this repository keeps agent guidance, for the `context` plugin (`/plugin install context@infrahub`).
`.claude/context.md` is a symlink to this file. The keys are described in `.agents/plugins/context/README.md`;
`/context:init` can rewrite it.

Globs match repo-relative paths after symlinks resolve, so a Read of `.claude/rules/x.md` is recorded as
`.agents/rules/x.md`. A `context.local.md` beside this file replaces whole keys for you alone;
`**/*.local.*` keeps it out of git.
