# Implementation Report — Phase 1 (US1: the ledger stays honest as data moves)

**Status: DONE** — all Phase 1 work is complete and green. The finding previously recorded here as a
blocking regression (§7) was reviewed with the PRD owner on 2026-09-16 and is **by design**.

| | |
|---|---|
| Feature | Numbers you give the pool (IFC-3184) |
| Spec dir | `dev/specs/ifc-3184-pool-number-attach/` |
| Scope run | Phase 1 only (T001–T038); Phases 2–5 untouched |
| Base commit | `ea85f894f` |
| Head commit | `ea85f894f` — **nothing committed, by user instruction** |
| Working tree | 34 paths changed/added, all unstaged |
| Tasks | 37 of 38 done; T036 dropped by the user |

The user asked for no commits and no pushes: everything is left in the working tree to be staged
into atomic commits under their review. The Phase 7 report commit the skill prescribes was therefore
also skipped.

---

## 1. Chunk ledger

Five implementation chunks, each in a clean-context subagent, run strictly sequentially.

| # | Chunk | Tasks | Outcome | Commits |
|---|---|---|---|---|
| 1 | 1a+1b — ground truth, failing repros | T001–T005 | 4 ✅, 1 ⚠️ (T004) | none |
| 2 | 1c — re-anchor the edge | T006–T014 | 9 ✅ | none |
| 3 | 1d+1e — defects, `HAS_SOURCE` exit | T015–T024 | 10 ✅ | none |
| 4 | 1f — migration `m079` implementation | T025–T033 | 9 ✅ | none |
| 5 | 1f/1g/1h — migration tests, SC-022, docs | T034–T038 | 4 ✅, 1 dropped | none |

Plus two orchestrator-run verification passes, two adversarial reviews, and one fix pass (§5).

### Decisions surfaced by chunks

- **T011 was not implementable as written** (chunk 2). `Node.handle_pool` runs inside `obj.new()`,
  before `obj.save()`, so the `Attribute` vertex does not exist at allocation time. Resolved by
  deferring the ledger write to save: `BaseAttribute.pool_reservation_pending`, drained by
  `Node.save()::_write_pending_pool_reservations()`. Phase 2's T042 should absorb this.
- **T016 resolved toward re-target, not re-allocation** (chunk 3). Conversion previously "worked" by
  re-allocating the lowest free number, which equals the old number only by coincidence; for a
  user-`from_pool` number carried by field mapping, nothing re-allocated and the ledger lost the
  number. `PoolChangeReserved` split: IP shapes keep it, new `NumberPoolChangeReserved` for pools.
- **Behaviour 3 is broader than the task text says** (chunk 4). The pre-change writer `CREATE`d a
  record per allocation, so one pool can hold several live records for one object; the collapse
  groups by `attr` regardless of pool.
- **Records are hard-deleted, not time-closed**, in behaviours 2/3/5 — a time-closed loser stays
  visible to a read at an earlier `at` and would reinstate two live records in the past.
- **A latent data-loss bug fixed in passing** (chunk 3): `create.py::allocate_from_resource_pools`
  allocated before `obj_peer.save()`, so the template pool path wrote **no ledger record at all**.
  The pool `HAS_SOURCE` edge was its only trace — and T020 removes that edge.
- **An irreversible data-loss bug in m079, caught by its first real execution** (chunk 5).
  `_ACTIVE_NODE_FOR_RECORD` resolved an object by the single highest-priority `IS_PART_OF` across all
  branches, so an object deleted on a branch while the default branch held it resolved as gone and
  behaviour 2 **hard-deleted its record**. Fixed to resolve per branch, then union.

---

## 2. Tasks not completed

| Task | State | Reason |
|---|---|---|
| T036 | `[ ]` | **Dropped by the user**: component tests cover the upgrade path; no `integration_docker` test, no CI workflow change. (`shard: [a, b]` already existed, so none would have been needed.) |

