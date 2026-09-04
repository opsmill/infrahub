# Data Model: E2E proof runs for the bug pipeline

No database entities — the feature's state lives in GitHub objects and CI artifacts.

## Proof run

One workflow execution bound to (pipeline PR, phase).

| Field | Source | Values |
|---|---|---|
| `pr_number` | `github.event.pull_request.number` | int |
| `phase` | PR body markers | `red` (no `AGENT_FIX_COMPLETE`) / `green` |
| `test_file` | PR diff (`--diff-filter=AM`, `tests/e2e/**/test_*.py`, excl. `tutorial/`) | exactly one path, else hard fail |
| `verdict` | `e2e_proof_verdict.py` over `playwright-junit.xml` | `red_confirmed` / `green_confirmed` / `does_not_reproduce` / `inconclusive` |
| `reason` | same | one line, human-readable |
| `screenshot` | newest `test-results/**/*.png` | optional (absence never fails a satisfied phase) |
| `run_id` | `github.run_id` | used in asset names + run links |

**State rule**: job success ⇔ (`phase=red` ∧ `verdict=red_confirmed`) ∨ (`phase=green` ∧ `verdict=green_confirmed`).

## Phase (existing pipeline contract, reused)

`AGENT_TEST_COMPLETE` / `AGENT_FIX_COMPLETE` HTML comments in the PR body, written by the test/fix agents. This feature only **reads** them.

## Screenshot store

Orphan branch `bug-pipeline-assets` (T001 validation reversed the release-asset choice — see research R1).

- File path: `pr-<pr_number>/<phase>-<run_id>.png`; embed URL is `raw.githubusercontent.com/<repo>/<commit-sha>/…` pinned to the publishing commit (immutable — no cache staleness).
- Publish commit also deletes the older `pr-<pr_number>/<phase>-*.png` (one live file per phase).
- Cleanup on PR close commits the removal of the whole `pr-<pr_number>/` folder.
- Lifecycle invariant (SC-005): the branch **tip** carries files only for open pipeline PRs; history growth is the accepted trade-off recorded in research R1.

## PR-description sections (owned by this feature)

| Marker pair | Content | Written when |
|---|---|---|
| `<!-- E2E_PROOF:RED:BEGIN/END -->` | verdict line + before image + run link | every RED run |
| `<!-- E2E_PROOF:GREEN:BEGIN/END -->` | verdict line + after image + run link | every GREEN run |
| `<!-- E2E_PROOF:NOTE:BEGIN/END -->` | expected-red explanation (RED) / all-green expectation (GREEN) | every run |

Sections are replaced in place if present, appended once if absent. Nothing outside the markers is modified (protects `AGENT_*` markers and other bots' content).
