from typing import Any

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.query.diff_get import EnrichedDiffGetQuery
from infrahub.core.diff.query.diff_summary import DiffSummaryCounters, DiffSummaryQuery, EnrichedDiffQueryFilters
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import SchemaRoot
from infrahub.database import InfrahubDatabase
from infrahub.dependencies.registry import get_component_registry
from tests.helpers.test_app import TestInfrahub


class TestDiffReadQuery(TestInfrahub):
    @pytest.fixture(scope="class")
    async def hierarchical_location_schema(self, db: InfrahubDatabase, default_branch: Branch) -> None:
        SCHEMA: dict[str, Any] = {
            "generics": [
                {
                    "name": "Generic",
                    "namespace": "Location",
                    "default_filter": "name__value",
                    "display_labels": ["name__value"],
                    "hierarchical": True,
                    "attributes": [
                        {"name": "name", "kind": "Text", "unique": True},
                        {"name": "status", "kind": "Text", "enum": ["online", "offline"], "default_value": "online"},
                    ],
                    "relationships": [
                        {"name": "things", "peer": "TestThing", "cardinality": "many", "optional": True},
                    ],
                }
            ],
            "nodes": [
                {
                    "name": "Region",
                    "namespace": "Location",
                    "default_filter": "name__value",
                    "inherit_from": ["LocationGeneric"],
                    "parent": "",
                    "children": "LocationSite",
                },
                {
                    "name": "Site",
                    "namespace": "Location",
                    "default_filter": "name__value",
                    "inherit_from": ["LocationGeneric"],
                    "parent": "LocationRegion",
                    "children": "LocationRack",
                },
                {
                    "name": "Rack",
                    "namespace": "Location",
                    "default_filter": "name__value",
                    "order_by": ["name__value"],
                    "inherit_from": ["LocationGeneric"],
                    "parent": "LocationSite",
                    "children": "",
                },
                {
                    "name": "Thing",
                    "namespace": "Test",
                    "default_filter": "name__value",
                    "display_labels": ["name__value"],
                    "attributes": [
                        {"name": "name", "kind": "Text", "unique": True},
                    ],
                    "relationships": [
                        {"name": "location", "peer": "LocationGeneric", "cardinality": "one", "optional": False},
                    ],
                },
            ],
        }

        schema = SchemaRoot(**SCHEMA)
        registry.schema.register_schema(schema=schema, branch=default_branch.name)

    @pytest.fixture(scope="class")
    async def hierarchical_data(self, db: InfrahubDatabase, default_branch: Branch, hierarchical_location_schema):
        REGIONS = (
            ("north-america",),
            ("europe",),
            ("asia",),
        )

        SITES = (
            ("paris", "europe"),
            ("london", "europe"),
            ("chicago", "north-america"),
            ("seattle", "north-america"),
            ("beijing", "asia"),
            ("singapore", "asia"),
        )
        NBR_RACKS_PER_SITE = 2

        nodes = {}

        for region in REGIONS:
            obj = await Node.init(db=db, schema="LocationRegion")
            await obj.new(db=db, name=region[0])
            await obj.save(db=db)
            nodes[obj.name.value] = obj

        for site in SITES:
            obj = await Node.init(db=db, schema="LocationSite")
            await obj.new(db=db, name=site[0], parent=site[1])
            await obj.save(db=db)
            nodes[obj.name.value] = obj

            for idx in range(1, NBR_RACKS_PER_SITE + 1):
                rack_name = f"{site[0]}-r{idx}"
                statuses = ["online", "offline"]
                obj = await Node.init(db=db, schema="LocationRack")
                await obj.new(db=db, name=rack_name, parent=site[0], status=statuses[idx - 1])
                await obj.save(db=db)
                nodes[obj.name.value] = obj

        return nodes

    @pytest.fixture(scope="class")
    async def load_data(self, db: InfrahubDatabase, default_branch: Branch, hierarchical_data):
        rack1_main = hierarchical_data["paris-r1"]
        rack2_main = hierarchical_data["paris-r2"]

        thing1_main = await Node.init(db=db, schema="TestThing")
        await thing1_main.new(db=db, name="thing1", location=rack1_main)
        await thing1_main.save(db=db)

        thing2_main = await Node.init(db=db, schema="TestThing")
        await thing2_main.new(db=db, name="thing2", location=rack2_main)
        await thing2_main.save(db=db)

        diff_branch = await create_branch(db=db, branch_name="diff")

        thing3_branch = await Node.init(db=db, schema="TestThing", branch=diff_branch)
        await thing3_branch.new(db=db, name="thing3", location=rack1_main)
        await thing3_branch.save(db=db)

        # rprint(hierarchical_location_data)
        rack1_branch = await NodeManager.get_one(db=db, id=rack1_main.id, branch=diff_branch)
        rack1_branch.status.value = "offline"
        rack2_branch = await NodeManager.get_one(db=db, id=rack2_main.id, branch=diff_branch)
        rack2_branch.name.value = "paris rack2"

        await rack1_branch.save(db=db)
        await rack2_branch.save(db=db)

        thing1_branch = await NodeManager.get_one(db=db, id=thing1_main.id, branch=diff_branch)
        thing1_branch.name.value = "THING1"
        await thing1_branch.save(db=db)

        component_registry = get_component_registry()
        diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=diff_branch)
        # diff_repo = await component_registry.get_component(DiffRepository, db=db, branch=diff_branch)

        enriched_diff = await diff_coordinator.update_branch_diff(
            base_branch=default_branch,
            diff_branch=diff_branch,
        )

        return {
            "diff_branch": diff_branch,
            "from_time": enriched_diff.from_time,
            "to_time": enriched_diff.to_time,
        }

    @pytest.mark.parametrize(
        "filters,counters",
        [
            pytest.param({}, DiffSummaryCounters(num_added=2, num_updated=4), id="no-filters"),
            pytest.param(
                {"kind": {"includes": ["TestThing"]}},
                DiffSummaryCounters(num_added=2, num_updated=1),
                id="kind-includes",
            ),
            pytest.param({"kind": {"excludes": ["TestThing"]}}, DiffSummaryCounters(num_updated=3), id="kind-excludes"),
            pytest.param(
                {"namespace": {"includes": ["Test"]}},
                DiffSummaryCounters(num_added=2, num_updated=1),
                id="namespace-includes",
            ),
            pytest.param(
                {"namespace": {"excludes": ["Location"]}},
                DiffSummaryCounters(num_added=2, num_updated=1),
                id="namespace-excludes",
            ),
            pytest.param(
                {"status": {"includes": ["updated"]}}, DiffSummaryCounters(num_updated=4), id="status-includes"
            ),
            pytest.param(
                {"status": {"excludes": ["unchanged"]}},
                DiffSummaryCounters(num_added=2, num_updated=4),
                id="status-excludes",
            ),
            pytest.param(
                {"kind": {"includes": ["TestThing"]}, "status": {"excludes": ["added"]}},
                DiffSummaryCounters(num_updated=1),
                id="kind-includes-status-excludes",
            ),
        ],
    )
    async def test_summary_no_filter(self, db: InfrahubDatabase, default_branch: Branch, load_data, filters, counters):
        query = await DiffSummaryQuery.init(
            db=db,
            base_branch_name=default_branch.name,
            diff_branch_names=[load_data["diff_branch"].name],
            from_time=load_data["from_time"],
            to_time=load_data["to_time"],
            filters=EnrichedDiffQueryFilters(**filters),
        )
        await query.execute(db=db)

        summary = query.get_summary()
        assert summary == counters

    async def test_get_without_parent(self, db: InfrahubDatabase, default_branch: Branch, load_data):
        query = await EnrichedDiffGetQuery.init(
            db=db,
            base_branch_name=default_branch.name,
            diff_branch_names=[load_data["diff_branch"].name],
            from_time=load_data["from_time"],
            to_time=load_data["to_time"],
            filters=EnrichedDiffQueryFilters(status={"includes": ["updated"]}),
            max_depth=10,
            limit=1000,
            offset=0,
        )
        await query.execute(db=db)

        diffs_without = await query.get_enriched_diff_roots(include_parents=False)
        diffs_with = await query.get_enriched_diff_roots(include_parents=True)

        assert set([node.label for node in diffs_without[0].nodes]) == {"paris-r1", "paris rack2", "THING1"}
        assert set([node.label for node in diffs_with[0].nodes]) == {
            "paris",
            "THING1",
            "paris-r1",
            "paris rack2",
            "europe",
        }
