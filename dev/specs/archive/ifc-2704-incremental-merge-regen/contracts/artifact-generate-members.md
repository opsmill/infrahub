# Contract: Artifact-definition-generate member filter

**Plan**: [../plan.md](../plan.md) · **Decision**: D5 (the "limit trap")

## Problem

`RequestArtifactDefinitionGenerate.limit` (`git/models.py:19-28`) is matched in
`generate_request_artifact_definition` (`git/tasks.py:594-598`) against
`artifacts_by_member.get(member.id)` — the member's **existing** artifact id, or `None` when
the member has no artifact yet:

```python
for relationship in group.members.peers:
    member = relationship.peer
    artifact_id = artifacts_by_member.get(member.id)   # existing artifact id or None
    if model.limit and artifact_id not in model.limit:
        continue                                        # None not in limit -> NEW member skipped
```

A selective merge that computed impacted **existing** artifact ids and passed them as `limit`
would silently drop members added on the merged branch (no prior artifact) → under-execution.

## Change

Add a member-node-id filter to `RequestArtifactDefinitionGenerate`:

```python
members: list[str] = Field(
    default_factory=list,
    description="Member node ids to generate artifacts for; when populated, only these members are processed.",
)
```

Consume it in `generate_request_artifact_definition` mirroring the generator's `target_members`
(filter on `member.id`, not on the existing artifact id):

```python
for relationship in group.members.peers:
    member = relationship.peer
    if model.members and member.id not in model.members:
        continue
    ...
```

## Semantics & compatibility

- `members` is keyed on the **member node id** — identical to
  `RequestGeneratorDefinitionRun.target_members` (`generators/tasks.py:224-228`), which is
  already safe for new members.
- `members` and `limit` are independent filters. `members` defaults to empty → **no behavior
  change** for existing callers that use `limit` or neither.
- The merge selection path uses `members` exclusively and never sets `limit`.
- Precedence if both were ever set: apply both (a member must pass both filters). The merge
  path never sets both, so this is not exercised by this feature.

## Verification

- Grep all submitters of `REQUEST_ARTIFACT_DEFINITION_GENERATE` / callers constructing
  `RequestArtifactDefinitionGenerate`; confirm none regress with the new default-empty field.
- Unit test: a group with one existing-artifact member and one new (artifact-less) member,
  `members=[both ids]` → both processed; `members=[]` → all processed (current behavior).