**T004 is ticked but is not a biting guard** (recorded as ⚠️, not ✅). `tasks.md` asserts it "must
fail before T016"; it cannot. Its subject is a schema-defined `NumberPool` attribute, which
`handle_pool` unconditionally re-allocates, and in its fixture ordering the freed number is also the
lowest free — so re-allocation returns the same number and writes a valid record. The defect is
structurally invisible in that scenario. No assertion was weakened; biting coverage was added instead
as `test_number_pool_object_conversion.py`, verified to fail without the fix. **`tasks.md`'s premise
for T004 is wrong and should be amended.**

---

## 3. Local-pass evidence

All runs: repo root `/home/ajtmccarty/opsmill/infrahub`, branch `pool-number-attach-ifc-3184`,
`INFRAHUB_USE_TEST_CONTAINERS=false` against the running local dev stack, pytest 9.0.3, Python 3.13.9.
Unit tests need no database.

### Final state — every suite green

| Test id | Type | Run command | Passed at | Env | Verbatim |
|---|---|---|---|---|---|
| `component/core/migrations/graph/m079_…/` + `m076_…/` + `migrations/schema/test_node_attribute_add.py` + `resource_manager/` + `templates/` | component | `INFRAHUB_USE_TEST_CONTAINERS=false uv run pytest -q -p no:randomly <those 5 paths>` | 2026-09-16T15:31:59-07:00 | local dev stack | `139 passed in 390.89s (0:06:30)` |
| Full pool surface (`resource_manager/`, `migrations/`, `templates/`, `agnostic_retirement/`, `core/node/`, `graphql/queries/test_resource_pool.py`, `graphql/resource_manager/`, `pools/`, `unit/core/graph/`, `unit/core/query/`, `unit/pools/`) | component + unit | same form, 11 paths | 2026-09-16T~22:05Z | local dev stack | `3 failed, 460 passed, 2 skipped in 842.97s` — all 3 failures fixed in §5 and re-verified above |
| `unit/core/query/test_number_pool_liveness_shape.py` | unit | `uv run pytest -q …` | 2026-09-16T15:21:51-07:00 | n/a | included in `24 passed in 44.14s` |
| `component/core/agnostic_retirement/test_on_node_delete.py::…::test_a_value_freed_by_retirement_is_allocatable_again_from_its_pool` | component | targeted node id | 2026-09-16T~21:00Z | local dev stack | `1 passed in 10.58s` (after orchestrator fix) |

### Guards shown to bite (fix removed → FAIL → restored → PASS)

| Guard | Without the fix | With it |
|---|---|---|
| `test_number_pool_object_conversion.py::test_converting_an_object_moves_its_record_onto_the_new_objects_attribute` (T016) | `1 failed` — `AssertionError: the pool must still account for the number… assert [] == [1]` | passes |
| `test_ordering.py::test_no_stored_pool_source_survives_a_collapse_between_two_pools` (T035) | `1 failed` — behaviour 3 ran first, losing pool's source edge survived | passes |
| `test_branch_disagreement.py` (2 tests, review 3a/3b) | `2 failed` | passes |
| `test_ordering.py` × 2 + `test_reported_figures.py` (behaviour 4 broadening) | `3 failed, 1 passed` | passes |

### Deliberately red during chunk 1 (TDD), green by chunk 3

`test_number_pool_branch_liveness.py` 2 failed → **4 passed** (T018);
`test_number_pool_attribute_rename.py` 1 failed → **1 passed** (T015).

### Not run

- `backend/tests/integration_docker/` — T036 dropped by the user; no file exists.
- `backend/tests/functional/convert_object_type/…::test_convert_number_pool` — last run
  2026-09-16T20:33Z, `1 passed in 28.85s`; not re-run after later chunks (slow, and its guard does
  not bite — see §2).

---

## 4. SC-022 evidence (T037)

Captured on a 7-object / 2-pool / 2-branch database exercising all five behaviours at once.

| | before | after |
|---|---|---|
| alpha util / default / branches | 5.0 / 4.0 / 1.0 | 4.0 / 3.0 / 1.0 |
| alpha in use | `1,2,3,7` | `1,2,4,7` |
| beta (all figures) | `2.0/2.0/0.0`, `3,5` | **identical** |

