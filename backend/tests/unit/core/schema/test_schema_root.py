import pytest

from infrahub.core.schema import NodeExtensionSchema, SchemaExtension, SchemaRoot


@pytest.mark.parametrize(
    ("kind", "namespace"),
    [
        ("CoreAccount", "Core"),
        ("CoreNumberPool", "Core"),
        ("BuiltinTag", "Builtin"),
        ("ProfileTestTestNode", "Profile"),
        ("TemplateTestTestNode", "Template"),
    ],
)
def test_validate_reserved_names_extension_in_restricted_namespace(kind: str, namespace: str) -> None:
    schema_root = SchemaRoot(
        extensions=SchemaExtension(
            nodes=[
                NodeExtensionSchema(
                    kind=kind, attributes=[{"name": "password", "kind": "HashedPassword", "state": "absent"}]
                )
            ]
        )
    )
    errors = schema_root.validate_reserved_names()
    assert errors == [f"Restricted namespace '{namespace}' used on extension of '{kind}'"]


@pytest.mark.parametrize("kind", ["TestTestNode", "CoreinfraDevice", "Builtin2Tag", "coreAccount"])
def test_validate_reserved_names_extension_in_allowed_namespace(kind: str) -> None:
    schema_root = SchemaRoot(
        extensions=SchemaExtension(
            nodes=[NodeExtensionSchema(kind=kind, attributes=[{"name": "description", "kind": "Text"}])]
        )
    )
    errors = schema_root.validate_reserved_names()
    assert errors == []
