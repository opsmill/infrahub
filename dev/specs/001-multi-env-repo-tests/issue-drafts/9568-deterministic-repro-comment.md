# DRAFT — short comment for existing issue #9568

**Target:** [opsmill/infrahub#9568](https://github.com/opsmill/infrahub/issues/9568)
**When:** post **after** the PR lands (so it can reference the PR number).
**Action:** a one/two-sentence comment, not a new issue.

---

Added a deterministic regression test for this in PR #<PR> — it reconstructs the failing
worker-clone state (local primary branch + `origin/<default>` only, no local `<default>`) so the
silent write-back drop reproduces without needing a multi-worker pool. Marked `xfail(strict)`, so it
flips to a failure signal once the push-rejection handling lands.
