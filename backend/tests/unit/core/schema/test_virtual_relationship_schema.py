from __future__ import annotations

import pytest

from infrahub.core.schema import NodeSchema, SchemaRoot, VirtualRelationshipSchema
from infrahub.core.schema.schema_branch import SchemaBranch


class TestVirtualRelationshipSchema:
    def test_instantiate_basic(self) -> None:
        vr = VirtualRelationshipSchema(name="all_interfaces", path="bays__line_cards__modules__interfaces")
        assert vr.name == "all_interfaces"
        assert vr.path == "bays__line_cards__modules__interfaces"
        assert vr.peer is None

    def test_get_path_segments(self) -> None:
        vr = VirtualRelationshipSchema(name="all_interfaces", path="bays__line_cards__modules__interfaces")
        assert vr.get_path_segments() == ["bays", "line_cards", "modules", "interfaces"]

    def test_get_path_segments_two_hops(self) -> None:
        vr = VirtualRelationshipSchema(name="remote_device", path="cable__device")
        assert vr.get_path_segments() == ["cable", "device"]

    def test_to_dict(self) -> None:
        vr = VirtualRelationshipSchema(name="all_interfaces", path="bays__modules", label="All Interfaces")
        data = vr.to_dict()
        assert data["name"] == "all_interfaces"
        assert data["path"] == "bays__modules"
        assert data["label"] == "All Interfaces"
        assert "peer" not in data  # None values excluded

    def test_is_virtual_relationship(self) -> None:
        vr = VirtualRelationshipSchema(name="test_vr", path="rel1__rel2")
        assert vr.is_virtual_relationship is True
        assert vr.is_attribute is False
        assert vr.is_relationship is False

    def test_schema_root_parses_virtual_relationships(self) -> None:
        schema = SchemaRoot.model_validate(
            {
                "nodes": [
                    {
                        "name": "Device",
                        "namespace": "Test",
                        "virtual_relationships": [
                            {
                                "name": "all_interfaces",
                                "path": "bays__modules__interfaces",
                            }
                        ],
                    }
                ],
            }
        )
        node = schema.nodes[0]
        assert len(node.virtual_relationships) == 1
        assert node.virtual_relationships[0].name == "all_interfaces"

    def test_schema_root_extension_virtual_relationships(self) -> None:
        schema = SchemaRoot.model_validate(
            {
                "extensions": {
                    "nodes": [
                        {
                            "kind": "TestDevice",
                            "virtual_relationships": [
                                {
                                    "name": "affected_services",
                                    "path": "interfaces__circuits__services",
                                }
                            ],
                        }
                    ],
                },
            }
        )
        ext = schema.extensions.nodes[0]
        assert len(ext.virtual_relationships) == 1
        assert ext.virtual_relationships[0].name == "affected_services"

    def test_node_schema_accessor_methods(self) -> None:
        node = NodeSchema(
            name="Device",
            namespace="Test",
            virtual_relationships=[
                VirtualRelationshipSchema(name="vr_one", path="rel_a__rel_b"),
                VirtualRelationshipSchema(name="vr_two", path="rel_c__rel_d"),
            ],
        )
        assert node.virtual_relationship_names == ["vr_one", "vr_two"]
        assert node.get_virtual_relationship("vr_one").path == "rel_a__rel_b"
        assert node.get_virtual_relationship_or_none("nonexistent") is None

        with pytest.raises(ValueError, match="Unable to find the virtual relationship"):
            node.get_virtual_relationship("nonexistent")


