from typing import Optional

from neo4j import AsyncSession

from infrahub.core.node.standard import StandardNode


class MyStdNode(StandardNode):
    attr1_str: str
    attr2_int: int
    attr3_int: Optional[int] = None
    attr4_bool: bool = False
    attr5_dict: dict


class OtherStdNode(StandardNode):
    name: str


async def test_node_standard_create(session: AsyncSession, empty_database):
    obj1 = MyStdNode(
        attr1_str="obj1", attr2_int=1, attr4_bool=True, attr5_dict={"key1": "value2", "key2": {"key21": "Value21"}}
    )
    await obj1.save(session=session)

    assert obj1.id is not None


async def test_node_standard_get(session: AsyncSession, empty_database):
    obj1 = MyStdNode(
        attr1_str="obj1", attr2_int="1", attr4_bool=True, attr5_dict={"key1": "value2", "key2": {"key21": "Value21"}}
    )
    assert await obj1.save(session=session)

    obj11 = await MyStdNode.get(id=obj1.uuid, session=session)
    assert obj11.dict(exclude={"uuid"}) == obj1.dict(exclude={"uuid"})
    assert str(obj11.uuid) == str(obj1.uuid)
    assert obj11.attr3_int == None


async def test_node_standard_update(session: AsyncSession, empty_database):
    attr5_value = {"key1": "value2", "key2": {"key21": "Value21"}}
    obj1 = MyStdNode(attr1_str="obj1", attr2_int=1, attr4_bool=True, attr5_dict=attr5_value)
    assert await obj1.save(session=session)

    obj11 = await MyStdNode.get(id=obj1.uuid, session=session)
    assert obj11.dict(exclude={"uuid"}) == obj1.dict(exclude={"uuid"})
    assert str(obj11.uuid) == str(obj1.uuid)
    assert obj11.attr3_int == None
    assert obj11.attr5_dict == attr5_value

    obj11.attr1_str = "obj11"
    obj11.attr2_int = 10
    obj11.attr5_dict = {"key11": "value12", "key2": {"key21": "Value21"}}
    await obj11.save(session=session)

    obj12 = await MyStdNode.get(id=obj1.uuid, session=session)
    assert obj12.dict(exclude={"uuid"}) == obj11.dict(exclude={"uuid"})


async def test_node_standard_list(session: AsyncSession, empty_database):
    obj1 = OtherStdNode(name="obj1")
    await obj1.save(session=session)
    obj2 = OtherStdNode(name="obj2")
    await obj2.save(session=session)
    obj3 = OtherStdNode(name="obj3")
    await obj3.save(session=session)

    objs = await OtherStdNode.get_list(session=session)
    assert len(objs) == 3
    assert isinstance(objs[0], OtherStdNode)

    objs = await OtherStdNode.get_list(session=session, ids=[obj1.uuid, obj3.uuid])
    assert len(objs) == 2

    objs = await OtherStdNode.get_list(session=session, name=obj2.name)
    assert len(objs) == 1
    assert objs[0].dict(exclude={"uuid"}) == obj2.dict(exclude={"uuid"})
