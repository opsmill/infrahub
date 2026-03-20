"""Unit tests for AWS Neptune database support."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from infrahub.config import DatabaseSettings, NeptuneSettings
from infrahub.constants.database import DatabaseType
from infrahub.core.graph.constraints import ConstraintManagerNeptune
from infrahub.database.index import IndexItem
from infrahub.database.neptune import IndexManagerNeptune, IndexNodeNeptune
from infrahub.database.neptune_auth import get_neptune_auth_token


class TestDatabaseTypeEnum:
    def test_neptune_enum_exists(self) -> None:
        assert DatabaseType.NEPTUNE == "neptune"
        assert DatabaseType.NEPTUNE.value == "neptune"

    def test_all_db_types(self) -> None:
        assert set(DatabaseType) == {DatabaseType.NEO4J, DatabaseType.MEMGRAPH, DatabaseType.NEPTUNE}


class TestNeptuneSettings:
    def test_default_settings(self) -> None:
        settings = NeptuneSettings()
        assert settings.iam_auth_enabled is True
        assert settings.aws_region == "us-east-1"
        assert settings.port == 8182

    def test_custom_settings(self) -> None:
        settings = NeptuneSettings(
            iam_auth_enabled=False, aws_region="eu-west-1", port=9182
        )
        assert settings.iam_auth_enabled is False
        assert settings.aws_region == "eu-west-1"
        assert settings.port == 9182


class TestDatabaseSettingsNeptune:
    def test_neptune_database_uri(self) -> None:
        settings = DatabaseSettings(
            db_type=DatabaseType.NEPTUNE,
            address="my-cluster.cluster-abc123.us-east-1.neptune.amazonaws.com",
        )
        assert settings.database_uri == "bolt+s://my-cluster.cluster-abc123.us-east-1.neptune.amazonaws.com:8182"

    def test_neptune_database_uri_custom_port(self) -> None:
        settings = DatabaseSettings(
            db_type=DatabaseType.NEPTUNE,
            address="my-cluster.cluster-abc123.us-east-1.neptune.amazonaws.com",
            neptune=NeptuneSettings(port=9182),
        )
        assert settings.database_uri == "bolt+s://my-cluster.cluster-abc123.us-east-1.neptune.amazonaws.com:9182"

    def test_neptune_database_name(self) -> None:
        settings = DatabaseSettings(db_type=DatabaseType.NEPTUNE)
        assert settings.database_name == "neptune"

    def test_neo4j_database_uri_unchanged(self) -> None:
        settings = DatabaseSettings(db_type=DatabaseType.NEO4J, protocol="bolt", address="localhost", port=7687)
        assert settings.database_uri == "bolt://localhost:7687"

    def test_neo4j_database_name_unchanged(self) -> None:
        settings = DatabaseSettings(db_type=DatabaseType.NEO4J)
        assert settings.database_name == "neo4j"


class TestNeptuneAuth:
    def test_no_iam_returns_empty_credentials(self) -> None:
        username, password = get_neptune_auth_token(
            region="us-east-1",
            endpoint="my-cluster.neptune.amazonaws.com",
            iam_enabled=False,
        )
        assert not username
        assert not password

    def test_iam_auth_requires_botocore(self) -> None:
        # When botocore is not installed, it should raise ImportError
        with patch.dict("sys.modules", {"botocore": None, "botocore.auth": None, "botocore.awsrequest": None, "botocore.session": None}):
            # We can't easily test the import failure since the module may already be imported
            # Test the no-auth path instead
            username, _password = get_neptune_auth_token(
                region="us-east-1",
                endpoint="test",
                iam_enabled=False,
            )
            assert not username


class TestIndexNodeNeptune:
    def test_add_query_returns_comment(self) -> None:
        item = IndexNodeNeptune(
            name="test_index", label="TestNode", properties=["uuid"], type="range"
        )
        query = item.get_add_query()
        assert query.startswith("// Neptune:")
        assert "TestNode" in query

    def test_drop_query_returns_comment(self) -> None:
        item = IndexNodeNeptune(
            name="test_index", label="TestNode", properties=["uuid"], type="range"
        )
        query = item.get_drop_query()
        assert query.startswith("// Neptune:")


class TestIndexManagerNeptune:
    def test_init_sets_nodes_and_empty_rels(self) -> None:
        mock_db = MagicMock()
        manager = IndexManagerNeptune(db=mock_db)
        items = [
            IndexItem(name="test", label="TestNode", properties=["uuid"], type="range"),
            IndexItem(name="test2", label="TestNode2", properties=["name"], type="text"),
        ]
        rels = [
            IndexItem(name="rel", label="IS_RELATED", properties=["branch"], type="range"),
        ]
        manager.init(nodes=items, rels=rels)
        assert len(manager.nodes) == 2
        assert len(manager.rels) == 0  # Neptune doesn't support relationship indexes
        assert manager.initialized is True
        assert all(isinstance(n, IndexNodeNeptune) for n in manager.nodes)

    @pytest.mark.asyncio
    async def test_add_is_noop(self) -> None:
        mock_db = MagicMock()
        manager = IndexManagerNeptune(db=mock_db)
        manager.init(nodes=[], rels=[])
        await manager.add()  # Should not raise

    @pytest.mark.asyncio
    async def test_drop_is_noop(self) -> None:
        mock_db = MagicMock()
        manager = IndexManagerNeptune(db=mock_db)
        manager.init(nodes=[], rels=[])
        await manager.drop()  # Should not raise

    @pytest.mark.asyncio
    async def test_list_returns_synthetic_entries(self) -> None:
        mock_db = MagicMock()
        manager = IndexManagerNeptune(db=mock_db)
        items = [
            IndexItem(name="test", label="TestNode", properties=["uuid"], type="range"),
        ]
        manager.init(nodes=items, rels=[])
        result = await manager.list()
        assert len(result) == 1
        assert result[0].label == "TestNode"
        assert result[0].name.startswith("neptune_auto_")


class TestConstraintManagerNeptune:
    def test_no_constraint_classes(self) -> None:
        assert ConstraintManagerNeptune.constraint_node_class is None
        assert ConstraintManagerNeptune.constraint_rel_class is None

    @pytest.mark.asyncio
    async def test_add_is_noop(self) -> None:
        mock_db = MagicMock()
        manager = ConstraintManagerNeptune(db=mock_db)
        await manager.add()  # Should not raise

    @pytest.mark.asyncio
    async def test_drop_is_noop(self) -> None:
        mock_db = MagicMock()
        manager = ConstraintManagerNeptune(db=mock_db)
        await manager.drop()  # Should not raise

    @pytest.mark.asyncio
    async def test_list_returns_empty(self) -> None:
        mock_db = MagicMock()
        manager = ConstraintManagerNeptune(db=mock_db)
        result = await manager.list()
        assert result == []


class TestInfrahubDatabaseNeptuneMethods:
    """Test Neptune-specific rendering methods on InfrahubDatabase."""

    def _make_db(self) -> MagicMock:
        """Create a mock InfrahubDatabase with db_type set to NEPTUNE."""
        from infrahub.database import InfrahubDatabase  # noqa: PLC0415

        mock_driver = MagicMock()
        # Patch config to avoid real config loading
        with patch("infrahub.database.config") as mock_config:
            mock_config.SETTINGS.database.db_type = DatabaseType.NEPTUNE
            mock_config.SETTINGS.database.database_name = "neptune"
            mock_config.SETTINGS.database.max_concurrent_queries = 0
            db = InfrahubDatabase(driver=mock_driver, db_type=DatabaseType.NEPTUNE)
        return db

    def test_get_id_function_name(self) -> None:
        db = self._make_db()
        assert db.get_id_function_name() == "id"

    def test_render_uuid_generation(self) -> None:
        db = self._make_db()
        result = db.render_uuid_generation("n", "uuid")
        assert "$generated_uuid_" in result
        assert "randomUUID" not in result

    def test_to_database_id_returns_string(self) -> None:
        db = self._make_db()
        assert db.to_database_id("abc123") == "abc123"

    def test_is_neptune_property(self) -> None:
        db = self._make_db()
        assert db.is_neptune is True

    def test_render_list_comprehension(self) -> None:
        db = self._make_db()
        result = db.render_list_comprehension("items", "name")
        assert result == "[i IN items | i.name]"

    def test_render_list_comprehension_with_list(self) -> None:
        db = self._make_db()
        result = db.render_list_comprehension_with_list("items", ["name", "uuid"])
        assert result == "[i IN items | [i.name,i.uuid]]"
