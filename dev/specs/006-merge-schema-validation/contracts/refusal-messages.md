# Contract: Refusal messages for merge, proposed-change merge and rebase

The feature adds no endpoint, mutation or field. Its interface is the error that the existing operations return when a
check finds a violation. The message formats below already exist for a schema load; this feature makes merge and
rebase return them too. Tests assert them with exact equality.

## Operations and error carriers

| Operation | Interface | Error on violation |
|---|---|---|
| Branch merge | `BranchMerge` mutation, SDK `client.branch.merge` | GraphQL error, one message per violation |
| Proposed-change merge | `CoreProposedChangeMerge` mutation | The merge's violations; when the proposed change's checks have failed, the existing "Unable to merge proposed change containing failing checks" |
| Branch rebase | `BranchRebase` mutation, SDK `client.branch.rebase` | GraphQL error, one message per violation, each with the constraint suffix below |
| Proposed-change schema check | The proposed change's schema integrity check | A failed check listing the same violations as the merge |

## Message format

```text
<Level>-level '<check>' constraint violation on schema '<Kind>'. Node (<node label>) is not compliant.[ The error relates to field <field>=<value>.]
```

At rebase, each message ends with:

```text
 for constraint <constraint name> <attribute or field> <property> and node <node id> <Kind>
```

`<node label>` is the node's existing display form, for example `TestingLamp(ID: <id>)` or `TestingLabel: <id>`;
this feature does not change it.

## Messages per check

| Check | Example |
|---|---|
| Attribute made unique | `Attribute-level 'unique' constraint violation on schema 'TestingPass'. Node (TestingPass: <id>) is not compliant. The error relates to field code='P-1'.` |
| Attribute made mandatory | `Attribute-level 'optional' constraint violation on schema 'TestingLabel'. Node (TestingLabel: <id>) is not compliant.` |
| Mandatory attribute added without a default value | `Node-level 'attribute' constraint violation on schema 'TestingPlug'. Node (TestingPlug: <id>) is not compliant.` |
| Attribute kind changed | `Attribute-level 'kind' constraint violation on schema 'TestingMeter'. Node (TestingMeter(ID: <id>)) is not compliant. The error relates to field size='big'.` |
| Uniqueness constraint added | `Node-level 'uniqueness_constraints' constraint violation on schema 'TestingPass'. Node (TestingPass: <id>) is not compliant. The error relates to field code.value='P-1'.` |
| Number pool scope attribute removed | `'number_pool.scope' constraint violation on schema 'CoreNumberPool'. Node (<pool name>) is not compliant. The error relates to field role='pool <pool name> divides its numbers by <Kind>.role; a scope element cannot be removed while the pool exists'.` |
| Number pool scope attribute made optional | Same as above, ending `a scope element must stay required'.` |

Rebase example (attribute kind changed on the default branch):

```text
Attribute-level 'kind' constraint violation on schema 'TestingMeter'. Node (TestingMeter(ID: <id>)) is not compliant. The error relates to field size='big'. for constraint attribute.kind.update size kind and node <id> TestingMeter
```

## State after a refusal

- The branch status stays `OPEN`.
- The schema and data of both branches are unchanged, and the branch's branch point is unchanged after a refused
  rebase.
- A retry after fixing the data succeeds for merge and rebase; a proposed change needs its checks to run again.
