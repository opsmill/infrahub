from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.schema import SchemaRoot

if TYPE_CHECKING:
    from infrahub.core.schema.schema_branch import SchemaBranch


# FirewallGenericDevice.name is implicitly unique because it is in the only item in the HFID
# before fix, this took multiple runs through SchemaBranch.process() to filter through and set
# inheriting schema DcimFirewall.name to unique, which eventually removes the attribute
# from the generated TemplateSchema
SCHEMA_PAYLOAD: dict[str, Any] = {
    "version": "1.0",
    "generics": [
        {
            "name": "GenericDevice",
            "namespace": "Firewall",
            "description": "Generic Firewall object.",
            "include_in_menu": False,
            "order_by": ["name__value"],
            "display_label": "{{ name__value }}",
            "human_friendly_id": ["name__value"],
            "attributes": [
                {"name": "name", "kind": "Text"},
            ],
            "relationships": [],
        },
        {
            "name": "GenericRules",
            "namespace": "Firewall",
            "description": "Generic Generic Rules object.",
            "human_friendly_id": ["rule_id__value"],
            "display_label": "{{ rule_id__value }}",
            "include_in_menu": False,
            "order_by": ["rule_id__value"],
            "attributes": [
                {
                    "name": "rule_id",
                    "kind": "NumberPool",  # trigger #1
                    "read_only": True,
                    "branch": "agnostic",
                },
            ],
            "relationships": [],
        },
    ],
    "nodes": [
        {
            "name": "Firewall",
            "namespace": "Dcim",
            "label": "Firewall",
            "include_in_menu": False,
            "generate_template": True,  # trigger #2
            "inherit_from": ["FirewallGenericDevice"],
            "attributes": [
                {
                    "name": "status",
                    "kind": "Dropdown",
                    "optional": True,
                    "order_weight": 1100,
                    "choices": [
                        {"name": "active", "label": "Active", "color": "#7fbf7f"},
                        {"name": "provisioning", "label": "Provisioning", "color": "#ffff7f"},
                        {"name": "maintenance", "label": "Maintenance", "color": "#ffd27f"},
                        {"name": "drained", "label": "Drained", "color": "#bfbfbf"},
                    ],
                },
            ],
        },
    ],
}


def _describe_hash_diff(before: SchemaBranch, after: SchemaBranch) -> str:
    """Render a per-schema diff report when hashes disagree.

    Covers nodes, generics, profiles, and templates, since SchemaBranch.get_hash()
    only covers nodes + generics.
    """
    lines: list[str] = []
    all_names = sorted(
        set(
            before.node_names
            + before.generic_names
            + before.profile_names
            + before.template_names
            + after.node_names
            + after.generic_names
            + after.profile_names
            + after.template_names
        )
    )
    for name in all_names:  # noqa: PLR1702
        try:
            obj_before = before.get(name=name, duplicate=False)
            dump_before = obj_before.model_dump()
        except Exception:
            lines.append(f"{name}: only in 'after'")
            continue
        try:
            obj_after = after.get(name=name, duplicate=False)
            dump_after = obj_after.model_dump()
        except Exception:
            lines.append(f"{name}: only in 'before'")
            continue
        if obj_before.get_hash() == obj_after.get_hash():
            continue
        lines.append(f"{name}:")
        for key in sorted(set(dump_before.keys()) | set(dump_after.keys())):
            v1, v2 = dump_before.get(key), dump_after.get(key)
            if v1 == v2:
                continue
            if key not in ("attributes", "relationships"):
                lines.append(f"  {key}: {v1!r} -> {v2!r}")
                continue
            items1 = {i["name"]: i for i in v1} if v1 else {}
            items2 = {i["name"]: i for i in v2} if v2 else {}
            for iname in sorted(set(items1.keys()) | set(items2.keys())):
                i1, i2 = items1.get(iname), items2.get(iname)
                if i1 == i2:
                    continue
                if i1 is None:
                    lines.append(f"  {key}.{iname}: ADDED")
                elif i2 is None:
                    lines.append(f"  {key}.{iname}: REMOVED")
                else:
                    for fk in sorted(set(i1.keys()) | set(i2.keys())):
                        if i1.get(fk) != i2.get(fk):
                            lines.append(f"  {key}.{iname}.{fk}: {i1.get(fk)!r} -> {i2.get(fk)!r}")
    return "\n".join(lines) if lines else "(no per-schema diffs found)"