Two movements, both corrections: alpha stops reporting `3` (an object re-pooled to beta that the old
readers double-counted against *both* pools), and starts reporting `4` (deleted on a branch while
`main` still held it — the old reader let one branch's tombstone speak for all). Both one-sided in the
safe direction. The behaviour-5 deletion changed no figure, asserted explicitly rather than assumed:
both pre-change readers already keyed on the pool's configured attribute name, so an unreadable record
was reported by nobody.

---

## 5. Review findings

Two adversarial reviews (destructive-migration correctness; runtime read/write path), then one fix
pass. Every finding was verified against the code before action.

| Sev | Location | Finding | Disposition |
|---|---|---|---|
| CRITICAL | `number_pool.py` / `resource_manager.py` | Deferred ledger write "reopened" the duplicate-allocation race | **✖️ premise false.** Old `NumberPoolGetFree` wrapped the node join in a **non-optional** `CALL`, and old `handle_pool` also ran before `save()`, so a record naming an unsaved node was dropped and read as free then too. **Pre-existing, not a regression.** → follow-up |
| HIGH | `node_applier.py:166`, `m076/migration.py:460`, **`node_attribute_add.py:115`** | Three writers still put the pool into `HAS_SOURCE`; `_add_source_to_query` prefers a stored edge, so a stale pool wins the source slot forever | ✅ fixed (sweep found the third) |
| HIGH | `m079/queries.py:27` `_TRACKED_ATTRIBUTE_NAME` | `node_attribute` resolved to one cross-branch winner | **✖️ not reachable** — `CoreNumberPool` is `AGNOSTIC`, so only `-global-`/`branch_level=1` edges exist. Hardened anyway (per-branch unanimity, skip-and-report, plus the missing `status`/`to` guard) |
| HIGH | `m079/queries.py:65` `_ACTIVE_NODE_FOR_RECORD` | Per-branch union governs existence but `LIMIT 1` still collapses *which vertex*; two simultaneously-live same-uuid nodes anchor the record on a branch-only copy | ✅ fixed — anchors per live candidate; both-live fixture added |
| MEDIUM | `m079/queries.py:197` behaviour 4 | Source-edge delete scoped to *live* records, so a released reservation's stale edge survives forever | ✅ fixed — now unconditional (also the user's directive) |
| MEDIUM | `resource_manager.py:890`, `:490` | Branchless `SET live.to` closes the record across all branches | **✖️ by design — see §7** |
| MEDIUM | `resource_manager.py:873` | Idempotency guard silently swallows a `provenance` change | ✅ fixed (latent; Phase 2 attach would have hit it) |
| MEDIUM | `node/__init__.py:1249` | `_write_pending_pool_reservations` ignored `save(fields=…)` | ✅ fixed (unreachable today) |
| MEDIUM | `resource_manager.py:547` | Read hard-matched `(n:<pool.node>)` while `NumberPoolChangeReserved` re-targets with no kind check → number re-issued while held | ✅ fixed; `reserved_values_query` signature lost `node_kind` |
| LOW | `graph/index.py:33` | `IS_RESERVED(branch)` index: every consumer expands from a bound node, every record is `-global-` (one distinct key) | recorded — recommend removal; needs no further `GRAPH_VERSION` bump |
| LOW | `m079/queries.py:28` | Non-`OPTIONAL CALL` drops unresolvable pools from B1, B5 *and* validation | ✅ addressed with 3a |

---

## 6. Autonomous decisions

1. **Chunking**: 7 chunks → 5, merging 1d+1e and the 1f/1g/1h tails, to cut context-reading overhead
   after the user flagged elapsed time.
2. **Test budget trimmed mid-run**: named files instead of directories, `-q`, one invocation at the
   end of each chunk. Compensated with two orchestrator-run consolidated passes at natural seams —
   which is what caught the stale `HAS_SOURCE` expectation and the three-test failure.
