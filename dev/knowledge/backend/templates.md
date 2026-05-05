# Object Templates

> Part of: `dev/knowledge/backend/` | Related: [Schema Definitions](schema-definitions.md), [Code Generation](code-generation.md), [Display Labels and HFID](display-labels-and-hfid.md)

Object Templates are user-defined "shape" objects: a template node holds default attribute values and relationships, and creating an object that references the template copies those values onto the new object. The user-facing concepts live in `docs/docs/topics/object-template.mdx`; this doc covers the backend machinery.

## File Map

| Path | Purpose |
|------|---------|
| `backend/infrahub/templates/node_applier.py` | Reads a saved template node and merges its values into the field dict for a new instance. |
| `backend/infrahub/core/schema/template_schema.py` | `TemplateSchema` model — the schema-time representation of an auto-generated `Template*` kind. |
| `backend/infrahub/core/schema/definitions/core/template.py` | `core_object_template` and `core_object_component_template` generics — the core base kinds every template inherits from. |
| `backend/infrahub/core/schema/schema_branch.py` | Generation of per-kind template schemas from `generate_template`-enabled nodes (`manage_object_template_schemas`, `add_relationships_to_template`, etc.). |
| `backend/infrahub/core/relationship/constraints/template_resource_pool_exclusive.py` | Constraint preventing both a fixed value and a pool reference being set on the same template field. |
| `backend/infrahub/core/node/create.py` | `handle_template_relationships()` recursively materializes component-template peers as real instances. |
| `backend/infrahub/core/node/__init__.py` | `Node._apply_template()` (around line 480) is the call site that invokes `NodeTemplateApplier` during `Node.new()`. |

## Core Kinds

Every auto-generated template kind transitively inherits from one of two core generics defined in `core/schema/definitions/core/template.py`:

