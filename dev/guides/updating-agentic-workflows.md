# Updating agentic workflows

How to change the settings of an agentic workflow and how to review the weekly upgrade pull request.
For how the workflows and their lock files work, see
[Agentic workflows](../knowledge/agentic-workflows.md).

## Prerequisites

- The `gh` CLI with the gh-aw extension installed: `gh extension install github/gh-aw`.

## Change the settings of a workflow

If you change only the body of a `.md` source, commit it as it is: the lock file reads the body when
it runs. If you change the frontmatter:

1. Upgrade gh-aw, so the regeneration does not move the lock files back to an older gh-aw version:

   ```bash
   gh extension upgrade gh-aw
   ```

2. Regenerate the lock file, naming the source without `.md`:

   ```bash
   gh aw compile bug-agent-analyst
   ```

3. Commit the source, its lock file and any change the regeneration made to `.gitattributes` or
   `.github/aw/actions-lock.json`.

### Verification

`git diff` shows the lock file changed, and the `compiler_version` in its `gh-aw-metadata` line is at
least as new as before.

## Review an upgrade pull request

A new gh-aw release can change a default without any error, and `gh aw upgrade` only rewrites fields
that were renamed. Before merging:

1. Compare the `claude` command line in one lock file before and after: `--permission-mode`,
   `--allowed-tools`, `--disallowed-tools` and whether `--bare` appears. The bug agents need to edit
   files and run commands.
2. Check that no `create-github-app-token` step in the lock files asks for `permission-workflows`.
3. For each new secret in the description, check whether the workflows need it. gh-aw skips some
   secrets when they are not set; a missing required secret makes the workflows fail.
4. Read the [gh-aw release notes](https://github.com/github/gh-aw/releases) between the two versions
   for changed defaults.

### Verification

After merging, start `issue-triage-sweep` by hand from the Actions tab, and comment `/bug-analyze` on
a bug issue. Check in the logs of both runs that the agent started with the expected model and
finished.
