# context

Records which guidance a coding-agent session loads, and what led to each load, then lets you read, draw and
audit that record. It records Claude Code sessions today; the repository lint applies to every harness.

| Skill | What it does |
|---|---|
| `/context:init` | Scans the repository, asks where its guidance lives, and writes the config below |
| `/context:trace [session id]` | Shows the session's load log, the last 200 lines when it is longer |
| `/context:map [session id]` | Draws the log as a Mermaid diagram and saves it as `context-map.md` beside the log |
| `/context:doctor [session id]` | Audits the session and lints the repository, then merges the two reports, starting with what never loaded |

With no argument, each skill uses the current session. `/context:doctor` runs two skills you don't call
yourself:

- `context:audit-session`: forked into the plugin's read-only `context:doctor` agent, a 1M-context model
  reads the session history and every doc, works out what the session should have loaded, and reports the
  difference.
- `context:lint-repo`: runs the repository lint below, a script with no model, and hands its output to the
  doctor unchanged.

Installing the plugin is the opt-in: its hooks start recording with the next session.

## Configuration

Each repository describes where its guidance lives in a committed `context.md`, as YAML frontmatter, in
`.agents/`, `.claude/`, or both. A repository with both folders keeps the file in `.agents/` and makes
`.claude/context.md` a symlink to it; two separate files are an error. A `context.local.md` beside it, kept
out of git, replaces whole keys for one person. Without a config the defaults apply. `/context:init` writes
the file, and the symlink, from a few questions.

Globs are repo-relative and match paths after symlinks resolve; `**` spans directories, `*` does not, and
`{a,b}` lists alternatives. `CLAUDE.md` and `AGENTS.md` files count as guidance whatever `docs` lists.

| Key | Meaning | Default |
|---|---|---|
| `docs` | Guidance. Every Read of it is logged, and `/context:doctor` reads all of it | `**/AGENTS.md`, `**/CLAUDE.md` |
| `also_logged` | Reads are logged, but the doctor does not read these, such as commands, rules and skills | `.agents/**`, `.claude/**` |
| `working_files` | Material a session works on, such as spec artifacts: logged, never read or judged as guidance | none |
| `skip_dirs` | Directories never scanned, such as submodules | none |
| `lint_allow` | Files the lint lets name harness-loaded files, such as guidance about writing guidance | none |

```markdown
---
docs:
  - "<guidance folder>/**"
  - "**/AGENTS.md"
also_logged:
  - ".agents/**"
  - ".claude/**"
working_files:
  - "<specs folder>/**"
skip_dirs:
  - "<submodule>"
---
```

Claude Code's own loading rules are built in, so the log records what it actually loaded:

- At session start, the root `CLAUDE.md`, `.claude/CLAUDE.md` and `CLAUDE.local.md`, the files they import,
  and the rules without `paths:`. It records the root `AGENTS.md` too, when Claude Code reads it: under the
  default instruction-files setting only when no `CLAUDE.md` counts, or always when the person set it to
  read both.
- When a file is read, each folder's `CLAUDE.md` above it, the `AGENTS.md` that the setting makes Claude
  Code read, and the path-scoped rules that match.
- Rules come only from `.claude/rules`, and skills only from `.claude/skills`, because Claude Code reads
  nothing under `.agents/`. The doctor's index flags rules and skills that exist only in `.agents/`.
- Explore and Plan subagents, and custom agents that set `omitClaudeMd`, start without the startup files,
  though nested instruction files and path-scoped rules still reach them on a Read.

## What did not load

`/context:doctor` reports first what never reached the context that needed it. Before the audit, a script
works it out from Claude Code's own record in the transcript: for every file a context read or changed, each
`CLAUDE.md`, `AGENTS.md` and path-scoped rule that applied to it but never loaded there, with the reason.
Typical reasons are an `AGENTS.md` that Claude Code never loads on its own because no `CLAUDE.md` imports it,
a rule that only injects on a Read while the context only wrote the file, and a rule kept in `.agents/rules`.
A subagent's result counts as reaching its parent, so guidance it quotes back is not reported as missing.

The session audit runs in the plugin's `context:doctor` agent, which has Read, Glob and Grep and nothing
else, so it never runs a command or changes a file. It judges the docs tree as it is now and says so when the
session ran on another branch.

## Repository lint

`scripts/context_lint.py <repository>` checks how guidance is organised, so that every harness loads each file
once. Claude Code reads `CLAUDE.md` files, rules and skills, and loads a nested `CLAUDE.md` when a file below
it is read. Codex reads only the `AGENTS.md` files from the repository root down to its working directory,
once, and skills: no `CLAUDE.md`, no rules and no `@` imports. The rules:

| Rule | Level | What it asks |
|---|---|---|
| `shim` | error | Every `AGENTS.md` has a `CLAUDE.md` beside it holding only `@AGENTS.md` |
| `pointer` | error | Nothing names a harness-loaded file by path: `AGENTS.md`, `CLAUDE.md`, rules, `SKILL.md` files, commands, agent definitions. Name skills and commands instead. A skill's files may name each other, and an `AGENTS.md` may name the `AGENTS.md` files below it, which is how Codex finds them |
| `import` | error | No `@` imports outside `CLAUDE.md` |
| `size` | error | The `AGENTS.md` files from the root down to any folder stay under Codex's 32 KiB default |
| `rule` | error | A rule stays under about 1k tokens, counted at 3 bytes a token, since Claude Code injects its whole text into every context that reads a matching file, or every session when it has no `paths:` |
| `orphan` | warning | Every guidance doc is reachable from a file a harness loads |
| `conflict` | warning | A rule doesn't recommend a code term that the doc it names advises against |

Working files and `lint_allow` files are not checked for pointers. Listing a file under `lint_allow` is the
only exception there is: the lint reports any inline allow marker as an error instead of honouring it. `--fix` creates the missing `CLAUDE.md` shims and trims those that hold only headings besides
the import. With `--check` the script exits 1 on any error, for a pre-commit hook or CI job.

Two environment variables change where output goes, per person:

- `CLAUDE_TRACK_DOC_READS_DIR`: write each session's files to `<dir>/<session id>/`
- `CLAUDE_TRACK_DOC_READS_ECHO=0`: no chat notice when a doc is loaded for the first time

## Output

Everything for a session sits in `~/.claude/projects/<project>/<session id>/doc-reads/`:

- `reads.log`: the readable log that `/context:trace` shows, stamped in local time
- `reads.jsonl` and `state.json`: the records behind it
- `errors.log`: only when the hook failed, including on a bad config file
- `context-map.md`: from `/context:map`
- `doctor/`: the session summary, doc index and not-loaded list `/context:doctor` reads; its report comes back in chat

The scripts need `python3` 3.9 or later and use only the standard library.
