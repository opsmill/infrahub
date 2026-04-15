from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core.constants import BranchSupportType
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.attribute_schema import AttributeSchema
from infrahub.core.schema.dropdown import DropdownChoice
from infrahub.core.schema.generic_schema import GenericSchema
from infrahub.core.schema.node_schema import NodeSchema

if TYPE_CHECKING:
    from infrahub.core.schema.schema_branch import SchemaBranch


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


def _validate_process_idempotent(schema_branch: SchemaBranch, iterations: int = 4) -> None:
    """Call process() once to establish baseline, then `iterations` more times
    asserting the full schema state is unchanged across calls.

    Checks the schema hash (nodes + generics), node/generic/template/profile
    name sets, and each template and profile hash individually — since
    SchemaBranch.get_hash() only covers nodes and generics.
    """
    schema_branch.process()

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

    snapshot = schema_branch.duplicate()

    for iteration in range(2, 2 + iterations):
        schema_branch.process()

        assert schema_branch.get_hash() == hash_initial, (
            f"SchemaBranch hash (nodes + generics) changed at process() call #{iteration}.\n"
            f"{_describe_hash_diff(snapshot, schema_branch)}"
        )
        assert set(schema_branch.node_names) == node_names_initial, f"node_names changed at process() call #{iteration}"
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


@pytest.fixture
def firewall_hfid_schema() -> SchemaRoot:
    """FirewallGenericDevice.name is implicitly unique because it is the only item in the HFID.

    Before fix, this took multiple runs through SchemaBranch.process() to filter through and set
    inheriting schema DcimFirewall.name to unique, which eventually removes the attribute
    from the generated TemplateSchema.
    """
    return SchemaRoot(
        version="1.0",
        generics=[
            GenericSchema(
                name="GenericDevice",
                namespace="Firewall",
                description="Generic Firewall object.",
                include_in_menu=False,
                order_by=["name__value"],
                display_label="{{ name__value }}",
                human_friendly_id=["name__value"],
                attributes=[AttributeSchema(name="name", kind="Text")],
            ),
            GenericSchema(
                name="GenericRules",
                namespace="Firewall",
                description="Generic Generic Rules object.",
                human_friendly_id=["rule_id__value"],
                display_label="{{ rule_id__value }}",
                include_in_menu=False,
                order_by=["rule_id__value"],
                attributes=[
                    AttributeSchema(
                        name="rule_id",
                        kind="NumberPool",  # trigger #1
                        read_only=True,
                        branch=BranchSupportType.AGNOSTIC,
                    ),
                ],
            ),
        ],
        nodes=[
            NodeSchema(
                name="Firewall",
                namespace="Dcim",
                label="Firewall",
                include_in_menu=False,
                generate_template=True,  # trigger #2
                inherit_from=["FirewallGenericDevice"],
                attributes=[
                    AttributeSchema(
                        name="status",
                        kind="Dropdown",
                        optional=True,
                        order_weight=1100,
                        choices=[
                            DropdownChoice(name="active", label="Active", color="#7fbf7f"),
                            DropdownChoice(name="provisioning", label="Provisioning", color="#ffff7f"),
                            DropdownChoice(name="maintenance", label="Maintenance", color="#ffd27f"),
                            DropdownChoice(name="drained", label="Drained", color="#bfbfbf"),
                        ],
                    ),
                ],
            ),
        ],
    )


@pytest.fixture
def conflicting_inherit_schema() -> SchemaRoot:
    """A node inheriting the same attribute from two generics with conflicting `unique` settings.

    NodeInheritanceHandler iterates `inherit_from` in order. For the first generic, the attribute
    is added fresh; for each subsequent generic, `update_from_generic` overwrites every
    non-excluded field on the existing inherited attribute. With
    inherit_from=[TestGenericSpecific, TestGenericBase]: TestGenericSpecific adds `name` with
    unique=False, then TestGenericBase's update_from_generic flips it to unique=True.
    """
    return SchemaRoot(
        generics=[
            GenericSchema(
                name="GenericBase",
                namespace="Test",
                description="Base generic with a unique name attribute.",
                include_in_menu=False,
                attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
            ),
            GenericSchema(
                name="GenericSpecific",
                namespace="Test",
                description="Specific generic with a non-unique name attribute.",
                include_in_menu=False,
                attributes=[AttributeSchema(name="name", kind="Text")],
            ),
        ],
        nodes=[
            NodeSchema(
                name="ConcreteDevice",
                namespace="Test",
                description="Node inheriting name from two generics with conflicting unique settings.",
                include_in_menu=False,
                generate_template=True,
                # TestGenericSpecific processed first (name.unique=False),
                # then update_from_generic overwrites to unique=True from TestGenericBase.
                inherit_from=["TestGenericSpecific", "TestGenericBase"],
            ),
        ],
    )


class TestSchemaProcessUniquenessIdempotent:
    """Loading the same schema payload twice must leave the persisted schema unchanged."""

    async def test_hfid_to_node_attr_to_template_propagation(
        self,
        register_core_models_schema: SchemaBranch,
        firewall_hfid_schema: SchemaRoot,
    ) -> None:
        """Calling SchemaBranch.process() repeatedly must not mutate the schema.

        SchemaBranch.process() can be called multiple times during a schema load, which will lead
        to unexpected schema drift if changes are made to the schema when calling process() on the
        same data multiple times.

        FirewallGenericDevice.name is implicitly unique because it is the only entry in the HFID;
        before the process_post_validation fix, the HFID-derived `unique` flag propagated to
        DcimFirewall.name one pass late, which eventually removed the attribute from the generated
        templates and profiles.
        """
        schema_branch = register_core_models_schema.duplicate()
        schema_branch.load_schema(schema=firewall_hfid_schema)

        _validate_process_idempotent(schema_branch)

    async def test_conflicting_inherit_unique_propagation(
        self,
        register_core_models_schema: SchemaBranch,
        conflicting_inherit_schema: SchemaRoot,
    ) -> None:
        """A node inheriting the same attribute from two generics with
        conflicting `unique` settings must still process idempotently.
        """
        schema_branch = register_core_models_schema.duplicate()
        schema_branch.load_schema(schema=conflicting_inherit_schema)

        _validate_process_idempotent(schema_branch)
