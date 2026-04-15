"""Tests for the template name attribute inconsistency.

Two independent bugs that both result in 'name' being dropped from generated templates:

Bug 1 — multi-generic inheritance conflict:
  When a node inherits from two generics with conflicting name.unique settings,
  update_from_generic() silently overwrites name.unique=False (from the first generic)
  with name.unique=True (from the second generic). Because support_templates = (read_only
  is False and unique is False), the node ends up with name excluded from its template,
  while the first generic's template still includes it.

Bug 2 — human_friendly_id progressive degradation:
  When a generic has human_friendly_id: [name__value] but name without unique: true,
  the full process() pipeline degrades across reload cycles:
    Cycle 1: template OK; process_human_friendly_id() writes ["name__value"] into
             uniqueness_constraints and that state is persisted.
    Cycle 2: template OK (name.unique=False at generation time); then
             sync_uniqueness_constraints_and_unique_attributes() sees the persisted
             constraint and sets name.unique=True — persisted.
    Cycle 3: template BROKEN — name.unique=True is already in the DB when templates
             are generated, so name is silently excluded.

See dev/specs/template-name-attribute-inconsistency.md for the full analysis.
"""

from infrahub.core.schema import (
    AttributeSchema,
    GenericSchema,
    NodeSchema,
    SchemaRoot,
    core_models,
)
from infrahub.core.schema.schema_branch import SchemaBranch


async def test_template_name_attribute_inconsistency() -> None:
    """Template name attribute asymmetry between generic template and node template.

    Schema setup mirrors dev/specs/template-name-repro.yml:
      - TestGenericBase:     name (unique=True)
      - TestGenericSpecific: name (no unique -> unique=False, support_templates=True)
      - TestConcreteDevice:  inherit_from=[TestGenericSpecific, TestGenericBase]
                             generate_template=True

    Expected (desired) behaviour:
      TemplateTestGenericSpecific.attributes includes 'name'  (GenericSpecific.name.unique=False)
      TemplateTestConcreteDevice.attributes  includes 'name'  (inherited from GenericSpecific)

    Current (buggy) behaviour:
      TemplateTestGenericSpecific includes 'name'        (PASS - generic read directly)
      TemplateTestConcreteDevice  does NOT include 'name' (FAIL - update_from_generic copies
                                                            unique=True from TestGenericBase,
                                                            making support_templates=False)
    """
    schema_branch = SchemaBranch(cache={}, name="test")

    test_schema = SchemaRoot(
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

    schema_branch.load_schema(schema=SchemaRoot(**core_models).merge(schema=test_schema))
    schema_branch.generate_identifiers()
    schema_branch.process_inheritance()
    schema_branch.manage_object_template_schemas()

    # 1. Generic template includes name (TestGenericSpecific.name.unique=False → support_templates=True).
    #    This currently passes.
    generic_template = schema_branch.get_generic("TemplateTestGenericSpecific", duplicate=False)
    assert "name" in generic_template.attribute_names, (
        "TemplateTestGenericSpecific must include 'name' "
        "(TestGenericSpecific.name.unique=False → support_templates=True)"
    )

    # 2. Node template should also include name because TestConcreteDevice inherits
    #    from TestGenericSpecific which marks name as templatable.
    #    BUG: currently fails because process_inheritance() calls update_from_generic()
    #    with TestGenericBase.name (unique=True), overwriting the node's name.unique to True,
    #    so support_templates becomes False and name is excluded from the node template.
    node_template = schema_branch.get_template("TemplateTestConcreteDevice", duplicate=False)
    assert "name" in node_template.attribute_names, (
        "TemplateTestConcreteDevice must include 'name' "
        "(inherited from TestGenericSpecific which has name.unique=False), "
        "but update_from_generic from TestGenericBase sets name.unique=True, "
        "causing support_templates=False and silently dropping name from the template"
    )


async def test_shared_cache_does_not_corrupt_generic_template() -> None:
    """Two SchemaBranch instances sharing the same cache must each produce correct templates.

    Branch A: TestGenericSpecific (name.unique=False) + no inheritance conflict
              → TemplateTestGenericSpecific should include name

    Branch B: same schema PLUS TestConcreteDevice inheriting from both
              TestGenericSpecific and TestGenericBase (name.unique=True)
              → TemplateTestGenericSpecific should still include name (generic is unchanged)
              → TemplateTestConcreteDevice should include name (desired, currently fails per
                the primary test above)

    The shared cache means both branches reference the same cached schema objects for
    schemas that produce an identical hash. If the generic's cached attributes are mutated
    (e.g., name.unique silently flipped to True), the first branch's template would also
    be affected. This test verifies the cache does not cause such cross-branch corruption.
    """
    shared_cache: dict = {}

    # Branch A: only the specific generic and a simple node — no conflicting unique.
    branch_a = SchemaBranch(cache=shared_cache, name="branch_a")
    schema_a = SchemaRoot(
        generics=[
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
                name="SimpleDevice",
                namespace="Test",
                include_in_menu=False,
                generate_template=True,
                inherit_from=["TestGenericSpecific"],
            ),
        ],
    )
    branch_a.load_schema(schema=SchemaRoot(**core_models).merge(schema=schema_a))
    branch_a.generate_identifiers()
    branch_a.process_inheritance()
    branch_a.manage_object_template_schemas()

    generic_template_a = branch_a.get_generic("TemplateTestGenericSpecific", duplicate=False)
    assert "name" in generic_template_a.attribute_names, "Branch A: TemplateTestGenericSpecific must include 'name'"

    # Branch B: adds TestGenericBase (name.unique=True) and a node with the inheritance conflict.
    # Uses the SAME shared_cache as branch_a.
    branch_b = SchemaBranch(cache=shared_cache, name="branch_b")
    schema_b = SchemaRoot(
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
                include_in_menu=False,
                generate_template=True,
                inherit_from=["TestGenericSpecific", "TestGenericBase"],
            ),
        ],
    )
    branch_b.load_schema(schema=SchemaRoot(**core_models).merge(schema=schema_b))
    branch_b.generate_identifiers()
    branch_b.process_inheritance()
    branch_b.manage_object_template_schemas()

    # Branch A's template must not be affected by Branch B's processing.
    generic_template_a_after = branch_a.get_generic("TemplateTestGenericSpecific", duplicate=False)
    assert "name" in generic_template_a_after.attribute_names, (
        "After Branch B processing, Branch A's TemplateTestGenericSpecific must still include 'name' "
        "(shared cache must not corrupt Branch A's cached generic)"
    )

    # Branch B's generic template should also include name (generic.name.unique=False).
    generic_template_b = branch_b.get_generic("TemplateTestGenericSpecific", duplicate=False)
    assert "name" in generic_template_b.attribute_names, (
        "Branch B: TemplateTestGenericSpecific must include 'name' "
        "(TestGenericSpecific.name.unique=False is unchanged by the node inheritance)"
    )


