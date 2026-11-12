# Research: Validate schema changes against both branches at merge and rebase

Base: `origin/release-1.12` at `650116308`. The reference implementation is the stash
`migration-validators-wip-2026-11-03` (`110e36f4`), built on `d0d4162bd`. Read its own changes with
`git diff 110e36f4^1 110e36f4` and its new files with `git show 110e36f4^3 --stat`. Between `d0d4162bd` and
`650116308`, `release-1.12` changed only number pool allocation code; the merge, validator and schema code is
identical, so the stash applies as a reference.

## R1. Run the checks of migration-required changes at merge and rebase

- **Decision**: build the constraints from the 3-way diff (changes on both sides since the common ancestor), then
  add the checks of its migrations with the same validator map that a schema load uses.
- **Rationale**: a schema load already does this through the validation result's migration-to-validator step; merge
  and rebase skipped it. Using the 3-way diff covers the changes of both branches (spec FR-001), and each side's
  data can break the other side's change.
- **Alternatives considered**: only the branch's changes (the first plan). Rejected because the default branch's
  changes made after branching would never be checked against the branch's data, which the local matrix showed
  (cases R7–R10).

## R2. Data each check reads

- **Decision**: merge, proposed-change merge and rebase read the merge view (`is_isolated=False`); a schema load or
  schema check on a branch reads the branch view (`is_isolated=True`). The validation message carries the choice as
  a required field, so every caller states it; the per-constraint request keeps a default because it is always built
  from the message inside the validation task, and about 55 tests and one graph migration build it directly.
- **Rationale**: every branch is isolated, so the branch view is what the branch sees, and the merge view is what the
  operation produces: the default branch's current edges, with the branch's edges ranked higher by branch level.
  Choosing per operation keeps schema loads on a branch unchanged (FR-008).
- **Alternatives considered**:
  - Always reading the merge view in the optional, kind and new-attribute queries, as the unique and Number queries
    do. Rejected: it changes which branch schema loads are accepted, which is out of scope (issue 10).
  - Running each query in both views and combining the results. Rejected: the merge view alone covers both
    branches' data at merge, and a schema load only needs the branch view.
- **Queries that take the option**: optional, kind, and the new-attribute query. Queries already fixed to the merge
  view (unique, Number, hierarchy, relationship optional, peer and count) are unchanged. Regex, enum, length and
  choices take the option in the separate pull request for user story 5.

## R3. Check of a new mandatory attribute

- **Decision**: a new query for the new-attribute check returns the active nodes of the kind whose attribute is
  missing, inactive, null or the null marker. The attribute is matched in an optional subquery, because a node
  created before the attribute existed has no attribute vertex. Edge activity follows the usual ordering
  (`branch_level DESC, from DESC, status ASC`).
- **Rationale**: the shared "node not present" query returns every active node of the kind. In the branch view at
  schema load that is correct, because no node can have the new attribute yet; in the merge view it would refuse
  branch nodes that already set a value (accepted case A1).
- **Alternatives considered**: keeping the shared query and filtering in Python. Rejected: it reads every node and
  its attributes into memory for a check the database can answer. The shared query stays for the new-relationship
  check (issue 11 is investigated separately).

## R4. Merge gate (when the schema checks run at merge)

- **Decision**: run the schema checks when the recomputed branch diff contains schema changes, or when the default
  branch's schema and the branch's schema differ by hash in the in-memory registry. Expose it as one analyzer method
  and use it in the merge gate and in rebase.
- **Rationale**:
  - The gate's comment says it uses the freshly recomputed diff "rather than the branch's cached schema-hash flag",
    because the flag stored on the branch can be stale. The stash added that cached flag; this design does not.
  - The recomputed diff holds only the branch's changes, so a change made only on the default branch never opens
    the gate (issue 3).
  - Comparing the two in-memory schema hashes is fresh once the analyzer loads both branches' stored schemas into
    the registry (plan, "Registry freshness"), cheap (it hashes per-kind hashes), and covers both sides: when the
    hashes are equal, every change on either side was already checked when it was loaded, against the data that
    can break it.
- **Alternatives considered**:
  - The cached `schema_differs_from_default_branch` flag (the stash). Rejected for the staleness the comment
    describes.
  - Comparing each side with the common ancestor schema. Rejected: loading the ancestor schema reads the full schema
    from the database at the branch point, which would then run on every merge, including merges without schema
    changes (SC-006).
- **Rebase** gates today on the cached flag; it moves to the same analyzer method so merge and rebase decide the
  same way.

## R5. How to build the merged schema (candidate)

