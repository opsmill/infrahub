from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.query.utils import find_node_schema
from infrahub.database import InfrahubDatabase


async def test_find_node_schema(db: InfrahubDatabase, group_schema: None, branch: Branch) -> None:
    labels = ["Node", "Group", InfrahubKind.STANDARDGROUP]
    schema = find_node_schema(db=db, branch=branch, labels=labels, duplicate=True)
    assert schema.kind == InfrahubKind.STANDARDGROUP

    labels = ["Node", InfrahubKind.GENERICGROUP]
    schema = find_node_schema(db=db, branch=branch, labels=labels, duplicate=False)
    assert schema is None
