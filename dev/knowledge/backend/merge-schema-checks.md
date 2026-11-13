# Schema Checks at Merge and Rebase

> Part of: `dev/knowledge/backend/` | Related: [query-pattern.md](query-pattern.md), [diff-conflicts.md](diff-conflicts.md)

How merge, the merge of a proposed change, and rebase check schema changes against stored data, and which
data each check reads.

## Two views of the default branch

A constraint check reads the data through `get_query_filter_path(is_isolated=...)`:

| View | `is_isolated` | Data read |
|------|---------------|-----------|
| Branch view | `True` | The branch's changes, and the default branch as it was when the branch was created or last rebased |
| Merge view | `False` | The branch's changes, and the default branch's current data |

In the merge view, a node or value changed on both branches resolves to the branch's edge, because the checks order
edges by `branch_level` first. That is the data the merge would write.

The flag travels from `SchemaValidateMigrationData.is_isolated` to `SchemaConstraintValidatorRequest.is_isolated`
and then to `SchemaValidatorQuery.is_isolated`. The query field defaults to `True`, so a new checker or query that
does not pass the flag reads the branch view without an error.

✅ `query = await query_class.init(..., is_isolated=request.is_isolated)`

❌ `query = await query_class.init(...)`

The uniqueness and number checks read the default branch's current data in either view.

## Which constraints run in which view

Merge (`core/merge/constraints.py::MergeConstraintValidator`) and rebase (`core/branch/tasks.py`) split the
constraints into two batches, keyed by constraint name and schema path:

- **Merge view**: the constraints of the source branch's own schema changes since it was created or last rebased,
  with the validators their migrations need (`MergeSchemaAnalyzer.calculate_source_validations`). A node created
  on the default branch after branching that breaks one of these changes refuses the merge or the rebase.
- **Branch view**: every other constraint, from the data diff and from the three-way schema diff
  (`MergeSchemaAnalyzer.calculate_validations`).

Schema changes made on the default branch stay in the branch view, because the candidate schema cannot be trusted
for them. `SchemaBranch.update` builds the candidate by copying the source branch's value of every scalar that
differs, except where the source branch leaves the field unset, which keeps the default branch's value. So a value
that only the default branch changed is replaced by the source branch's older value whenever the source branch sets
that field. Checking that change against the default branch's current data would refuse nodes that the default
branch's schema allows.

## Limits

- A schema change made on the default branch is checked against the branch's data only through the candidate schema,
  which can hold the branch's older value, so the check can miss nodes that break it.
- A dropdown choice removed on the branch is not checked against the default branch's current data:
  `SchemaBranch.update` merges lists of choices and keeps a choice that only the default branch still holds.
- The Schema Integrity check of a proposed change reads the branch view, so it can pass while the merge of the
  proposed change is refused.