3. **`speckit-review-run` not used.** It runs six review agents sequentially; substituted two parallel
   adversarial reviews targeted at destructive-migration correctness and the runtime read/write path.
   The comment-rot, type-design and simplification passes were run separately afterwards — see §10.
4. **One finding fixed by the orchestrator directly**: the stale `HAS_SOURCE` expectation in
   `test_on_node_delete.py`, left behind when chunk 3's T020 removed the edge chunk 2 had asserted.
5. **Fix-pass instructed to verify before fixing** — which is how the CRITICAL and 3a were caught as
   non-findings rather than "fixed" on a reviewer's say-so.

---

## 7. Reviewed and closed — the branchless record close is by design

Both reviewers, and this orchestrator, initially read
`resource_manager.py:890-892` (`NumberPoolSetReserved`) and the identical construct at `:490-492`
(`NumberPoolChangeReserved`) as a regression:

```cypher
OPTIONAL MATCH ()-[live:IS_RESERVED]->(attr)   -- anonymous start node: every pool's record
WHERE live.status = "active" AND live.to IS NULL
SET live.to = $at
```

**It is not.** It implements the ledger's stated contract, confirmed by the PRD owner on 2026-09-16:

1. `IS_RESERVED` is branch-agnostic (`rel_prop["branch"] = global_branch.name`, `:864`).
2. An attribute has **at most one pool at any point in time** — which is precisely what the unbound
   `()` enforces. Binding it to `pool` would permit two.
3. A pool change made on **any** branch applies to **all** branches.

The docstring at `:820` already states this. The review flagged it by assuming pool ownership should
be branch-scoped; that assumption is wrong. Under the real contract, after a branch re-pools an
attribute from P to Q, the default branch's value belongs to **Q**, so P correctly stops accounting
for it — there is no double-allocation.

Two consequences follow and are worth recording:

- **Ownership moves globally; the value does not.** After a branch re-pool, the default branch still
  displays the old number, now owned by Q — a number Q never issued, possibly outside Q's range.
  `NumberPoolGetFree` filters by range and ignores it; `get_used`/utilization are worth a look.
  Inherent to "ownership global, values branch-scoped", not a defect.
- **A provisional change has a permanent global effect.** A re-pool on a branch takes effect on the
  default branch immediately. If that branch is abandoned rather than merged, Q's ownership persists
  and P's record stays closed, from a change that was discarded. Nothing cleans this up — see
  follow-up 4 (branch delete does not close records; node delete does). Not specific to re-pooling:
  allocating on an abandoned branch leaks the same way. Re-pooling makes it more visible.

**Recommended**: state the provisionality consequence explicitly in
`contracts/reservation-ledger.md`, since it is the non-obvious part of an otherwise clean rule.

## 8. Follow-ups for triage

1. **`NumberPool.node` / `node_attribute` are plain editable `Text` attributes** — no `read_only`.
   The user identified this independently; the review showed changing them is an active data-loss
   vector, not just future hygiene.
2. **Pre-existing duplicate-allocation race** — `get_taken()` only guards `if attribute.unique`, so a
   non-unique pool attribute has no fallback at all.
3. **Object conversion does not carry the value** — the replacement re-allocates, so converting an
   object whose number is not the lowest free silently hands it a different number. Post-re-anchor
   the record cannot fix this (it no longer stores the value).
4. **Branch delete still leaks records** — node delete now closes them via
   `close_unretained_agnostic_fields`; branch delete does not.
5. **Remove the `IS_RESERVED(branch)` index** (§5 LOW).
6. **Template/profile source copy** — `node_applier.py:79`, `create.py:180` copy `source_id` onto the
   instance; not reachable today, but the one remaining path by which a pool could become a stored
   source.
