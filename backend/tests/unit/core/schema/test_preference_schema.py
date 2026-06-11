import pytest

from infrahub.core.constants import (
    BranchSupportType,
    InfrahubKind,
    RelationshipCardinality,
    RelationshipDeleteBehavior,
    RelationshipKind,
)
from infrahub.core.schema import SchemaRoot, core_models
from infrahub.core.schema.definitions.core.preference import core_global_preference
from infrahub.core.schema.schema_branch import SchemaBranch


@pytest.fixture
def core_schema_branch() -> SchemaBranch:
    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(schema=SchemaRoot(**core_models))
    schema_branch.process()
    return schema_branch


def test_global_preference_schema(core_schema_branch: SchemaBranch) -> None:
    schema = core_schema_branch.get(name=InfrahubKind.GLOBALPREFERENCE, duplicate=False)

    assert schema.namespace == "Core"
    assert schema.branch == BranchSupportType.AGNOSTIC
    assert schema.include_in_menu is False
    assert schema.generate_profile is False
    assert schema.icon == "mdi:cog"

    date_format = schema.get_attribute(name="date_format")
    assert date_format.kind == "Text"
    assert date_format.optional is True
    assert date_format.order_weight == 1000

    timezone = schema.get_attribute(name="timezone")
    assert timezone.kind == "Text"
    assert timezone.optional is True
    assert timezone.order_weight == 1100

    # No user-defined relationships in V1 (processing may add group relationships)
    assert not core_global_preference.relationships


def test_user_preference_schema(core_schema_branch: SchemaBranch) -> None:
    schema = core_schema_branch.get(name=InfrahubKind.USERPREFERENCE, duplicate=False)

    assert schema.namespace == "Core"
    assert schema.branch == BranchSupportType.AGNOSTIC
    assert schema.include_in_menu is False
    assert schema.generate_profile is False
    assert schema.icon == "mdi:account-cog-outline"
    assert schema.uniqueness_constraints == [["account"]]

    date_format = schema.get_attribute(name="date_format")
    assert date_format.kind == "Text"
    assert date_format.optional is True
    assert date_format.order_weight == 1000

    timezone = schema.get_attribute(name="timezone")
    assert timezone.kind == "Text"
    assert timezone.optional is True
    assert timezone.order_weight == 1100

    account_rel = schema.get_relationship(name="account")
    assert account_rel.peer == InfrahubKind.GENERICACCOUNT
    assert account_rel.identifier == "account__preferences"
    assert account_rel.kind == RelationshipKind.PARENT
    assert account_rel.cardinality == RelationshipCardinality.ONE
    assert account_rel.optional is False
    assert account_rel.on_delete == RelationshipDeleteBehavior.CASCADE


def test_preference_kind_constants() -> None:
    assert InfrahubKind.GLOBALPREFERENCE == "CoreGlobalPreference"
    assert InfrahubKind.USERPREFERENCE == "CoreUserPreference"
