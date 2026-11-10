# Data Model: Validate schema changes against both branches at merge and rebase

No graph vertex, edge, index or GraphQL type changes. The entities below are in-memory objects and messages.

## Schema views

| View | Reads | Used by |
|---|---|---|
| Branch view (`is_isolated=True`) | The default branch as it was when the branch was created, plus the branch's changes | Schema load and schema check on a branch; core schema update (on the default branch, where both views read the same data) |
| Merge view (`is_isolated=False`) | The default branch's current data, with the branch's edges ranked higher by branch level | Merge, proposed-change merge, rebase, proposed-change schema check |

## Validation message (`SchemaValidateMigrationData`)

| Field | Type | Rule |
|---|---|---|
| `branch` | Branch | The branch the checks run on (the source branch for merge and rebase) |
| `schema_branch` | Schema branch | The merged schema for merge, rebase and proposed change; the candidate schema for a schema load |
| `constraints` | list of constraint info | Each constraint names a check and a schema path |
| `is_isolated` | bool, required | The view; no default, so every caller states it |

The serialized form includes `is_isolated`, and a round trip keeps its value.

## Per-constraint request (`SchemaConstraintValidatorRequest`)

Gains `is_isolated: bool`, default `True`. The validation task always sets it from the message.

## Schema-change gate

True when either:

1. the recomputed branch diff contains a schema node, attribute or relationship change; or
2. the source and destination schema hashes in the registry differ.

False otherwise. When false, merge and rebase run only the data-diff constraints.

## Merged schema rules

Inputs: the destination's current schema (D), the branch's current schema (S), and the branch's schema diff since
the common ancestor (diff of A to S). Output: a copy of D with the diff applied.

1. When the hashes of D and S are equal, return a copy of D.
2. For each kind the diff lists as added or removed: take S's copy (a removal carries the absent state).
3. For each kind the diff lists as changed, find D's copy by id, otherwise by name; when D no longer holds the kind,
   take S's copy:
   - copy each changed node-level field from S;
   - for attributes and relationships:
     - added in S: add S's element;
     - removed in S: take S's element with its absent state, or leave it out when S no longer holds it;
     - changed in S: find D's element by id, otherwise by name, and copy each changed field from S's element; when
       D no longer holds the element, take S's element;
   - when an attribute's `kind` changes, rebuild it with the schema class of its new kind, so its parameters match;
   - an inherited element has no id of its own, so it is matched by name.
4. For each changed node kind, apply rule 3 to its profile and template kinds too, with a diff of the ancestor's and
   the branch's copies of those kinds.
5. Values the diff does not list keep D's value, including every change made only on the default branch.
6. The diff leaves out the list of node kinds that use a generic (`used_by`), so each generic's list is rebuilt: a
   kind the diff lists takes its membership from S, any other kind keeps its membership from D, and a kind the
   merged schema does not hold is left out.
7. An attribute or relationship the diff lists as added or changed that S does not hold raises an error naming the
   kind and the element; the diff is computed from S, so this is an internal fault, not a refusal.

Expected results, from the unit cases:

| Case | Result |
|---|---|
| D made an attribute mandatory; S changed another kind | The attribute stays mandatory |
| D changed an attribute's kind (and schema class); S changed another attribute | The new kind and its parameters class stay |
| D and S both changed the same description | S's value |
| D and S each added an attribute | Both attributes are present |
| D removed an attribute that S did not change | The attribute is absent |
| D removed a kind that S did not change | The kind is absent |
| D renamed an attribute; S changed another field of it | Both changes, under the new name |
| D changed an attribute of a generic; S changed a node that inherits it | The node holds D's change to the inherited attribute and S's own change |
| S changed an attribute of a node that has a profile | The profile kind's copy of the attribute holds S's change |
| D removed an attribute that S changed | S's version of the attribute is present and checked |
| D removed a kind that S changed | S's version of the kind and its profile kind are present and checked |
| D and S each added a node that inherits a generic | The generic's `used_by` lists both nodes |
| D and S each removed a node that inherits a generic | The generic's `used_by` lists neither node |

## Constraint sources at merge and rebase

| Source | Built from | Covers |
|---|---|---|
| Data-diff constraints | Nodes changed on the branch, checked against the merged schema | Branch data against every schema rule |
| Schema-diff constraints | The 3-way schema diff plus the checks of its migrations | Data of both branches against each schema change made since the branch was created |

The two lists are merged by the existing constraint merger, keyed by constraint name and schema path.