7. **Amend `tasks.md`'s T004 premise** (§2).
10. **Optional — write the reservation inside `NodeCreateAllQuery` and delete
    `pool_reservation_pending` altogether.** Today `_create` issues one query for the node, its
    attributes and their property edges, then `save()` issues a *second* query for the reservation;
    the field exists only to carry the pool id across that gap. `core/query/node.py:331-338` already
    does the needed shape for `HAS_SOURCE` — inside the same `CALL` that runs
    `CREATE (a:Attribute …)`, a `FOREACH` locates a pre-existing node by uuid and creates an edge to
    it. `IS_RESERVED` is the same operation with the arrow reversed.

    The pool id is **already on the attribute**: `from_pool` holds `{"id": …}` and is populated in
    both allocation cases (`node/__init__.py:451` for the template relationship, `:454-455` for a
    user-supplied pool). With no gap to bridge there is no "pending" state to track, so
    `get_create_data` (`attribute.py:707`) can read `from_pool["id"]` next to `self.source_id` and
    the field disappears — along with `_write_pending_pool_reservations` and its `fields` gate, which
    is where the one correctness bug of the second review round lived (§10).

    Gains: the value and its record become atomic (today there is a window with one and not the
    other), one fewer round-trip per create, and a whole mechanism deleted. Does **not** fix the
    allocation race (the record still lands after `get_resource`'s lock releases), and the
    update/re-pool path still needs `NumberPoolSetReserved`'s close-then-create.

    Three caveats: the reservation edge is `-global-` with `identifier`/`provenance`, so it needs its
    own property literal rather than `%(attr_edge)s`; `MERGE (peer:Node {uuid: …})` would fabricate a
    phantom pool vertex on a bad id, so it wants a `MATCH` in a `CALL`; and the `FOREACH` block is
    duplicated four times (`node.py:331, 353, 377, 406`) across the plain/indexed/iphost/ipnetwork
    variants, in the hottest write path in the product.

    Deferred deliberately: Phase 1 is reviewed and green, and the bug this would have prevented is
    already fixed. Natural fit for Phase 2's T042 ("`handle_pool` becomes an executor"), which
    reopens this code anyway.
8. **`NumberPoolGetAllocated` still uses the pre-fix liveness rule** while `NumberPoolGetUsed` uses the
   union — they can disagree about whether a number is taken (§10).
9. **`repositories/` is neither gitignored nor ruff-excluded** (§9).

---

## 9. Post-implementation cleanup (completed 2026-09-16)

| # | Item | Outcome |
|---|---|---|
| 1 | Branchless record close | **Closed — by design**, see §7 |
| 2 | `/pre-ci` against the final tree | **Pass.** Every applicable check green; scoped to the branch, `ruff check backend` and `ty check backend` both report *All checks passed*, and all four generated-artifact validations show zero drift |
| 3 | Delete the duplicate spec artifact | **Done.** `ruff check` 41 → 18 errors, `ty` 28 → 15, `ruff format --check` clean — every remainder is in `repositories/` |
| 4 | Amend T004's premise in `tasks.md` | **Done.** "Must fail before T016" struck, with the reason and a pointer to the guard that does bite |

### Pre-CI residue — none of it caused by this branch

- **`repositories/` is neither gitignored nor ruff-excluded.** It is created by the dev stack
  (`INFRAHUB_GIT_REPOSITORIES_DIRECTORY` defaults to `repositories`,
  `development/docker-compose.yml:84`), so every developer running the local stack sees 18 ruff
  errors and 15 `ty` diagnostics that CI never sees. Worth a `.gitignore` or ruff `exclude` entry in
  a separate change.
- **3 backend unit tests fail on local git 2.34.1.** `backend/tests/unit/git/test_git_repository.py`
  uses `git merge-tree --write-tree`, which needs git ≥ 2.38. Untouched by this branch; passes in CI.

## 10. Second review round (comments / types / simplification)

Run after the cleanup above, over the final tree. These are the three passes §6.3 originally skipped.

| Sev | Location | Finding | Disposition |
|---|---|---|---|
| HIGH | `node/__init__.py:1258` vs `:1174` | `_write_pending_pool_reservations` and `_update` disagreed on `fields`: `fields=[]` wrote every value but drained no record, and `_create` takes no `fields` yet `save()` forwarded it — on the very path where the deferred write matters | ✅ **fixed**, with a regression test proven to bite (`assert 0 == 1`). **Introduced by the first fix pass** when it addressed finding 4c |
| HIGH | `m079/queries.py:38` | Claimed the migration's liveness check matches `NumberPoolChangeReserved`'s; it is deliberately stricter (order-then-filter, `$at`-bounded, tombstone silences the branch) | ✅ fixed |
| HIGH | `m079/queries.py:324` | Routed behaviour 5's record class to behaviour 2 | ✅ fixed |
| MED | `resource_manager.py:421` | "same close-then-create guard" — the other lacks the provenance clause | ✅ fixed |
| MED | `object_conversion.py:161` | "Deleting the node closes its pool records" — only for branch-agnostic attributes | ✅ fixed |
| MED | `graphql/mutations/profile.py:76` | **The comment T024 rewrote was itself self-contradictory** | ✅ fixed |
| MED | `resource_manager.py:252` | `NumberPoolGetReserved` uses the resolution `reserved_values_query` argues against, with no docstring saying why | ✅ fixed |
| LOW ×4 | `m079/queries.py:16`, `migration.py:109`/`:114`, `resource_manager.py:281`, `queries.py:172` | Over-broad scope claim; operator-facing counts labelled "attribute(s)" while counting records and edges; overstated claim; behaviour 3 described as multi-pool when it keys on record count | ✅ all fixed |
| LOW | `resource_manager.py:326` | `get_reservations()` was a one-line wrapper over `get_data()` with no other caller | ✅ deleted |
| — | `m079/queries.py:251` | Spec ID in a source comment, forbidden by `.agents/rules/code-doc-style.md:35` | ✅ removed (orchestrator); `backend/` now has none |

**Recorded, not changed — worth a follow-up.** `NumberPoolGetAllocated` (`resource_manager.py:208`) and
`NumberPoolGetUsed` (`:617`) both answer "which values does this pool account for" but use **different
liveness rules**: the former keeps the single-winner `all(r in [ha, hv, ir] WHERE branch_filter)`, the
latter the per-branch-then-union rule `test_number_pool_liveness_shape.py` exists to protect. They can
therefore disagree about whether a number is taken, and `NumberPoolGetAllocated` feeds utilization
(`pools/number.py:37`) and the GraphQL pool view. It cannot be merged mechanically — it needs the
per-branch attribution the union discards. The divergence is now stated in its docstring. **The
cross-branch liveness fix was applied to one read path and not its sibling.**

**Three simplifications proposed and declined by the PRD owner** (2026-09-16): folding the range filter
into `reserved_values_query` with a shared base class; extracting the close-then-create tail; extracting
`_HAS_TRACKED_ATTRIBUTE` in `m079`. Reason: `%`-interpolated Cypher fragments make the query text harder
to read, which matters most in a destructive migration. A cross-reference comment between behaviour 5's
delete predicate and the validator that audits it was also declined.

**Type-design findings left as Phase 2 input**: `pool_reservation_pending` is a pool id in a `str`
doubling as a pending flag, crossing a module boundary as an untyped dict key; m079's
`pre_count`/`pre_message` are two Optionals encoding one fact; `_sweep` accepts any count/delete class
pair, so a mismatched pair type-checks. None cause a bug today.

**Unexamined, not clean** — the simplification reviewer did not reach: the `m076` and
`attribute_rename.py` diffs, `backend/tests/db_snapshot.py`, `tests/helpers/agnostic_edges.py`, and the
functional `test_convert_object_type.py` changes.

## 11. Suggested next steps

1. Stage and review in atomic slices. A natural order: (a) read/write query re-anchoring, (b) the
   deferred-ledger-write mechanism, (c) the two defect fixes (rename `-global-`, conversion
   re-target), (d) the `HAS_SOURCE` exit + derived source, (e) migration `m079` + its tests,
   (f) docs + changelog.
2. Nothing is outstanding: §7 is closed, §9 is complete, §10's findings are fixed or recorded.
3. Phase 2 starts only after this change set merges (SC-022 is measurable only at this boundary).
