# Data Model: One branch deletion records the same number of task runs whatever the number of open branches

**Feature**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

This change adds no entity, field, relationship, table or migration. It changes how many task-run records one flow run writes. The entities below are the existing ones the change touches. The invariant at the end is what the tests check.

## Existing entities

### Branch (Infrahub graph database)

- Read from the worker's branch registry.
- Each gather visits every branch that is not global, in registry order.
- The deleted branch can still be listed on a worker whose registry has not been refreshed. See the edge case in the spec.

### Python computed attribute (schema)

- An attribute whose `computed_attribute.kind` is `TransformPython`, wired to a transform by name or UUID.
- Read per branch from the branch's schema (`python_attributes_by_transform`).

### Python transform (`CoreTransformPython`, graph database)

- Fields read by the gather: `name`, `repository` (peer), `query` (peer).
- A missing peer on one branch makes the gather of that branch fail. See research R4 and R6.

### Node-input automation (task manager)

- Trigger types: `COMPUTED_ATTR_PYTHON`, one per attribute, and `COMPUTED_ATTR_PYTHON_QUERY`, one per kind that the transform's query reads.
- Ownership: each automation belongs to one branch. The default-branch automation lists the branches it excludes, which are the branches whose repository commit differs from the default branch's.
- Lifecycle: the reconcile rebuilds the full set under the trigger-registry lock. It creates the missing automations, updates the changed ones and deletes the ones it no longer produces. A deleted branch's automations are removed this way.
- This change does not alter how the set is computed.

### Flow run, task run, task-run state, log (task manager database)

- One task run per call of a Prefect `@task` inside a flow run, written by the Prefect server from the task-run state events.
- Each task run has about 3 state rows. About 480 bytes of each state row is the `state_details` JSON.
- Deleting a flow run deletes its task runs and their states through the database's cascade rules, and the Prefect API deletes its logs in a background job. See the spec's Resolved Clarifications.

## Invariant on task runs

For a fixed schema and a fixed set of Python transforms, the number of task runs in one run of each flow below does not depend on the number of branches that are not global.

| Flow | Event | Requirement |
|------|-------|-------------|
| `computed-attribute-setup-python` | `infrahub.branch.deleted` | FR-001 |
| `computed-attribute-setup-python` | `infrahub.schema.updated` | FR-003 |
| `computed-attribute-process-transform-lifecycle` | Python transform created, updated or deleted | FR-003 |

From the code, the first two hold 4 task runs per run and the third holds 3 for a delete. Tests compare counts across branch numbers instead of pinning these numbers (research R2).

## State of the gather after the change

```text
gather_trigger_computed_attribute_python   (one task run)
  └── for each branch that is not global:
        gather_python_transform_attributes   (plain call, no task run)
          ├── transform missing on the branch → warning naming the branch and the transform
          └── any exception → note naming the branch added, exception re-raised unchanged
  └── group the results per attribute and build the trigger definitions (unchanged)
```
