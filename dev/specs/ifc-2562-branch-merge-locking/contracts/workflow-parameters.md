# Contract — `merge_holder_id` Workflow Parameter

Every Prefect workflow that writes to a branch participates in coordination. To allow the merge flow to submit follow-on workflows that bypass the merge's own claim, every writer flow's parameter model carries an optional `merge_holder_id` field.

## Parameter

```python
class WriterFlowParameters(BaseModel):
    # ... existing fields ...
    merge_holder_id: str | None = None
    """If set, the flow's body presents this id to BranchLocker.acquire_write
    to bypass the merge_intent check. The merge flow passes its holder_id when
    it submits sub-flows from inside the merge critical section. Default None
    for all other callers — the flow then participates in coordination
    normally and may be rejected with BranchLockedError if a merge is holding
    the relevant branch."""
```

The field is added to every flow parameter model whose flow body executes a write against a branch. The full list is enumerated in `research.md` §C.2.

## Flow body convention

```python
@flow(name="...")
async def my_writer_flow(model: WriterFlowParameters) -> None:
    branch_locker: BranchLocker = service.branch_locker
    async with branch_locker.acquire_write(
        model.branch_name,  # or model.infrahub_branch_name, depending on the flow's existing field
        merge_holder_id=model.merge_holder_id,
    ):
        # existing flow body
        ...
```

The `acquire_write` call is the first awaited operation in the flow body, before any database I/O.

## Caller convention

The merge flow (in `_do_merge_branch`) submits sub-flows with its `holder_id`:

```python
# Inside `acquire_merge` body:
holder_id = ...  # yielded by acquire_merge

await workflow.submit_workflow(
    workflow_definition=catalogue.IPAM_RECONCILIATION,
    parameters={
        "branch": registry.default_branch,
        "ipam_node_details": ipam_node_details,
        "merge_holder_id": holder_id,
    },
)
```

All non-merge callers omit `merge_holder_id` and the field defaults to `None`. No call-site changes are required for normal callers.

## Validation

- `merge_holder_id` is opaque to the workflow; it is forwarded verbatim to `acquire_write`. The locker validates it by comparing against the current `merge_intent` cache value for the named branch.
- A stale `merge_holder_id` (one whose merge has already completed) does not match any current `merge_intent`; `acquire_write` falls through to the normal "no merge in progress" path. No false bypass results.
- A forged `merge_holder_id` from an external client cannot reach this field — workflow parameters are constructed by trusted backend code. (External clients submit GraphQL mutations or REST requests, which do not expose the field.)

## Failure modes

| Scenario | Result |
|---|---|
| Flow runs while merge holds the branch, no `merge_holder_id` set | Flow fails with `BranchLockedError`. Prefect surfaces failure in the run UI. |
| Flow runs while merge holds the branch, `merge_holder_id` matches | Flow proceeds. |
| Flow runs while no merge holds the branch | Flow proceeds (writer key registered for merge-side drain). |
| Flow runs while a different merge holds the branch (impossible under FR-015 single-merge invariant; would mean caller passed an obsolete id) | Flow fails with `BranchLockedError`. |

## Migration

This is an additive parameter with a default. All existing callers continue to work unchanged. The PR that adds the parameter to a flow's model and wraps its body in `acquire_write` is the same PR — they ship together for that flow.
