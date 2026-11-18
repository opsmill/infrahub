from dataclasses import dataclass

import pytest

from infrahub.core.branch import Branch
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from tests.helpers.graphql import graphql_query


@dataclass
class EdgeMetadataSelectionCase:
    name: str
    include_relationship_metadata: bool
    expected_empty_peer: dict[str, None]


EDGE_METADATA_SELECTION_CASES: list[EdgeMetadataSelectionCase] = [
    EdgeMetadataSelectionCase(
        name="node_metadata",
        include_relationship_metadata=False,
        expected_empty_peer={"node": None, "node_metadata": None},
    ),
    EdgeMetadataSelectionCase(
        name="node_and_relationship_metadata",
        include_relationship_metadata=True,
        expected_empty_peer={"node": None, "node_metadata": None, "relationship_metadata": None},
    ),
]


class TestHierarchyNodeMetadata:
    @pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in EDGE_METADATA_SELECTION_CASES])
    async def test_parent_node_metadata_without_parent(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        hierarchical_location_data_scope_class: dict[str, Node],
        test_case: EdgeMetadataSelectionCase,
    ) -> None:
        relationship_metadata = (
            "relationship_metadata { updated_at }" if test_case.include_relationship_metadata else ""
        )
        query = """
        query {
            LocationRegion(name__value: "europe") {
                edges {
                    node {
                        parent {
                            node {
                                id
                            }
                            node_metadata {
                                created_at
                            }
                            %(relationship_metadata)s
                        }
                    }
                    node_metadata {
                        created_at
                    }
                }
            }
            LocationSite(name__value: "paris") {
                edges {
                    node {
                        parent {
                            node {
                                id
                            }
                            node_metadata {
                                created_at
                            }
                            %(relationship_metadata)s
                        }
                    }
                }
            }
        }
        """ % {"relationship_metadata": relationship_metadata}
        result = await graphql_query(query=query, db=db, branch=default_branch_scope_class)

        assert result.errors is None
        assert result.data
        region_edge = result.data["LocationRegion"]["edges"][0]
        site_parent = result.data["LocationSite"]["edges"][0]["node"]["parent"]
        assert region_edge["node_metadata"]["created_at"] is not None
        assert region_edge["node"]["parent"] == test_case.expected_empty_peer
        assert site_parent["node"] == {"id": hierarchical_location_data_scope_class["europe"].id}
        assert site_parent["node_metadata"] == {"created_at": region_edge["node_metadata"]["created_at"]}
        if test_case.include_relationship_metadata:
            assert site_parent["relationship_metadata"]["updated_at"] is not None

    async def test_ancestors_and_descendants_node_metadata(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        hierarchical_location_data_scope_class: dict[str, Node],
    ) -> None:
        query = """
        query {
            LocationSite(name__value: "paris") {
                edges {
                    node {
                        ancestors {
                            edges {
                                node {
                                    id
                                }
                                node_metadata {
                                    created_at
                                    updated_at
                                }
                            }
                        }
                        descendants {
                            edges {
                                node {
                                    id
                                }
                                node_metadata {
                                    created_at
                                    updated_at
                                }
                            }
                        }
                    }
                }
            }
            LocationGeneric {
                edges {
                    node {
                        id
                    }
                    node_metadata {
                        created_at
                        updated_at
                    }
                }
            }
        }
        """
        result = await graphql_query(query=query, db=db, branch=default_branch_scope_class)

        assert result.errors is None
        assert result.data
        metadata_by_id = {edge["node"]["id"]: edge["node_metadata"] for edge in result.data["LocationGeneric"]["edges"]}
        paris = result.data["LocationSite"]["edges"][0]["node"]
        ancestors = paris["ancestors"]["edges"]
        descendants = paris["descendants"]["edges"]

        assert [edge["node"]["id"] for edge in ancestors] == [hierarchical_location_data_scope_class["europe"].id]
        assert sorted(edge["node"]["id"] for edge in descendants) == sorted(
            [
                hierarchical_location_data_scope_class["paris-r1"].id,
                hierarchical_location_data_scope_class["paris-r2"].id,
            ]
        )
        for edge in ancestors + descendants:
            assert edge["node_metadata"]["created_at"] is not None
            assert edge["node_metadata"] == metadata_by_id[edge["node"]["id"]]


@pytest.fixture(scope="class")
async def person_car_data(
    db: InfrahubDatabase, default_branch_scope_class: Branch, generic_car_person_schema_scope_class: None
) -> dict[str, Node]:
    car = await Node.init(db=db, schema="TestElectricCar", branch=default_branch_scope_class)
    await car.new(db=db, name="volt", color="blue")
    await car.save(db=db)
    person_without_car = await Node.init(db=db, schema="TestPerson", branch=default_branch_scope_class)
    await person_without_car.new(db=db, name="alice")
    await person_without_car.save(db=db)
    person_with_car = await Node.init(db=db, schema="TestPerson", branch=default_branch_scope_class)
    await person_with_car.new(db=db, name="bob", car=car)
    await person_with_car.save(db=db)
    return {"volt": car, "alice": person_without_car, "bob": person_with_car}


class TestOptionalRelationshipToGenericNodeMetadata:
    @pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in EDGE_METADATA_SELECTION_CASES])
    async def test_node_metadata_without_peer(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        person_car_data: dict[str, Node],
        test_case: EdgeMetadataSelectionCase,
    ) -> None:
        relationship_metadata = (
            "relationship_metadata { updated_at }" if test_case.include_relationship_metadata else ""
        )
        query = """
        query {
            TestPerson {
                edges {
                    node {
                        name {
                            value
                        }
                        car {
                            node {
                                id
                            }
                            node_metadata {
                                created_at
                            }
                            %(relationship_metadata)s
                        }
                    }
                }
            }
            TestElectricCar {
                edges {
                    node_metadata {
                        created_at
                    }
                }
            }
        }
        """ % {"relationship_metadata": relationship_metadata}
        result = await graphql_query(query=query, db=db, branch=default_branch_scope_class)

        assert result.errors is None
        assert result.data
        car_by_person = {
            edge["node"]["name"]["value"]: edge["node"]["car"] for edge in result.data["TestPerson"]["edges"]
        }
        car_metadata = result.data["TestElectricCar"]["edges"][0]["node_metadata"]
        assert car_by_person["alice"] == test_case.expected_empty_peer
        assert car_by_person["bob"]["node"] == {"id": person_car_data["volt"].id}
        assert car_by_person["bob"]["node_metadata"] == car_metadata
        if test_case.include_relationship_metadata:
            assert car_by_person["bob"]["relationship_metadata"]["updated_at"] is not None
