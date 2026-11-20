# Agentic workflows

The `.md` files in `.github/workflows/` that have a `.lock.yml` file beside them are agentic
workflows: GitHub Actions workflows that start a Claude agent. They are written for
[GitHub Agentic Workflows](https://github.github.com/gh-aw/) (gh-aw), a `gh` CLI extension that turns
a Markdown file into a GitHub Actions workflow. Each source says what it does: its `description`
field, what starts it under `on:` and the agent's instructions in its body.

The `bug-agent-*` workflows form the bug pipeline. They hand a bug from one agent to the next through
marker text in comments and pull request descriptions, which gate steps in their frontmatter check.
The `/bug-analyze`, `/bug-tdd` and `/bug-fix` commands in `.agents/commands/` run the same steps in a
local agent session and read their instructions from `dev/bug-pipeline/`. The GitHub agents carry
their own instructions, so a change to one set does not change the other.

## Source files and lock files

Each workflow has two files:

- `<name>.md`: the source. Its frontmatter sets the triggers, engine, model, permissions, tools,
  network access and the writes the agent may request. Its body is the agent's prompt.
- `<name>.lock.yml`: the GitHub Actions workflow that `gh aw compile` generates from the source.
  GitHub runs this file. Do not edit it: the next regeneration overwrites the edit.

The lock file reads the prompt from the source when it runs, so a change to the body of a source
file takes effect without regenerating. A change to the frontmatter needs a regeneration, see
[Updating agentic workflows](../guides/updating-agentic-workflows.md). Each run starts with a gh-aw
step that checks whether the lock file is out of date with its source.

The lock file fixes everything the run depends on, and its first lines record it:

- The gh-aw version that generated it (`compiler_version` in the `gh-aw-metadata` line).
- The Claude Code version it installs (`engine_versions` in the same line, and the
  `npm install -g @anthropic-ai/claude-code@<version>` step).
- The secrets, actions and container images it uses, each action by commit SHA and each image by
  digest (the `gh-aw-manifest` line). `.github/aw/actions-lock.json` records the action versions
  that gh-aw resolved.

No pull request check compares the lock files with their sources. actionlint skips them
(`.github/actionlint.yaml`), because gh-aw owns their content.

## What a run is allowed to do

- The agent job has read-only GitHub permissions. The agent requests its writes (comments, labels,
  pull requests, pushes) as "safe outputs". A detection job checks them, then a later job applies
  them with the gh-aw GitHub App (`GH_AW_APP_ID`). The `safe-outputs` frontmatter caps how many of
  each the agent may request.
- `network: defaults` limits the agent to gh-aw's default list of domains.
- In a source that sets them, `min-integrity` removes content by authors below a trust level from the
  agent's GitHub reads, and `approval-labels` lifts that for an issue or pull request carrying one of
  the labels. The bug agents set both, with the `state/ai-pipeline-ready` label.
  [Integrity filtering](https://github.github.com/gh-aw/reference/integrity/) lists who reaches each
  level.
- The repository variable `GH_AW_DEFAULT_MAX_AI_CREDITS` sets the AI credit budget of each run, 1000
  when unset.

## Model and Claude Code version

`engine: claude` selects Claude Code, and the frontmatter `model` field selects the model. Without
`model`, the model depends on the defaults of the pinned gh-aw and Claude Code versions. From gh-aw
1.0, gh-aw resolves an alias such as `opus` itself, before Claude Code starts, to the newest
available model of that family, so the model can change without a regeneration.

The Claude Code version changes only when the lock file is regenerated: each gh-aw release pins the
Claude Code version it supports. The `engine.version` field can override that pin. Leave it unset:
the generated command line changes between gh-aw releases, so a Claude Code version that gh-aw was
not released with can break the run. See [AI engines](https://github.github.com/gh-aw/reference/engines/)
and the [Claude engine](https://github.github.com/gh-aw/reference/engines/claude/).

Two engine settings decide whether an agent can edit files:

- `permission-mode: acceptEdits`: lets the agent edit files without approval. Set it in every source
  whose agent edits files: before gh-aw 1.0 it was the default, and from 1.0 the default is
  `dontAsk`, which denies those edits.
- `bare`: keep it `false`, the default. Bare mode skips the repository instruction files and limits
  Claude Code to the Bash, Edit and Read tools.

## Keeping gh-aw and Claude Code current

Dependabot skips gh-aw's own actions, so `.github/workflows/upgrade-agentic-workflows.yml` is what
moves the lock files to newer gh-aw and Claude Code releases. It runs every Monday, can be started by
hand, and has two jobs:

1. The upgrade job checks out `stable`, installs the newest gh-aw release and runs
   `gh aw upgrade --approve`, which rewrites renamed frontmatter fields, updates
   `.github/aw/actions-lock.json` and the gh-aw agent file, and regenerates every lock file. When
   anything changed, it commits the result and writes the pull request description: the gh-aw and
   Claude Code versions before and after, and the secrets and actions the workflows did not use
   before.
2. The publish job starts on a fresh runner, loads that commit and pushes it to
   `ci/upgrade-agentic-workflows` with the gh-aw GitHub App, then opens or updates the pull request to
   `stable`.

gh-aw runs only in the upgrade job, which has no token that can write. The publish job never runs
gh-aw, so nothing the newly installed release leaves on its runner can reach the App token. That
token needs write access to repository contents, pull requests and workflows. The agents ask the same
app for tokens with a fixed list of permissions that does not include workflows.

`--approve` accepts the secrets and actions that a regeneration adds, which strict mode would
otherwise hold for approval. The pull request review is where a person checks them, following
[Review an upgrade pull request](../guides/updating-agentic-workflows.md#review-an-upgrade-pull-request).

A later run replaces an open upgrade pull request only while it still holds the bot's single commit,
so a fix someone pushed or amended stays until the pull request is merged or closed. It leaves the
pull request alone when it already holds the same changes and has no merge conflict.
