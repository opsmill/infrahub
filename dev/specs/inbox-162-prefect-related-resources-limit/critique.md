# Critique: Align Infrahub's event related-resource cap with Prefect's effective limit

**Date**: 2026-09-07 | **Inputs**: [spec.md](./spec.md), [plan.md](./plan.md), [research.md](./research.md)

**Verdict**: ✅ **PROCEED** — the spec and plan are proportionate to a one-module fix, the research
is empirical rather than assumed, and the risky part (the test-mechanism change) is identified
rather than glossed over. Three 🎯 Must-Address findings were applied before tasks generation; they
are recorded below with what changed.

---

## Lens 1 — Product / Value

### 🎯 P1 (Must-Address, APPLIED): the headline benefit was overstated for the unconfigured case

The spec's SC-001 originally implied unconfigured deployments get their events *back*. That is true
only for events whose related-resource count sits between the new budget (80) and the old one (450).
An unconfigured deployment mutating, say, 3,000 related nodes still loses everything above 80 — it
now gets a *truncated* event instead of *no* event. That is a real improvement (an event that fires
automations beats silence), but "no events are lost" would be wrong.

**Applied**: SC-001 already scopes the claim to "produces exactly one delivered event", not "no
related resources are lost", and the spec's Assumptions section states plainly that truncation
remains the response and chunking is out of scope. Verified this reading is consistent across
spec.md and the changelog guidance in plan.md D4. No further edit needed — flagged so the PR
description does not overclaim.

### 💡 P2 (Recommendation, APPLIED): the reduced budget deserves explicit acknowledgement

For an unconfigured deployment the per-event budget *drops* from 450 to 80. Anyone reading only the
title ("stop hardcoding 500") could reasonably expect capacity to be unaffected. It isn't — it gets
smaller, and that is the correct outcome, because the 450 was a fiction Prefect never honoured.

**Applied**: added as an explicit row in research.md R7's behaviour-delta table and as a Risk in
plan.md ("Reduced budget (450→80) surprises an unconfigured deployment"). plan.md D4 requires the
changelog to state it.

### 🤔 P3 (Question, RESOLVED): should the shipped image's 500 stay?

Resolved: **yes, unchanged.** Two independent reasons. (1) FR-006 exists precisely to keep shipped
behaviour bit-for-bit identical — changing both the resolution mechanism *and* the shipped value in
one change would make any regression impossible to attribute. (2) 500 is a deliberate operational
choice for the image (larger events, fewer truncations) and is legitimate *because the image also
raises Prefect's own limit to match*. The bug was never the 500; it was assuming 500 everywhere.

### 💡 P4 (Recommendation, ACCEPTED AS-IS): operator-facing, not end-user-facing

The spec's "user stories" are operator stories. The template asks for user journeys; the honest
mapping here is deployment operators, since the observable symptom is "my automation did not fire".
Noted in `checklists/requirements.md` rather than contorted into an end-user narrative.

---

## Lens 2 — Engineering Risk

### 🎯 E1 (Must-Address, APPLIED): the test-mechanism change was the real risk and needed to be load-bearing

The natural, careless version of this change edits `limits.py` and leaves
`test_limits.py`'s `monkeypatch.setenv` alone. Because Prefect snapshots settings at import
(research.md R4), every parametrized case would then stop driving the value at all. The failure is
loud (expectations mismatch), so it would be caught — but only *after* someone spends time
confused, and the tempting "fix" is to weaken the assertions rather than change the mechanism.

**Applied**: research.md R4 states the mechanism with its verification output and calls it "the
single highest-impact finding"; plan.md D3 makes the migration an explicit design decision; and it
is the top entry in plan.md's Risks table. tasks.md sequences the migration as its own task, before
the new coverage, so the suite is green on the new mechanism before anything is added.

### 🎯 E2 (Must-Address, APPLIED): new tests must assert derived budgets, not literals

A test asserting `len(related) == 80` passes whether or not the cap actually tracks the setting — it
would keep passing if `get_related_resource_budget()` were reverted to a constant. The whole point
of the card is that the number *follows* the setting.

**Applied**: plan.md D3 requires the two new node-action tests to assert against a budget derived
from the maximum, and calls out that "a literal would still pass if the derivation broke". Carried
into the corresponding tasks.