class TestVirtualRelationshipValidation:
    """Tests for SchemaBranch validation of virtual relationships."""

    @staticmethod
    def _build_schema_branch(nodes: list[dict]) -> SchemaBranch:
        """Build a SchemaBranch from a list of node dicts for testing."""
        schema_root = SchemaRoot.model_validate({"nodes": nodes})
        schema_root.generate_uuid()
        sb = SchemaBranch(cache={}, name="test")
        sb.load_schema(schema=schema_root)
        return sb

    def test_valid_path_resolves_peer(self) -> None:
        sb = self._build_schema_branch(
            [
                {
                    "name": "Device",
                    "namespace": "Test",
                    "relationships": [{"name": "bays", "peer": "TestBay", "cardinality": "many"}],
                    "virtual_relationships": [{"name": "all_bays", "path": "bays__modules"}],
                },
                {
                    "name": "Bay",
                    "namespace": "Test",
                    "relationships": [{"name": "modules", "peer": "TestModule", "cardinality": "many"}],
                },
                {
                    "name": "Module",
                    "namespace": "Test",
                },
            ]
        )
        sb.process()
        device = sb.get(name="TestDevice")
        vr = device.get_virtual_relationship("all_bays")
        assert vr.peer == "TestModule"

    def test_invalid_path_segment_rejected(self) -> None:
        sb = self._build_schema_branch(
            [
                {
                    "name": "Device",
                    "namespace": "Test",
                    "relationships": [{"name": "bays", "peer": "TestBay", "cardinality": "many"}],
                    "virtual_relationships": [{"name": "bad_vr", "path": "bays__nonexistent"}],
                },
                {
                    "name": "Bay",
                    "namespace": "Test",
                },
            ]
        )
        with pytest.raises(ValueError, match="is not a valid relationship"):
            sb.process()

    def test_path_too_short_rejected(self) -> None:
        sb = self._build_schema_branch(
            [
                {
                    "name": "Device",
                    "namespace": "Test",
                    "relationships": [{"name": "bays", "peer": "TestBay", "cardinality": "many"}],
                    "virtual_relationships": [{"name": "short_vr", "path": "bays"}],
                },
                {
                    "name": "Bay",
                    "namespace": "Test",
                },
            ]
        )
        with pytest.raises(ValueError, match="at least 2 segments"):
            sb.process()

    def test_name_conflict_with_attribute(self) -> None:
        sb = self._build_schema_branch(
            [
                {
                    "name": "Device",
                    "namespace": "Test",
                    "attributes": [{"name": "hostname", "kind": "Text"}],
                    "relationships": [{"name": "bays", "peer": "TestBay", "cardinality": "many"}],
                    "virtual_relationships": [{"name": "hostname", "path": "bays__modules"}],
                },
                {
                    "name": "Bay",
                    "namespace": "Test",
                    "relationships": [{"name": "modules", "peer": "TestModule", "cardinality": "many"}],
                },
                {
                    "name": "Module",
                    "namespace": "Test",
                },
            ]
        )
        with pytest.raises(ValueError, match="must be unique"):
            sb.process()

    def test_name_conflict_with_relationship(self) -> None:
        sb = self._build_schema_branch(
            [
                {
                    "name": "Device",
                    "namespace": "Test",
                    "relationships": [{"name": "bays", "peer": "TestBay", "cardinality": "many"}],
                    "virtual_relationships": [{"name": "bays", "path": "bays__modules"}],
                },
                {
                    "name": "Bay",
                    "namespace": "Test",
                    "relationships": [{"name": "modules", "peer": "TestModule", "cardinality": "many"}],
                },
                {
                    "name": "Module",
                    "namespace": "Test",
                },
            ]
        )
        with pytest.raises(ValueError, match="must be unique"):
            sb.process()

    def test_peer_mismatch_rejected(self) -> None:
        sb = self._build_schema_branch(
            [
                {
                    "name": "Device",
                    "namespace": "Test",
                    "relationships": [{"name": "bays", "peer": "TestBay", "cardinality": "many"}],
                    "virtual_relationships": [
                        {
                            "name": "wrong_peer",
                            "path": "bays__modules",
                            "peer": "TestDevice",  # Wrong! Path resolves to TestModule
                        }
                    ],
                },
                {
                    "name": "Bay",
                    "namespace": "Test",
                    "relationships": [{"name": "modules", "peer": "TestModule", "cardinality": "many"}],
                },
                {
                    "name": "Module",
                    "namespace": "Test",
                },
            ]
        )
        with pytest.raises(ValueError, match="specifies peer"):
            sb.process()

    def test_label_auto_generated(self) -> None:
        sb = self._build_schema_branch(
            [
                {
                    "name": "Device",
                    "namespace": "Test",
                    "relationships": [{"name": "bays", "peer": "TestBay", "cardinality": "many"}],
                    "virtual_relationships": [{"name": "all_bays", "path": "bays__modules"}],
                },
                {
                    "name": "Bay",
                    "namespace": "Test",
                    "relationships": [{"name": "modules", "peer": "TestModule", "cardinality": "many"}],
                },
                {
                    "name": "Module",
                    "namespace": "Test",
                },
            ]
        )
        sb.process()
        device = sb.get(name="TestDevice")
        vr = device.get_virtual_relationship("all_bays")
        assert vr.label is not None
        assert vr.label == "All Bays"