async def test_human_friendly_id_does_not_promote_unique_on_secondary_load() -> None:
    """sync_uniqueness_constraints_and_unique_attributes() must not promote name.unique=True
    when the single-attribute constraint originates from human_friendly_id.

    When a generic defines human_friendly_id: [name__value] but name without unique: true,
    the full process() pipeline runs across reload cycles:

      process_pre_validation()    → manage_object_template_schemas()               (line 641)
      process_validate()          → sync_uniqueness_constraints_and_unique_attrs()  (line 660)
      process_post_validation()   → process_human_friendly_id()                    (line 678)

    Cycle 1 (raw schema, name.unique=False, constraints=[]):
      templates generated correctly; process_human_friendly_id() writes
      constraints=[["name__value"]] → persisted.

    Without the fix, Cycle 2 (from DB: name.unique=False, constraints=[["name__value"]]):
      sync_uniqueness_constraints_and_unique_attributes() sees the single-attribute constraint
      and promotes name.unique to True → persisted. Cycle 3 templates then exclude name.

    With the fix, Cycle 2 must NOT promote name.unique because the constraint is HFID-derived:
      sync_uniqueness_constraints_and_unique_attributes() detects the constraint type is HFID
      and skips the promotion. name.unique stays False → templates continue to include name.

    This test simulates cycle 2: name.unique=False in the input, constraints=[["name__value"]]
    already written by process_human_friendly_id() from cycle 1. It asserts that after
    sync_uniqueness_constraints_and_unique_attributes() the generic's name.unique is still False
    and the generated template still includes name.
    """
    # State as loaded from DB after cycle 1:
    # process_human_friendly_id() wrote constraints=[["name__value"]], but name.unique is still False.
    schema_branch = SchemaBranch(cache={}, name="test")
    test_schema = SchemaRoot(
        generics=[
            GenericSchema(
                name="GenericSpecific",
                namespace="Test",
                description="Generic with human_friendly_id referencing a non-unique attribute.",
                include_in_menu=False,
                human_friendly_id=["name__value"],
                # Cycle 1 result: process_human_friendly_id() persisted this constraint.
                # name.unique is still False — the author never set unique: true.
                uniqueness_constraints=[["name__value"]],
                attributes=[AttributeSchema(name="name", kind="Text")],
            ),
        ],
        nodes=[
            NodeSchema(
                name="ConcreteDevice",
                namespace="Test",
                include_in_menu=False,
                generate_template=True,
                inherit_from=["TestGenericSpecific"],
            ),
        ],
    )

    schema_branch.load_schema(schema=SchemaRoot(**core_models).merge(schema=test_schema))
    schema_branch.generate_identifiers()
    schema_branch.process_inheritance()

    # Simulate cycle 2's process_validate() call before templates are (re-)generated.
    # Without the fix, this promotes name.unique to True (HFID constraint treated as a
    # standard uniqueness constraint). With the fix, HFID-derived constraints are skipped.
    schema_branch.sync_uniqueness_constraints_and_unique_attributes()

    # After sync, name.unique must still be False — the HFID-derived constraint must not
    # have been used to promote it.
    generic_schema = schema_branch.get_generic("TestGenericSpecific", duplicate=False)
    name_attr = generic_schema.get_attribute("name")
    assert name_attr.unique is False, (
        "sync_uniqueness_constraints_and_unique_attributes() must not promote name.unique=True "
        "when the single-attribute constraint originates from human_friendly_id"
    )

    # Generate templates after sync and verify name is still included.
    schema_branch.manage_object_template_schemas()

    generic_template = schema_branch.get_generic("TemplateTestGenericSpecific", duplicate=False)
    assert "name" in generic_template.attribute_names, (
        "TemplateTestGenericSpecific must include 'name' — the HFID-derived constraint must not "
        "cause sync_uniqueness_constraints_and_unique_attributes() to promote name.unique=True, "
        "which would then drop name from the template on the next cycle"
    )