### 🎯 E3 (Must-Address, APPLIED): the unreachable-guard decision needed justifying, not just doing

Deleting the `try/except ValueError` is correct (research.md R5: Pydantic raises at settings
construction, before Infrahub runs), but silently deleting a defensive branch in a module whose
entire job is defensive looks like carelessness to a reviewer, and it *is* a user-visible behaviour
change — a typo that used to degrade quietly now stops the process at startup.

**Applied**: research.md R5 tabulates each value class against reachability with the verification
output; plan.md D2 records the decision and its rationale; plan.md D4 requires the changelog to
mention it; quickstart.md §5 gives a reproduction. This is now a documented decision rather than an
incidental deletion.

### 💡 E4 (Recommendation, APPLIED): don't let the non-positive guard imply more than it delivers

With a maximum of `0` Prefect rejects every event with any related resource, so returning 100
instead rescues nothing. If the docstring says the fallback keeps events flowing, it is lying.

**Applied**: plan.md D2 and research.md R5 both state the guard's actual, narrower purpose — keeping
the derived arithmetic positive — and explicitly say it does not rescue delivery. The implementation
task carries this into the docstring wording.

### 💡 E5 (Recommendation, APPLIED): scope discipline against the parent issue

Issue #10127 is *primarily* about `GroupMutatedEvent`'s unbounded related list. That is a bigger,
riskier fix (it needs a truncation strategy for a path that currently has none) and `group_action.py`
already imports the budget helper, which makes it look adjacent enough to "just do too". Pulling it
in would blow the S-effort estimate and mix two behaviour changes in one PR.

**Applied**: spec.md has an explicit "Out of Scope" section naming it, and research.md R6 notes the
import without treating it as in-frame.

### 🤔 E6 (Question, RESOLVED): `PREFECT_EVENTS_…` or `PREFECT_SERVER_EVENTS_…` as the accessor?

Resolved in favour of `PREFECT_EVENTS_MAXIMUM_RELATED_RESOURCES` — **not** on style grounds but
because it is the literal expression inside Prefect's own `_validate_related_resources`. Verified
the two are true aliases returning identical values under either override (research.md R1/R3), so
the choice is behaviourally neutral today; sharing the enforcer's own expression is what makes
future divergence impossible. Documented as R1's rationale.

Note the tests override via `PREFECT_SERVER_EVENTS_MAXIMUM_RELATED_RESOURCES` (the name the shipped
image and the existing tests use) while the implementation reads the other. That asymmetry is
deliberate and valuable: it *proves* the alias equivalence rather than assuming it.

### 💡 E7 (Recommendation, APPLIED): pin the pre-change baseline

Without a recorded baseline, "existing tests still pass" is unfalsifiable after the fact.

**Applied**: research.md R8 records **59 passed** for the relevant suites before any production
edit, along with the worktree/submodule setup required to get there.

---

## Constitution re-check (post-design)

Re-ran plan.md's Constitution Check against `dev/constitution.md` after the design settled. No
change: PASS, no violations, no Complexity Tracking entries. Principle IV (Test Discipline) is the
most engaged and is satisfied at the unit level with no mocking — the tests drive Prefect's real
settings and assert against Prefect's real validator.

## Findings summary

| ID | Lens | Severity | Status |
|---|---|---|---|
| P1 | Product | 🎯 Must-Address | Applied (claim scoped in SC-001 + Assumptions) |
| P2 | Product | 💡 Recommendation | Applied (R7 table, Risks, changelog requirement) |
| P3 | Product | 🤔 Question | Resolved (image keeps 500) |
| P4 | Product | 💡 Recommendation | Accepted as-is (documented in checklist) |
| E1 | Engineering | 🎯 Must-Address | Applied (R4, D3, top Risk, own task) |
| E2 | Engineering | 🎯 Must-Address | Applied (D3 derived-budget rule) |
| E3 | Engineering | 🎯 Must-Address | Applied (R5, D2, D4, quickstart §5) |
| E4 | Engineering | 💡 Recommendation | Applied (guard scoped honestly) |
| E5 | Engineering | 💡 Recommendation | Applied (Out of Scope section) |
| E6 | Engineering | 🤔 Question | Resolved (mirror the enforcer) |
| E7 | Engineering | 💡 Recommendation | Applied (baseline 59 passed, R8) |

No 🛑 RETHINK findings. Proceeding to task generation.
