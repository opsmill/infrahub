from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from neo4j.graph import Node, Relationship

from infrahub.cli.db import load_export, selected_export
from infrahub.database import InfrahubDatabase


class TestSelectedExportAndLoad:
    async def _get_before_vertex_and_edge_count_data(self, db: InfrahubDatabase):
        edge_details_by_vertex_dict: dict[str, dict[str, Any]] = {}
        # we don't include Branch objects in the export
        query = """MATCH (a)-[e]->(b) WHERE NOT "Branch" IN labels(a) RETURN a, e, b"""
        results = await db.execute_query(query=query)
        for result in results:
            a: Node = result.get("a")
            e: Relationship = result.get("e")
            b: Node = result.get("b")
            if a.element_id not in edge_details_by_vertex_dict:
                edge_details_by_vertex_dict[a.element_id] = {"labels": a.labels, "edges": set()}
            edge_details = (
                e.type,
                e.get("branch"),
                e.get("status"),
                e.get("hierarchy"),
                e.get("from"),
                e.get("to"),
                b.element_id,
            )
            edge_details_by_vertex_dict[a.element_id]["edges"].add(edge_details)
        return edge_details_by_vertex_dict

    async def _get_after_vertex_and_edge_count_data(self, db: InfrahubDatabase):
        edge_details_by_vertex_dict: dict[str, dict[str, Any]] = {}
        query = "MATCH (a)-[e]->(b) RETURN a, e, b"
        results = await db.execute_query(query=query)
        for result in results:
            a: Node = result.get("a")
            e: Relationship = result.get("e")
            b: Node = result.get("b")
            a_db_id = a.get("db_id")
            b_db_id = b.get("db_id")
            if a_db_id not in edge_details_by_vertex_dict:
                # this label will only exist in the export
                labels = frozenset(lbl for lbl in a.labels if lbl != "ImportNode")
                edge_details_by_vertex_dict[a_db_id] = {"labels": labels, "edges": set()}
            edge_details = (
                e.type,
                e.get("branch"),
                e.get("status"),
                e.get("hierarchy"),
                e.get("from"),
                e.get("to"),
                b_db_id,
            )
            edge_details_by_vertex_dict[a_db_id]["edges"].add(edge_details)
        return edge_details_by_vertex_dict

    async def test_export_and_load(
        self, db: InfrahubDatabase, hierarchical_location_data_thing: dict[str, Node]
    ) -> None:
        """Validate that database structure is preserved across selected export and import"""
        before_details = await self._get_before_vertex_and_edge_count_data(db=db)

        with TemporaryDirectory() as temp_dir:
            temp_dir_path = Path(temp_dir)
            export_dir = await selected_export(db=db, kinds=[], uuids=[], export_dir=temp_dir_path, query_limit=20)

            await db.execute_query("MATCH (n) DETACH DELETE n")

            await load_export(db=db, export_dir=export_dir, query_limit=10)

        after_details = await self._get_after_vertex_and_edge_count_data(db=db)

        assert before_details == after_details
