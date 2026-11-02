# Agentic workflows

Six GitHub Actions workflows in this repository start a Claude agent. They are written for
[GitHub Agentic Workflows](https://github.github.com/gh-aw/) (gh-aw), a `gh` CLI extension that turns
a Markdown file into a GitHub Actions workflow. Four of them form the bug pipeline, which takes a bug
issue from root cause analysis to a reviewed fix. The other two label issues.

## The workflows

| Source file | Starts when | What the agent produces |
|-------------|-------------|-------------------------|
| `bug-agent-analyst.md` | Someone comments `/bug-analyze` on an issue | A root cause analysis comment |
| `bug-agent-test.md` | Someone comments `/bug-tdd` on the issue, or on the draft pull request after the reviewer asks for test changes | A failing test that reproduces the bug, in a draft pull request against `stable` |
| `bug-agent-review.md` | The pipeline's bot opens or updates a pull request on an `ai-bug-pipeline-*` branch | A review comment with a verdict |
| `bug-agent-fix.md` | Someone comments `/bug-fix` on the draft pull request after the reviewer approves the test, or after it asks for fix changes | A fix pushed to the draft pull request |
| `issue-triage-labeler.md` | An issue is opened; the agent waits 10 minutes so the reporter can label it first | `group/*` and `category/*` labels on that issue |
| `issue-triage-sweep.md` | Every Monday, or started by hand | `group/*` and `category/*` labels on open issues that still have none |

All six source files are in `.github/workflows/`. The slash commands only start a run for people
with admin, maintain or write access to the repository.

## How the bug pipeline moves from step to step

The four bug agents pass work to each other through marker text in comments and pull request
descriptions. Before the agent starts, a gate step reads those markers and stops the run when the
previous step is missing:

- The analyst ends its comment with `AGENT_ANALYSIS_COMPLETE`. `/bug-tdd` on the issue needs it.
- The test writer creates an `ai-bug-pipeline-<issue>-<slug>` branch, opens a draft pull request
  and puts `AGENT_TEST_COMPLETE` in the description. That pull request starts the reviewer.
- The reviewer posts `AGENT_REVIEW_VERDICT:` followed by `TEST_APPROVED`, `TEST_CHANGES_REQUESTED`,
  `FIX_APPROVED` or `FIX_CHANGES_REQUESTED`. `/bug-fix` needs `TEST_APPROVED`, or
  `FIX_CHANGES_REQUESTED` once a fix exists.
- The fixer pushes to the draft pull request and adds `AGENT_FIX_COMPLETE` to the description. The
  push starts the reviewer again, this time on the fix.

The gates read the comment markers (the analysis and the verdicts) only from comments by
`opsmill-bug-pipeline[bot]`, `github-actions[bot]` and `claude[bot]`. They read `AGENT_TEST_COMPLETE`
and `AGENT_FIX_COMPLETE` from the pull request description without checking who wrote it.

After a `FIX_APPROVED` verdict, the reviewer runs again only when a later push changes at least
`BUG_REVIEW_REREVIEW_MIN_LINES` lines outside test files (a repository variable, 1 when unset). The
reviewer gives up after three reviews of the test or three of the fix and adds the
`state/needs-human-fix` label. The other agents hand the issue to a person with
`state/need-more-info` (unclear report), `state/needs-human-test` or `state/needs-human-fix`.

The `/bug-analyze`, `/bug-tdd` and `/bug-fix` commands in `.agents/commands/` are local versions of
the same steps, for an agent session on a developer's machine. They read their instructions from
`dev/bug-pipeline/`. The GitHub agents carry their own instructions in the workflow sources, so a
change to one set does not change the other.

## Source files and lock files

Each workflow has two files:

- `<name>.md`: the source. Its frontmatter sets the triggers, engine, model, permissions, tools,
  network access and the writes the agent may request. Its body is the agent's prompt.
- `<name>.lock.yml`: the GitHub Actions workflow that `gh aw compile` generates from the source.
  GitHub runs this file. Do not edit it: the next regeneration overwrites the edit.

The lock file reads the prompt from the source when it runs, so a change to the body of a source
file takes effect without regenerating. A change to the frontmatter needs a regeneration. Each run
starts with a gh-aw step that checks whether the lock file is out of date with its source.

The lock file fixes everything the run depends on, and its first lines record it:

- The gh-aw version that generated it (`compiler_version` in the `gh-aw-metadata` line).
- The Claude Code version it installs (`engine_versions` in the same line, and the
  `npm install -g @anthropic-ai/claude-code@<version>` step).
- The secrets, actions and container images it uses, each action by commit SHA and each image by
  digest (the `gh-aw-manifest` line). `.github/aw/actions-lock.json` records the action versions
  that gh-aw resolved.

No pull request check compares the lock files with their sources, and only the weekly upgrade
workflow described below regenerates them outside a developer's machine. actionlint skips them
(`.github/actionlint.yaml`), because gh-aw owns their content.

## What a run is allowed to do

- The agent job has read-only GitHub permissions. Comments, labels, pull requests and pushes are
  "safe outputs": the agent requests them, a separate detection job checks the agent's output, and
  a later job applies the requests with the GitHub App token (`GH_AW_APP_ID`,
  `GH_AW_APP_PRIVATE_KEY`). The `safe-outputs` frontmatter caps how many of each the agent may
  request.
- The agent runs inside gh-aw's sandbox, and `network: defaults` limits it to gh-aw's default list
  of domains.
- In the bug agents, `min-integrity: approved` removes from the agent's GitHub reads any content
  written by someone who is not an owner, member or collaborator of the repository. An issue or pull
  request with the `state/ai-pipeline-ready` label is read in full. See
  [Integrity filtering](https://github.github.com/gh-aw/reference/integrity/).
- The repository variable `GH_AW_DEFAULT_MAX_AI_CREDITS` sets the AI credit budget of each run, 1000
  when unset.

## Model and Claude Code version

`engine: claude` selects Claude Code, and the frontmatter `model` field selects the model. Set
`model` in every source: without it, the model depends on the defaults of the pinned gh-aw and
Claude Code versions. From gh-aw 1.0, gh-aw resolves an alias such as `opus` itself, before Claude
Code starts, to the newest available model of that family, so the model can change without a
regeneration.

The Claude Code version changes only when the lock file is regenerated: each gh-aw release pins the
Claude Code version it supports. The `engine.version` field can override that pin. Leave it unset:
the generated command line changes between gh-aw releases, so a Claude Code version that gh-aw was
not released with can break the run. See [AI engines](https://github.github.com/gh-aw/reference/engines/)
and the [Claude engine](https://github.github.com/gh-aw/reference/engines/claude/).

Two engine settings decide what Claude Code may do in the bug agents:

- `permission-mode: acceptEdits`: lets the agent edit files without approval. Set it explicitly:
  before gh-aw 1.0 it was the default, and from 1.0 the default is `dontAsk`, which denies the file
  edits the agents make.
- `bare`: keep it `false`, the default. Bare mode skips the repository instruction files and limits
  Claude Code to the Bash, Edit and Read tools.

## Changing a workflow

Edit the `.md` file. When the change touches the frontmatter, regenerate the lock file and commit
both files together:

```bash
gh extension upgrade gh-aw
gh aw compile bug-agent-analyst
```

Use a gh-aw version at least as new as the `compiler_version` of the lock files, or the
regeneration downgrades them. A regeneration can also change `.gitattributes` and
`.github/aw/actions-lock.json`; commit those changes too.

## Keeping gh-aw and Claude Code current

`.github/workflows/upgrade-agentic-workflows.yml` runs every Monday and can be started by hand. It:

1. Checks out `stable` and installs the newest gh-aw release.
2. Runs `gh aw upgrade --approve`, which rewrites renamed frontmatter fields, updates
   `.github/aw/actions-lock.json` and the gh-aw agent file, and regenerates every lock file.
3. When anything changed, commits it and opens a pull request from `ci/upgrade-agentic-workflows`
   to `stable`. The description lists the gh-aw and Claude Code versions before and after, and the
   secrets and actions the workflows did not use before.

In strict mode, gh-aw asks for approval when a regeneration adds secrets or actions. `--approve`
gives that approval, so the pull request review is where a person checks them.

When an upgrade pull request is already open, the next run updates it only if every commit on it
came from the bot. A pull request someone has pushed to stays as it is until it is merged or
closed.

The workflow needs a token that can push changes to workflow files and open pull requests. It uses
the gh-aw GitHub App, which needs write access to repository contents, pull requests and workflows;
without one of them, the token step fails. The bug agents ask the same app for tokens limited to
contents, issues and pull requests, so they cannot push changes to workflow files even when the app
has that access. gh-aw runs before the upgrade workflow creates its token, so the newly installed
release never has write access.

Dependabot does not update gh-aw's own actions (`.github/dependabot.yml` skips
`github/gh-aw-actions/**`), so without this workflow the lock files stay on the gh-aw version they
were last generated with.

## Reviewing an upgrade pull request

A new gh-aw release can change a default without any error, and `gh aw upgrade` only rewrites fields
that were renamed. Before merging:

- Compare the `claude` command line in one lock file before and after: `--permission-mode`,
  `--allowed-tools`, `--disallowed-tools` and whether `--bare` appears. The bug agents need to edit
  files and run commands.
- For each new secret in the description, check whether the workflows need it. gh-aw skips some
  secrets when they are not set; a missing required secret makes the workflows fail.
- Read the [gh-aw release notes](https://github.com/github/gh-aw/releases) between the two versions
  for changed defaults.
- After merging, start `issue-triage-sweep` by hand from the Actions tab and run `/bug-analyze` on
  a bug issue. Check in the run logs that the agent started with the expected model and finished.
