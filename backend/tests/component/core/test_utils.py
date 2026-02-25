import ipaddress

import pytest

from infrahub.core.utils import convert_ip_to_binary_str
from infrahub.database import InfrahubDatabase


@pytest.mark.parametrize(
    "input,response",
    [
        (ipaddress.ip_network("10.10.0.0/22"), "00001010000010100000000000000000"),
        (ipaddress.ip_interface("10.10.22.23/22"), "00001010000010100001011000010111"),
        (ipaddress.ip_interface("192.0.22.23/22"), "11000000000000000001011000010111"),
    ],
)
def test_convert_ip_to_binary_str(input: ipaddress.IPv4Network | ipaddress.IPv4Interface, response: str) -> None:
    assert convert_ip_to_binary_str(obj=input) == response


async def verify_all_linked_edges_deleted(db: InfrahubDatabase, node_uuid: str, branch_name: str) -> None:
    """
    Verify that a node is completely deleted at the database level

    check that all edges linked to a given node on a given branch are deleted or inactive
    """
    query = """
    MATCH (n:Node {uuid: $node_uuid})-[r1]-(attr_rel)-[r2]-(p)
    WHERE p <> n
    AND r1.branch = $target_branch
    AND r2.branch = $target_branch
    AND (
        "Attribute" IN labels(attr_rel) OR "Relationship" IN labels(attr_rel)
    )
    WITH n, attr_rel, p, r1, r2
    ORDER by r1.from DESC, r2.from DESC
    WITH n, type(r1) AS r1_type, attr_rel, type(r2) AS r2_type, p, head(collect(r1)) AS latest_r1, head(collect(r2)) AS latest_r2
    RETURN n, attr_rel, p, latest_r1, latest_r2,
        (
            (latest_r1.status = "deleted" AND latest_r1.to IS NULL)
            OR (latest_r1.status = "active" AND latest_r1.to IS NOT NULL)
        ) AS latest_r1_is_deleted,
        (
            (latest_r2.status = "deleted" AND latest_r2.to IS NULL)
            OR (latest_r2.status = "active" AND latest_r2.to IS NOT NULL)
        ) AS latest_r2_is_deleted
    """
    records = await db.execute_query(query=query, params={"node_uuid": node_uuid, "target_branch": branch_name})
    for record in records:
        if record.get("latest_r1_is_deleted") is False or record.get("latest_r2_is_deleted") is False:
            node_uuid = record.get("n", {}).get("uuid")
            r1 = record.get("latest_r1")
            r1_type = r1.type if r1 else None
            attr_rel_name = record.get("attr_rel", {}).get("name")
            r2 = record.get("latest_r2")
            r2_type = r2.type if r2 else None
            p = record.get("p", {})
            p_label = p.get("uuid") or p.get("value")
            raise ValueError(
                f"Latest path '{node_uuid}'-[{r1_type}]-'{attr_rel_name}'-[{r2_type}]-'{p_label}' is not deleted"
            )

    query = """
    MATCH (n:Node {uuid: $node_uuid})<-[r1]-(attr_rel)
    WHERE r1.branch = $target_branch
    AND type(r1) IN ["HAS_OWNER", "HAS_SOURCE"]
    WITH n, attr_rel, r1
    ORDER by r1.from DESC
    WITH n, attr_rel, head(collect(r1)) AS latest_r1
    RETURN n, attr_rel, latest_r1,
        (
            (latest_r1.status = "deleted" AND latest_r1.to IS NULL)
            OR (latest_r1.status = "active" AND latest_r1.to IS NOT NULL)
        ) AS latest_r1_is_deleted
    """
    records = await db.execute_query(query=query, params={"node_uuid": node_uuid, "target_branch": branch_name})
    for record in records:
        if record.get("latest_r1_is_deleted") is False:
            node_uuid = record.get("n", {}).get("uuid")
            r1 = record.get("latest_r1")
            r1_type = r1.type if r1 else None
            attr_rel_name = record.get("attr_rel", {}).get("name")
            raise ValueError(f"Latest path '{node_uuid}'<-[{r1_type}]-'{attr_rel_name}' is not deleted")
