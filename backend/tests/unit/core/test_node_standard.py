from typing import Any, Dict, List, Optional

from pydantic.v1 import BaseModel

from infrahub.core.node.standard import StandardNode
from infrahub.database import InfrahubDatabase


class MyStdNode(StandardNode):
    attr1_str: str
    attr2_int: int
    attr3_int: Optional[int] = None
    attr4_bool: bool = False
    attr5_dict: dict


class OtherStdNode(StandardNode):
    name: str


class MyModel(BaseModel):
    key1: int
    key2: str


class PadanticStdNode(StandardNode):
    name: str
    mymodel: MyModel
    mydict: Dict[str, Any]
    mylistofmodel: List[MyModel]


async def test_node_standard_create(db: InfrahubDatabase, empty_database):
    obj1 = MyStdNode(
        attr1_str="obj1", attr2_int=1, attr4_bool=True, attr5_dict={"key1": "value2", "key2": {"key21": "Value21"}}
    )
    await obj1.save(db=db)

    assert obj1.id is not None


async def test_node_standard_delete(db: InfrahubDatabase, empty_database):
    obj1 = OtherStdNode(name="obj1")
    await obj1.save(db=db)
    obj2 = OtherStdNode(name="obj2")
    await obj2.save(db=db)

    objs = await OtherStdNode.get_list(db=db)
    assert len(objs) == 2
    await objs[1].delete(db=db)

    objs = await OtherStdNode.get_list(db=db)
    assert len(objs) == 1


async def test_node_standard_get(db: InfrahubDatabase, empty_database):
    obj1 = MyStdNode(
        attr1_str="obj1", attr2_int="1", attr4_bool=True, attr5_dict={"key1": "value2", "key2": {"key21": "Value21"}}
    )
    assert await obj1.save(db=db)

    obj11 = await MyStdNode.get(id=obj1.uuid, db=db)
    assert obj11.dict(exclude={"uuid"}) == obj1.dict(exclude={"uuid"})
    assert str(obj11.uuid) == str(obj1.uuid)
    assert obj11.attr3_int is None


async def test_node_standard_update(db: InfrahubDatabase, empty_database):
    attr5_value = {"key1": "value2", "key2": {"key21": "Value21"}}
    obj1 = MyStdNode(attr1_str="obj1", attr2_int=1, attr4_bool=True, attr5_dict=attr5_value)
    assert await obj1.save(db=db)

    obj11 = await MyStdNode.get(id=obj1.uuid, db=db)
    assert obj11.dict(exclude={"uuid"}) == obj1.dict(exclude={"uuid"})
    assert str(obj11.uuid) == str(obj1.uuid)
    assert obj11.attr3_int is None
    assert obj11.attr5_dict == attr5_value

    obj11.attr1_str = "obj11"
    obj11.attr2_int = 10
    obj11.attr5_dict = {"key11": "value12", "key2": {"key21": "Value21"}}
    await obj11.save(db=db)

    obj12 = await MyStdNode.get(id=obj1.uuid, db=db)
    assert obj12.dict(exclude={"uuid"}) == obj11.dict(exclude={"uuid"})


async def test_node_standard_list(db: InfrahubDatabase, empty_database):
    obj1 = OtherStdNode(name="obj1")
    await obj1.save(db=db)
    obj2 = OtherStdNode(name="obj2")
    await obj2.save(db=db)
    obj3 = OtherStdNode(name="obj3")
    await obj3.save(db=db)

    objs = await OtherStdNode.get_list(db=db)
    assert len(objs) == 3
    assert isinstance(objs[0], OtherStdNode)

    objs = await OtherStdNode.get_list(db=db, ids=[obj1.uuid, obj3.uuid])
    assert len(objs) == 2

    objs = await OtherStdNode.get_list(db=db, name=obj2.name)
    assert len(objs) == 1
    assert objs[0].dict(exclude={"uuid"}) == obj2.dict(exclude={"uuid"})


async def test_node_standard_pydantic(db: InfrahubDatabase, empty_database):
    obj1 = PadanticStdNode(
        name="obj1",
        mymodel={"key1": 1, "key2": "value2"},
        mydict={"key1": 1, "key2": "value2"},
        mylistofmodel=[{"key1": 1, "key2": "value2"}],
    )
    await obj1.save(db=db)

    obj11 = await PadanticStdNode.get(id=obj1.uuid, db=db)
    assert obj11.dict(exclude={"uuid"}) == obj1.dict(exclude={"uuid"})
