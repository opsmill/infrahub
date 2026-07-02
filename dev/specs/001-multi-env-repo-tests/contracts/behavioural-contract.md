# Behavioural Contract: what each test pins

This feature exposes no new external interface. The "contract" is the **behavioural contract of the
git-integration layer** that the tests assert — one row per acceptance scenario, with the observable
signal each test reads (never `sync_status`, never a merge return value).

## Deterministic prong — `backend/tests/integration/git/test_multi_env_writeback.py`

| ID | Scenario | Setup | Observable assertion | Outcome |
|---|---|---|---|---|
| US1§1 | Write-back drop on a non-importer clone | Clone with local primary + `origin/<default>` only; merge writing back to `<default>` | `push` reports success AND remote `<default>` tip unchanged | xfail(strict) |
| US3.1 | Non-main default, no phantom | RW repo `default_branch=develop`; run sync cycle | `client.branch.all()` has no standalone `develop`; `develop` maps to primary | green |
| US3.2 | Non-main default import not frozen | New commit on remote `develop`; run sync | recorded `commit` advances to the new SHA | green |
| US4§1 | Divergent pull recovers | Diverge local `<default>` from remote (out-of-band commit); two sync cycles | first sync surfaces the error, second sync recovers to the remote tip (recorded commit == remote) | green (refuted defect) |
| US4§2 | Non-ff write-back drop | Advance remote `<default>` out-of-band, then in-Infrahub merge | write-back applied OR reported failed — not silently dropped | xfail(strict) |
| US4§3 | In-merge conflict surfaced | Infrahub branch genuinely conflicts with `<default>`; merge | merge fails (error raised) AND worktree left clean (merge aborted) | green |
| US4§4 | Per-branch failure isolation | One bad branch + one good branch; run sync | good branch imports; failure confined to the bad one | green |
| US5§1 | Filter excludes a branch | Filter excludes `<branch>`; sync | `<branch>` not imported as standalone; not required conflict-free | green |
| US5§2 | Fetch-before-filter blast radius | Fetch-time problem on an excluded ref (likely a clobbering/moved tag); sync | in-filter branches still import | xfail(strict), trigger confirmed empirically |

## Full-stack prong — `backend/tests/integration_docker/test_multi_env_approach_a.py`

Two separate instances (a development stack + a read-only consumer stack) sharing one remote. No
multi-worker pool. (US1§2 — the statistical live-pool write-back demonstration — was dropped;
clarification 2026-07-01.)

| ID | Scenario | Setup | Observable assertion | Outcome |
|---|---|---|---|---|
| US2.1 | Consumer imports only its branch | Read-only consumer stack pinned to its branch on the shared remote | consumer `branch.all()` == {primary} only | green |
| US2.2 | Isolation: dev advance invisible to consumer | Development stack advances its branch on the shared remote | consumer recorded `commit` unchanged | green |
| US2.3 | Promotion invisible before reimport | Promote a change onto the consumer's branch; no reimport | consumer `commit` == pre-promotion SHA | green |
| US2.4 | Reimport advances consumer | `InfrahubReadOnlyRepositoryImportLastCommit`, then poll | consumer `commit` advances to promoted SHA | green |

## Cross-cutting assertion rules

- Branch set via `client.branch.all()` (or `{Branch{name}}`); import advance via the repository's
  recorded `commit`; write-back via the remote tip (`git ls-remote` / bare repo ref).
- Never assert on `sync_status`, the `merge`/`push` return value, or the `BranchMerge` mutation result.
- Wait by polling observable state to a deadline; never `sleep` a fixed duration.
- `xfail(strict, reason=...)` reasons describe behaviour; no issue IDs in test source.
