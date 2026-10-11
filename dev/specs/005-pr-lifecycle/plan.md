# Implementation plan

Use actions/github-script's existing Octokit client from a pinned action. Implement a dependency-free
CommonJS helper under .github/scripts with collection, pure classification/rendering, and optional
label/dashboard synchronization. Inject the client in Node's built-in test runner. Prefer fewer than
400 production lines; do not recreate a GitHub client or persistence engine.

Collect every open PR and paginated review history before any mutation. Use the same-head GraphQL
merge aggregate for conservative readiness. Keep the dashboard stateless; publish only to a
configured issue carrying a dedicated marker. No automatic issue discovery or creation.

Use three workflow jobs: read-only preview, unconditionally disabled publish, and unconditionally
disabled native stale (dependent on successful publish). Native stale uses its own budget and cache.
Retain dry-run on the disabled stale step as another review barrier. Test helper behavior on pull
requests through a small CI workflow, with no GitHub write token or untrusted execution privileges.

Replace obsolete specification artifacts and test harnesses; Git history retains their evidence.
Write developer explanation, operator activation/dry-run instructions and native Slack setup.
Run a replay from the already captured private inventory if compatible; label it historical,
not a fresh production scan. Never commit private API bodies or activate notification settings.