- **Decision**: apply the branch's schema diff since the common ancestor to the default branch's current schema.
  For each kind in the diff:
  - added or removed kind: take the branch's copy, which carries an absent state for a removal;
  - changed kind: copy each changed node-level field from the branch's copy; for attributes and relationships,
    append added elements, take the branch's copy of removed ones, and copy each changed field of a changed element,
    matching elements by id first and by name otherwise;
  - an attribute whose kind changes is rebuilt with the schema class of its new kind;
  - for each changed node kind, its profile and template kinds get the same treatment, using a diff of the
    ancestor's and the branch's profile and template schemas, because the schema diff covers nodes and generics only
    and the checks of changed profile or template nodes read those schemas;
  - an attribute or relationship inherited from a generic carries no id, so it is matched by name.

  Skip the whole step when the two schema hashes are equal. When the default branch no longer holds a kind or an
  element that the branch changed, take the branch's copy, so the branch's change is checked (spec edge case). The
  diff leaves out each generic's `used_by`, so rebuild it from the merged set of kinds. When the branch's own schema
  lacks an element its diff lists, raise an error that names the kind and the element, so a broken build is not
  mistaken for a refusal.
- **Rationale**:
  - It applies exactly the changes the migration step computes from the same diff, so the checks and the migrations
    agree on what the branch changed.
  - It needs no new generic logic on the base model that every schema class inherits; the logic lives on the schema
    branch, its only caller (constitution principle VII).
  - The diff already matches renamed elements by id and is keyed by the branch's names, so a rename on either side
    is followed.
- **Alternatives considered**:
  - The stash's generic 3-way merge (`keep_changes_since` on the hashable base model, about 70 lines, plus
    `update_changes` on the schema branch). It works and passed the local matrix, but it adds a recursive merge to a
    base class for one caller and needed a second fix for kind changes (attribute classes differ by kind).
  - The current `update` of the default branch's schema with the branch's whole schema. Rejected: it restores the
    branch's stale copy of every value that only the default branch changed (verified with a unit test on the
    current code), which weakens the checks (issue 6).
- **Test reuse**: the stash's six schema-branch unit cases and its kind-class case are written against the
  schema-branch method, not the generic merge, so they carry over as the acceptance tests of this design.
- **Known limit**: when both sides changed the same nested value (for example two different parameters of the same
  attribute), the branch's whole value is applied. Schema properties are stored as graph data, so a change to the
  same property on both sides is expected to appear as a diff conflict the user resolves before the merge; a task
  confirms this, and if it does not hold, the limit is recorded in the edge cases.

## R6. Proposed-change schema check

- **Decision**: build the proposed change's merged schema with the analyzer (R5), take its constraints from the
  analyzer (R1), keep its existing data-diff constraints and its schema processing step, and read the merge view
  (R2).
- **Rationale**: FR-009 requires the same violations as the merge. Today the check builds its merged schema with the
  plain `update` and compares the default branch with it, so a change made only on the default branch shows as a
  reversal attributed to the branch.
- **Alternatives considered**: leaving the proposed-change check as it is. Rejected: the reviewer would see a passing
  check on a proposed change whose merge is refused.

## R7. Payload compatibility of the new message field

- **Decision**: make the view field required on the validation message.
- **Rationale**: the message is sent to the validation workflow and the caller waits for its result, so a payload
  does not outlive an upgrade; servers and workers run the same version. A required field turns a forgotten caller
  into an error instead of a silent branch-view read.
- **Alternatives considered**: a default of the branch view. Rejected: the merge, rebase and proposed-change paths
  must not fall back to it.

## R8. Suspected gaps (user story 6)

- **New mandatory relationship at merge**: the check uses the shared "node not present" query in the branch view, so
  at merge it may flag branch nodes that set the relationship, and miss nodes created on the default branch.
  Reproduce first with a component test on the merge view; fix with a relationship-presence query, as R3 does for
  attributes, only if confirmed.
- **Attribute added on the default branch with a default value**: the migration that adds the attribute runs on the
  default branch; branch nodes created before the merge may lack the attribute vertex after the merge. Reproduce with
  an integration test (create a node on the branch, add the attribute with a default on the default branch, merge,
  read the node on the default branch). If confirmed, record it as a follow-up with its reproduction: the fix is in
  the merge migrations, not in the checks.

## R9. Verification approach

- Unit tests for the merged schema (pure in-memory schema branches).
- Component tests against the database for each query in both views, and for the analyzer's constraint list.
- Integration tests for merge and rebase refusals with exact messages, and for the state left after a refusal.
- The local matrix from the stash's investigation (cases R1–R10 refused, A1–A5 and A8 accepted, each through merge,
  proposed-change merge and rebase, on a fresh local instance). See `quickstart.md`.
- Each regression test is run against the code without its fix and must fail.
