from infrahub.core import SchemaRegistry, get_branch, get_branch_from_registry
from infrahub.core.branch import Branch
from infrahub.core.schema import NodeSchema


async def test_get_branch_from_registry(session, default_branch):
    br1 = get_branch_from_registry()
    assert br1.name == default_branch.name

    br2 = get_branch_from_registry(default_branch.name)
    assert br2.name == default_branch.name


async def test_get_branch_not_in_registry(session, default_branch):
    branch1 = Branch(name="branch1", status="OPEN")
    await branch1.save(session=session)

    br1 = await get_branch(branch=branch1.name, session=session)
    assert br1.name == branch1.name


async def test_schema_registry_set():
    SCHEMA = {
        "name": "criticality",
        "kind": "Criticality",
        "default_filter": "name__value",
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
            {"name": "description", "kind": "Text"},
        ],
    }
    schema = NodeSchema(**SCHEMA)

    sr = SchemaRegistry()

    sr.set(name="schema1", schema=schema)
    assert hash(schema) in sr._cache
    assert len(sr._cache) == 1

    sr.set(name="schema2", schema=schema)
    assert len(sr._cache) == 1


async def test_schema_registry_get():
    SCHEMA = {
        "name": "criticality",
        "kind": "Criticality",
        "default_filter": "name__value",
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
            {"name": "description", "kind": "Text"},
        ],
    }
    schema = NodeSchema(**SCHEMA)

    sr = SchemaRegistry()

    sr.set(name="schema1", schema=schema)
    assert len(sr._cache) == 1

    schema11 = sr.get(name="schema1")
    assert schema11 == schema
