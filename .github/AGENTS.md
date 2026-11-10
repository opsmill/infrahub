# GitHub configuration

## Bug pipeline

Test every change to `.github/workflows/bug-agent-*` or `.github/aw/actions-lock.json` in the
sandbox before asking for review, and paste the report into the pull request description: follow
the `testing-bug-pipeline-changes` skill. The slash-command workflows run from the default branch,
so a pull request's version of the pipeline runs nowhere else before it merges.

After editing a `bug-agent-*.md` source, recompile with the gh-aw version named in the lock-file
header and commit the lock files with it:

```bash
gh aw compile bug-agent-analyst bug-agent-test bug-agent-fix bug-agent-review
```
