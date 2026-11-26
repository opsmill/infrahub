# Feature Specification: Re-enable ruff BLE (blind-except) rule and fix all violations

**Feature Branch**: `pha/INBOX-19`

**Created**: 2026-07-22

**Status**: Draft

**Input**: User description: "Re-enable the ruff BLE (flake8-blind-except) rule and fix all of its violations in opsmill/infrahub (Engineering Inbox card INBOX-19). Remove BLE from the global ruff ignore list in pyproject.toml; at each violation site replace the blind except with the specific exception type(s) the guarded code can actually raise; where a broad catch is genuinely required keep `except Exception` with a targeted `# noqa: BLE001` and a brief justification comment."

## Context

The repository's lint configuration selects all ruff rules (`select = ["ALL"]`) and then globally ignores the BLE category (flake8-blind-except) under the "needs to be investigated" block in `pyproject.toml`. The team's suppression analysis (Patrick Ogenstad's 2026-02-18 Slack thread on lint ignores) ranked re-enabling BLE as priority #1: blind `except Exception:` handlers swallow real bugs, and handlers that catch `BaseException` (or bare `except:`) additionally swallow `KeyboardInterrupt`/`SystemExit`.

Ground truth measured on this branch (2026-07-22): **78 BLE001 violations across 46 files** — the card's ~32 estimate is stale; the count grew with recently added graph migrations. Distribution:

| Area | Sites | Notes |
|------|-------|-------|
| `backend/infrahub/core/migrations/` (graph migrations + shared) | 30 | Best-effort per-item loops in data backfills; behavior must not change (hard constraint) |
| Authentication paths (`api/auth.py`, `api/oauth2.py`, `api/oidc.py`, `auth/auth.py`) | 8 | Auth behavior must not change (hard constraint) |
| Other backend runtime (`artifacts`, `cli/upgrade`, `core/schema`, `core/validators`, `generators`, `git`, `message_bus`, `services`, `task_manager`, `telemetry`, `webhook`) | 16 | Mix of defensive task loops and narrowable handlers |
| Backend test helpers/suites (`backend/tests/`) | 13 | Includes one `except BaseException` (`tests/helpers/test_worker.py`) |
| Repo tooling (`tasks/release.py`, `tests/e2e/data/parity.py`, `utilities/infrahub_load_tester.py`) | 11 | Dev/CI tooling and load-test scripts |

The enforcing gate is CI's `uv run ruff check . --exclude python_sdk` (full-repo run), so every one of the 78 sites must be resolved before the ignore entry can be removed.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Blind-except enforcement is active for all future code (Priority: P1)

As an Infrahub developer, when I introduce a new `except Exception:` (or broader) handler without justification anywhere in the repository, the lint gate rejects my change locally and in CI, so bug-swallowing handlers can no longer enter the codebase unnoticed.

**Why this priority**: The durable value of the card is regression prevention. Fixing today's 78 sites without turning the rule on would let the debt immediately re-accumulate.

**Independent Test**: Remove `"BLE"` from the ignore list, add a temporary `except Exception: pass` to any linted file, run the lint gate — it must fail with BLE001; revert the temporary handler — it must pass.

**Acceptance Scenarios**:

1. **Given** the BLE entry is removed from the global ignore list in `pyproject.toml`, **When** `uv run ruff check . --exclude python_sdk` runs (the CI lint command), **Then** it reports zero violations.
2. **Given** the rule is active, **When** a developer adds an unjustified `except Exception:` handler and runs the lint gate, **Then** the gate fails with a BLE001 diagnostic pointing at the new handler.
3. **Given** the rule is active, **When** `uv run invoke backend.lint` runs, **Then** it exits successfully.

---

### User Story 2 - Existing blind handlers are narrowed to real failure modes (Priority: P2)

As an Infrahub developer or operator, code paths that previously swallowed *any* error now catch only the exception types the guarded code can actually raise, so genuinely unexpected failures (typos, contract violations, programming bugs) surface immediately instead of being silently absorbed or mislabeled.

**Why this priority**: This is the direct bug-risk reduction the card was filed for. It ranks below P1 only because narrowing without enforcement decays, while enforcement without narrowing is impossible (CI would fail).

**Independent Test**: For each narrowed site, the module's existing tests pass unchanged; `ruff check --select=BLE <file>` is clean for that file.

**Acceptance Scenarios**:

1. **Given** a handler whose guarded code has an identifiable set of raisable exception types, **When** the fix is applied, **Then** the handler names those specific types (or a project/library base type that covers them) and its body is unchanged.
2. **Given** a narrowed handler, **When** the exceptions it previously handled are raised by the guarded code, **Then** runtime behavior is identical to before the change (same logging, same fallback, same control flow).
3. **Given** the full set of narrowed sites, **When** the test suites covering the touched modules run, **Then** they pass without modification (except tests that themselves contained violations).

---

### User Story 3 - Genuinely-broad catches are explicit and justified (Priority: P3)

As a future maintainer reading defensive code (top-level task loops, best-effort cleanup, data-migration per-item guards), I can immediately see that a broad catch is intentional: it reads `except Exception` (never bare `except:`), carries a targeted `# noqa: BLE001` suppression, and a brief comment stating why swallowing arbitrary errors is required there.

**Why this priority**: Documentation/readability value on top of P1/P2; it is what makes the suppression auditable rather than silent.

**Independent Test**: Grep all `noqa: BLE001` occurrences; each must sit on an `except Exception` (or deliberately `except BaseException` where isolation demands it) with an adjacent justification, and none may be a bare `except:`.

**Acceptance Scenarios**:

1. **Given** a site where any failure must not break the surrounding loop/cleanup (e.g., per-node migration backfill, telemetry push, scheduled-task loop), **When** the fix is applied, **Then** the handler keeps `except Exception`, gains `# noqa: BLE001`, and a short justification comment, with zero behavioral change.
2. **Given** the completed change, **When** the repository is searched for bare `except:` clauses in linted Python code, **Then** none exist (E722 already enforces this; the change must not introduce any).
3. **Given** the completed change, **When** any handler still catches `BaseException`, **Then** it carries an explicit justification for also intercepting `KeyboardInterrupt`/`SystemExit` (only defensible in process-isolation/diagnostic harnesses).

---

### Edge Cases

- **Handlers inside hard-constraint areas (graph migrations, auth flows)**: narrowing would change runtime behavior for unexpected exception types in code where behavior changes are prohibited by the card (no migration changes, no auth changes). These sites MUST use the suppress-with-justification treatment (comment + `noqa`), never semantic narrowing.
- **`except BaseException` in `backend/tests/helpers/test_worker.py`**: broader than `Exception`; must be either narrowed or explicitly justified — never silently converted in a way that changes what the test harness intercepts.
- **Handlers that both log and re-raise or wrap**: ruff still flags them; the fix must preserve the wrap/re-raise semantics exactly.
- **Fixture/vendored Python files** (e.g., `backend/tests/fixtures/repos/...` with their own `pyproject.toml`): governed by their own ruff scope; out of remediation scope — the CI command's output is authoritative for what is in scope.
- **`python_sdk/` submodule**: explicitly excluded by the CI lint command and a separate repository; out of scope.
- **New violations landing on the base branch while this change is in flight**: the final verification must re-run the full-repo check at merge-readiness time, not rely on the initial inventory of 78.
- **Unused-suppression detection (RUF100)**: every added `# noqa: BLE001` must be *load-bearing* once BLE is active; a `noqa` added to a line ruff does not flag would itself fail the lint gate.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The global ruff ignore list in `pyproject.toml` MUST no longer contain the `"BLE"` entry, and no new blanket suppression of BLE (global ignore, per-file-ignore section, or directory-wide ignore) may be introduced in its place.
- **FR-002**: After the change, `uv run ruff check --select=BLE .` and the CI lint command `uv run ruff check . --exclude python_sdk` MUST both report zero violations from the repository root.
- **FR-003**: Every current violation site MUST be resolved by exactly one of two treatments: (a) narrowing the handler to the specific exception type(s) the guarded block can raise, or (b) keeping `except Exception` with a line-targeted `# noqa: BLE001` and a brief justification comment. Treatment (b) is mandatory — not optional — for sites inside graph migrations and authentication flows (hard-constraint areas).
- **FR-004**: No handler may be resolved by widening (e.g., converting to bare `except:` or to `except BaseException:`); the single existing `BaseException` handler MUST end up either narrowed or explicitly justified for intercepting interpreter-exit signals.
- **FR-005**: Narrowed handlers MUST preserve the existing handler body and control flow; the only intended behavioral difference is that exception types the guarded code cannot legitimately raise now propagate instead of being swallowed.
- **FR-006**: Sites in hard-constraint areas (anything under `backend/infrahub/core/migrations/`, and the authentication paths `backend/infrahub/api/auth.py`, `backend/infrahub/api/oauth2.py`, `backend/infrahub/api/oidc.py`, `backend/infrahub/auth/`) MUST have identical runtime semantics after the change — only comments and suppression markers may be added there.
- **FR-007**: The full lint gate MUST pass after the change: `uv run invoke backend.lint` (ruff + ty + mypy over `backend/`) and the repo-wide `uv run ruff check . --exclude python_sdk`, including format checks.
- **FR-008**: Existing tests covering touched modules MUST pass without behavioral test changes; test files that themselves contained violations may only change in their exception-handling annotations, not in what they assert.
- **FR-009**: The change MUST NOT touch: database schema or migration semantics, GraphQL/REST API contracts, authentication/authorization behavior, dependency sets, CI workflow definitions, or generated files. (Editing exception-handler *annotations* inside existing migration/auth files is permitted only under FR-006's identical-semantics rule.)
- **FR-010**: Every added `# noqa: BLE001` MUST be effective (suppress an actual diagnostic) so the codebase stays clean under unused-suppression checking, and MUST be accompanied by a justification comment on or adjacent to the handler.

### Key Entities

- **Violation site**: one flagged `except` clause — identified by file, line, and caught type (`Exception` ×77, `BaseException` ×1); classified into a remediation category (narrow vs. suppress-with-justification) and a risk zone (migration, auth, runtime, test, tooling).
- **Ignore-list entry**: the `"BLE"` string in the `[tool.ruff.lint]` `ignore` array of the root `pyproject.toml` — the single configuration change that activates enforcement.
- **Suppression marker**: a line-targeted `# noqa: BLE001` plus adjacent justification comment — the auditable unit for intentional broad catches.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `uv run ruff check --select=BLE .` from the repository root reports 0 violations (baseline: 78).
- **SC-002**: The CI lint command `uv run ruff check . --exclude python_sdk` and `uv run invoke backend.lint` both exit 0 on the final state of the branch.
- **SC-003**: 100% of intentional broad catches are auditable: the count of `# noqa: BLE001` markers equals the count of justification comments attached to them, and a reviewer can enumerate them with a single search.
- **SC-004**: Zero bare `except:` clauses and zero unjustified `except BaseException:` clauses exist in linted Python code.
- **SC-005**: Test suites covering every touched module pass with unchanged assertions (locally runnable tiers: unit and component; heavier tiers deferred to CI).
- **SC-006**: Introducing a new unjustified blind except into any linted file makes the lint gate fail (verified once by mutation before finishing).
- **SC-007**: Runtime behavior in hard-constraint areas is unchanged: the diff for migration and auth files contains only comment/suppression additions (verifiable by diff inspection).

## Assumptions

- The card's "~32 sites" was accurate at analysis time (2026-02-18) but is superseded by the measured inventory of 78 sites / 46 files on this branch; the scope is *all current violations*, whatever the final count at verification time.
- "No DB schema or migration changes" (hard constraint) is interpreted as *no changes to what migrations do* — adding a comment and a `noqa` marker to an existing migration file does not constitute a migration change; renumbering, semantic edits, or new migrations would. The same interpretation applies to "no auth changes".
- The suppress-with-justification treatment is the *default* for defensive top-level loops (scheduled tasks, telemetry, webhook dispatch, artifact/generator task wrappers) because those handlers exist precisely to keep the worker loop alive against arbitrary failures; narrowing is reserved for handlers guarding a small, analyzable expression.
- "Tests related to touched modules pass" means the locally runnable test tiers (backend unit tests; component tests where practical) for the modules whose files changed; full integration/e2e tiers run in CI as usual and are not a local exit criterion.
- A towncrier `housekeeping` changelog fragment is included (plan decision R7): the change is developer-facing housekeeping with no user-visible behavior change, and the repo has precedent for recording such changes under the registered `housekeeping` type.
- `ruff rule BLE001` (the house method's "understand the rule first" step) confirms the rule flags `except Exception` and `except BaseException` handlers; ruff never flags narrower catches, so narrowing always satisfies the rule.
- The `python_testcontainers/` directory and test-fixture repos carry their own ruff configuration scopes; the authoritative in-scope file set is exactly what the CI command reports.
