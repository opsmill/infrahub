from infrahub.core.migrations import MIGRATION_MAP
from infrahub.core.migrations.schema.phases import MigrationPhase


def test_phases_are_defined_in_run_order() -> None:
    assert list(MigrationPhase) == [
        MigrationPhase.KIND_UPDATE,
        MigrationPhase.NODE_REMOVE,
        MigrationPhase.FIELD_REMOVE,
        MigrationPhase.ATTRIBUTE_RENAME,
        MigrationPhase.ATTRIBUTE_KIND_UPDATE,
        MigrationPhase.ATTRIBUTE_ADD,
        MigrationPhase.PROPERTY_UPDATE,
    ]


def test_every_migration_name_with_a_class_has_its_phase() -> None:
    phases = {name: migration_class.phase for name, migration_class in MIGRATION_MAP.items() if migration_class}

    assert phases == {
        "node.inherit_from.update": MigrationPhase.KIND_UPDATE,
        "node.name.update": MigrationPhase.KIND_UPDATE,
        "node.namespace.update": MigrationPhase.KIND_UPDATE,
        "node.remove": MigrationPhase.NODE_REMOVE,
        "node.attribute.remove": MigrationPhase.FIELD_REMOVE,
        "node.relationship.remove": MigrationPhase.FIELD_REMOVE,
        "attribute.name.update": MigrationPhase.ATTRIBUTE_RENAME,
        "attribute.kind.update": MigrationPhase.ATTRIBUTE_KIND_UPDATE,
        "node.attribute.add": MigrationPhase.ATTRIBUTE_ADD,
        "attribute.optional.update": MigrationPhase.PROPERTY_UPDATE,
        "attribute.read_only.update": MigrationPhase.PROPERTY_UPDATE,
        "attribute.unique.update": MigrationPhase.PROPERTY_UPDATE,
        "node.uniqueness_constraints.update": MigrationPhase.PROPERTY_UPDATE,
    }