class TestSchemaProcessUniquenessIdempotent:
    """Loading the same schema payload twice must leave the persisted schema unchanged."""

    async def test_process_is_idempotent(
        self,
        register_core_models_schema: SchemaBranch,
    ) -> None:
        """Calling SchemaBranch.process() repeatedly must not mutate the schema.

        SchemaBranch.process() can be called multiple times during a schema load, which will lead
        to unexpected schema drift if changes are made to the schema when calling process() on the
        same data multuple times
        """
        # Kinds whose HFID references name__value. FirewallGenericDevice owns
        # the `name` attribute directly; DcimFirewall only has it after inheritance
        # processing (which runs inside process()), so it's checked from after_first
        # onward.
        kinds_with_hfid_name = ["FirewallGenericDevice", "DcimFirewall"]

        def snapshot_unique_state(sb: SchemaBranch, kinds: list[str]) -> dict[str, dict[str, Any]]:
            """Capture name.unique and uniqueness_constraints for the given kinds."""
            result: dict[str, dict[str, Any]] = {}
            for kind in kinds:
                node = sb.get(name=kind, duplicate=False)
                name_attr = node.get_attribute(name="name")
                result[kind] = {
                    "name.unique": name_attr.unique,
                    "uniqueness_constraints": node.uniqueness_constraints,
                    "human_friendly_id": node.human_friendly_id,
                }
            return result

        schema_branch = register_core_models_schema.duplicate()
        schema_branch.load_schema(schema=SchemaRoot(**SCHEMA_PAYLOAD))

        # --- First process() call ---
        schema_branch.process()
        after_first = snapshot_unique_state(schema_branch, kinds_with_hfid_name)

        # Capture full state after the first process() call.
        hash_initial = schema_branch.get_hash()
        node_names_initial = set(schema_branch.node_names)
        generic_names_initial = set(schema_branch.generic_names)
        template_names_initial = set(schema_branch.template_names)
        profile_names_initial = set(schema_branch.profile_names)

        template_hashes_initial = {
            name: schema_branch.get(name=name, duplicate=False).get_hash() for name in template_names_initial
        }
        profile_hashes_initial = {
            name: schema_branch.get(name=name, duplicate=False).get_hash() for name in profile_names_initial
        }

        # Sanity-check: the triggers actually produced the expected schemas.
        assert "FirewallGenericDevice" in schema_branch.generic_names
        assert "FirewallGenericRules" in schema_branch.generic_names
        assert "DcimFirewall" in schema_branch.node_names
        assert "TemplateDcimFirewall" in schema_branch.template_names

        snapshot = schema_branch.duplicate()

        # Call process() several more times; state must not drift.
        for iteration in range(2, 6):
            schema_branch.process()
            after_iter = snapshot_unique_state(schema_branch, kinds_with_hfid_name)

            # The uniqueness state must not drift between process() calls.
            for kind in kinds_with_hfid_name:
                assert after_iter[kind] == after_first[kind], (
                    f"{kind}: unique / uniqueness_constraints drifted between "
                    f"process() #1 and process() #{iteration}.\n"
                    f"  after #1:            {after_first[kind]}\n"
                    f"  after #{iteration}:            {after_iter[kind]}\n"
                )

            assert schema_branch.get_hash() == hash_initial, (
                f"SchemaBranch hash (nodes + generics) changed at process() call #{iteration}.\n"
                f"{_describe_hash_diff(snapshot, schema_branch)}"
            )
            assert set(schema_branch.node_names) == node_names_initial, (
                f"node_names changed at process() call #{iteration}"
            )
            assert set(schema_branch.generic_names) == generic_names_initial, (
                f"generic_names changed at process() call #{iteration}"
            )
            assert set(schema_branch.template_names) == template_names_initial, (
                f"template_names changed at process() call #{iteration}"
            )
            assert set(schema_branch.profile_names) == profile_names_initial, (
                f"profile_names changed at process() call #{iteration}"
            )

            for name in template_names_initial:
                current = schema_branch.get(name=name, duplicate=False).get_hash()
                assert current == template_hashes_initial[name], (
                    f"Template {name} hash changed at process() call #{iteration}.\n"
                    f"{_describe_hash_diff(snapshot, schema_branch)}"
                )
            for name in profile_names_initial:
                current = schema_branch.get(name=name, duplicate=False).get_hash()
                assert current == profile_hashes_initial[name], (
                    f"Profile {name} hash changed at process() call #{iteration}.\n"
                    f"{_describe_hash_diff(snapshot, schema_branch)}"
                )