- `CoreObjectTemplate` — for the user-facing template kinds (one per node with `generate_template: true`).
- `CoreObjectComponentTemplate` — for sub-templates auto-generated for component peers (see [Subtemplates](#subtemplates)).

The kind name is mechanical: a template for `InfraDevice` becomes `TemplateInfraDevice`, computed by `SchemaBranch._get_object_template_kind()` (`schema_branch.py:2532`).

## Schema Generation Flow

Template schemas are generated during schema processing in `process_pre_validation` (`schema_branch.py:633` flow), in this order:

1. **`manage_object_template_schemas()` (~line 2889)** — for every `NodeSchema` that sets `generate_template: true`, call `generate_object_template_from_node()` to construct a `TemplateSchema` (or a generic template for shared abstractions) and register it under the `Template{kind}` name. Identifies dependent component peers via `identify_required_object_templates()` so they get subtemplates too.

2. **`generate_object_template_from_node()` (~line 2759)** — builds the bare `TemplateSchema`: copies attributes that have `support_templates`, sets the `template_name__value` HFID, wires `inherit_from` to `CoreObjectTemplate` (or the auto-generated parent template if the source node inherits from one).

3. **`add_relationships_to_template()` (~line 2669)** — walks the source node's relationships and copies the propagatable ones onto the template, with adjustments:
   - Filters out `GENERICGROUP` and `PROFILE` peers, and any kind not in `[COMPONENT, PARENT, ATTRIBUTE, GENERIC]`.
   - For `COMPONENT` and `PARENT` peers, retargets the peer to the corresponding `Template*` kind so the template can hold a reference to a *subtemplate* instead of a real object.
   - Calls `_create_resource_pool_relationship()` for IP-typed peers and `_create_attribute_resource_pool_relationship()` for `Number` attributes — see [Resource Pool Integration](#resource-pool-integration).

4. **`manage_object_template_relationships()` (~line 2535)** — adds an `object_template` relationship (kind `TEMPLATE`, identifier `node__objecttemplate`) on every template-eligible node so an instance can record which template it was created from.

These methods run before `process_post_validation`, which is also when `add_groups()` adds `member_of_groups` / `subscriber_of_groups` to *all* schemas (templates included — peers there make the template node itself a group member). On templates, `add_groups()` additionally emits `member_of_groups_for_instances` and `subscriber_of_groups_for_instances` (kind `GENERIC`, distinct identifiers `template_group_member_for_instances` and `template_group_subscriber_for_instances`). Peers on those fields drive per-instance group membership at template application time without affecting the template itself — see [Group Propagation](#group-propagation).

## Subtemplates

When a node has a `COMPONENT`-kind relationship (e.g., `InfraDevice` has components `InfraInterface`), the template generator creates a corresponding subtemplate kind (`TemplateInfraInterface`). This is driven by `identify_required_object_templates()` walking component edges transitively.

Subtemplates inherit from `CoreObjectComponentTemplate` rather than `CoreObjectTemplate`, and are not directly user-creatable — they exist as children of a parent template. `SUBTEMPLATE_EXCLUDED_KINDS` (in `core/constants/__init__.py`) lists kinds that must never be re-pointed to a `Template*` peer (the resource pool kinds). For those, the original peer is preserved as-is.

## Application Flow

When a user creates an object with `object_template={id: ...}`, `Node._apply_template()` is invoked from `Node.new()` (`core/node/__init__.py:480`). It:

1. Loads the referenced `CoreObjectTemplate` instance (via the GraphQL `object_template` input).
2. Constructs a `NodeTemplateApplier` with a `DefaultPoolAllocator` (or `NoOpPoolAllocator` if pool processing is suppressed).
3. Calls `applier.apply(template, target_schema, target_id, user_fields)` which returns a merged field dict where:
   - Template attribute values are written for any attribute the user did not supply, with `source` set to the template's id.
   - Template relationship peers are copied for relationships whose kind is `ATTRIBUTE`, `GENERIC`, or `PROFILE` — user-supplied values always take precedence. `GROUP`-kind rels (`member_of_groups`, `subscriber_of_groups`) are intentionally **not** propagated; they describe the template's own group membership.
   - For each `*_from_resource_pool` relationship on the template, an allocation is requested from the pool and written under the original (non-suffixed) name.
   - For each entry in `TEMPLATE_GROUP_FOR_INSTANCES_REL_MAP`, the peers on the template's `_for_instances` field are written under the corresponding real group-membership name on the instance — see [Group Propagation](#group-propagation).
4. Merges only previously-absent keys back into `fields`, preserving user input.
5. Returns the set of `pool_pending_fields` — fields whose pool allocation was deferred (e.g., because the chosen allocator is the no-op variant).

After save, `handle_template_relationships()` (`core/node/create.py:175`) walks the new node's `COMPONENT` relationships and recursively materializes any subtemplate peers as their own real objects, recursing into their components.

### Group Propagation

`TEMPLATE_GROUP_FOR_INSTANCES_REL_MAP` (defined in `infrahub/templates/node_applier.py`) maps the template-only field names to the real group-membership relationship names:

```python
TEMPLATE_GROUP_FOR_INSTANCES_REL_MAP = {
    "member_of_groups_for_instances": "member_of_groups",
    "subscriber_of_groups_for_instances": "subscriber_of_groups",
}
```

When `_apply_relationships` encounters a key from this map, it routes through `_handle_group_for_instances_relationship`, which reads the peers and writes them under the corresponding real name on the instance. The template's own `member_of_groups` / `subscriber_of_groups` are independent — they describe the template node's membership and are not copied. This mirrors the resource-pool sister-field pattern (`_from_resource_pool` → original field) but for groups.

## Resource Pool Integration

Templates can reference resource pools instead of fixed values. The integration is built around the `_from_resource_pool` suffix (`backend/infrahub/core/constants/schema.py:RESOURCE_POOL_REL_SUFFIX`).

**Schema time** (`add_relationships_to_template`):

- For a node relationship whose peer is `IPADDRESSPOOL` / `IPPREFIXPOOL`-eligible (`_create_resource_pool_relationship`), a `<rel_name>_from_resource_pool` relationship of kind `GENERIC` and peer `CoreIPAddressPool` / `CoreIPPrefixPool` is added to the template alongside the original relationship.
- For a `Number` attribute that supports templates (`_create_attribute_resource_pool_relationship`), an `<attr_name>_from_resource_pool` relationship to `CoreNumberPool` is added.

**Application time** (`NodeTemplateApplier._handle_pool_relationship`):

- When iterating template relationships, names ending in `RESOURCE_POOL_REL_SUFFIX` are routed to `_handle_pool_relationship`.
- The applier asks the `PoolAllocator` to allocate either an attribute value (number) or a relationship peer (IP), then writes the result under the original (non-suffixed) name with `source` set to the pool's id so allocation is attributable.
- If allocation cannot proceed (e.g., `NoOpPoolAllocator` is in use), the field is added to `pool_pending_fields` so the caller can decide.

**Constraint** (`TemplateResourcePoolExclusiveConstraint`):

- On any save of a template instance, the constraint refuses simultaneous values for `<name>` and `<name>_from_resource_pool`. A user must pick exactly one source per field.
- Wired in via `dependencies/builder/constraint/relationship_manager/template_resource_pool_exclusive.py`.

## Related Migrations

| Migration | Purpose |
|-----------|---------|
| `m022_add_generate_template_attr.py` | Introduced `generate_template` on the schema |
| `m045_backfill_hfid_display_label_in_db_profile_template.py` | Backfilled HFID/display labels on Profile and Template nodes |
| `m063_template_number_pool_cleanup.py` | Nullified `Number` attribute values on templates that came from a `CoreNumberPool` |
| `m064_template_ip_pool_relationship_cleanup.py` | Migrated pool-sourced IP rels and Number attrs into the new `_from_resource_pool` shape |
| `m065_remove_generic_generate_template.py` | Removed the now-unsupported `generate_template` on generics |

## Tests

| Path | Coverage |
|------|----------|
| `backend/tests/component/templates/test_template_applier.py` | End-to-end behaviour of `NodeTemplateApplier` (attributes, relationships, resource pools, `*_for_instances` group propagation). |
| `backend/tests/component/core/schema_manager/test_template_resource_pool_relationships.py` | Schema-level emission of `_from_resource_pool` rels for IP and Number cases. |
| `backend/tests/component/core/schema_manager/test_template_group_relationships.py` | Schema-level emission of `member_of_groups_for_instances` / `subscriber_of_groups_for_instances` on templates. |
| `backend/tests/integration/templates/` | Lifecycle tests (template attribute updates, resource pool wiring). |
| `backend/tests/integration/schema_lifecycle/test_migration_attr_remove_pool_rel.py` | End-to-end migration of pool-related schema changes on templates. |

## Limitations

- Templates only auto-generate for COMPONENT relationships; non-component peers stay pointed at real nodes.
- Edits to a template do not retro-update objects previously created from it.
- `RelationshipKind.PARENT` is propagated to instances only when explicitly modeled; templates carry parents via subtemplate retargeting, not by writing the parent into the field dict.
