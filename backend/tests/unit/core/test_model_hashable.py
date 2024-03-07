from typing import List, Optional

from deepdiff import DeepDiff

from infrahub.core.constants import HashableModelState
from infrahub.core.models import HashableModel, HashableModelDiff


def test_hashable_diff():
    diff1 = HashableModelDiff()
    diff2 = HashableModelDiff(added={"first": None})
    diff3 = HashableModelDiff(changed={"first": None})
    diff4 = HashableModelDiff(removed={"first": None})

    assert diff1.has_diff is False
    assert diff2.has_diff is True
    assert diff3.has_diff is True
    assert diff4.has_diff is True


def test_model_sorting():
    class MySchema(HashableModel):
        _sort_by: List[str] = ["first_name", "last_name"]
        first_name: str
        last_name: str

    my_list = [
        MySchema(first_name="John", last_name="Doe"),
        MySchema(first_name="David", last_name="Doe"),
        MySchema(first_name="David", last_name="Smith"),
    ]
    sorted_list = sorted(my_list)

    sorted_names = [(item.first_name, item.last_name) for item in sorted_list]
    assert sorted_names == [("David", "Doe"), ("David", "Smith"), ("John", "Doe")]


def test_model_hashing():
    class MySubElement(HashableModel):
        _sort_by: List[str] = ["name"]
        name: str

    class MyTopElement(HashableModel):
        _sort_by: List[str] = ["name"]
        name: str
        subs: List[MySubElement]

    node1 = MyTopElement(
        name="node1", subs=[MySubElement(name="orange"), MySubElement(name="apple"), MySubElement(name="coconut")]
    )
    node2 = MyTopElement(
        name="node1", subs=[MySubElement(name="apple"), MySubElement(name="orange"), MySubElement(name="coconut")]
    )

    assert node1.get_hash() == node2.get_hash()


def test_hashing_dict():
    class MySubElement(HashableModel):
        _sort_by: List[str] = ["name"]
        name: str
        value1: Optional[dict] = None

    class MyTopElement(HashableModel):
        _sort_by: List[str] = ["name"]
        name: str
        subs: List[MySubElement]

    node1 = MyTopElement(
        name="node1", subs=[MySubElement(name="orange", value1={"bob": "Alice"}), MySubElement(name="coconut")]
    )
    node2 = MyTopElement(
        name="node1", subs=[MySubElement(name="orange", value1={"bob": "Alice"}), MySubElement(name="coconut")]
    )

    assert node1.get_hash() == node2.get_hash()


def test_update():
    class MySubElement(HashableModel):
        _sort_by: List[str] = ["name"]
        name: str
        value1: Optional[str] = None
        value2: Optional[int] = None

    class MyTopElement(HashableModel):
        _sort_by: List[str] = ["name"]
        name: str
        value1: Optional[str] = None
        value2: Optional[int] = None
        value3: List[str]
        subs: List[MySubElement]

    node1 = MyTopElement(
        name="node1",
        value1="first",
        value2=2,
        value3=["one", "two"],
        subs=[MySubElement(name="orange", value1="tochange", value2=22), MySubElement(name="coconut")],
    )
    node2 = MyTopElement(
        name="node1",
        value1="FIRST",
        value3=["one", "three"],
        subs=[MySubElement(name="apple"), MySubElement(name="orange", value1="toreplace")],
    )

    expected_result = {
        "id": None,
        "name": "node1",
        "state": HashableModelState.PRESENT,
        "subs": [
            {"id": None, "state": HashableModelState.PRESENT, "name": "coconut", "value1": None, "value2": None},
            {"id": None, "state": HashableModelState.PRESENT, "name": "apple", "value1": None, "value2": None},
            {"id": None, "state": HashableModelState.PRESENT, "name": "orange", "value1": "toreplace", "value2": 22},
        ],
        "value1": "FIRST",
        "value2": 2,
        "value3": ["one", "two", "three"],
    }

    assert DeepDiff(expected_result, node1.update(node2).model_dump()).to_dict() == {}


def test_update_element_absent():
    class MySubElement(HashableModel):
        _sort_by: List[str] = ["name"]
        name: str
        value1: Optional[str] = None
        value2: Optional[int] = None

    class MyTopElement(HashableModel):
        _sort_by: List[str] = ["name"]
        name: str
        value1: Optional[str] = None
        value2: Optional[int] = None
        value3: List[str]
        subs: List[MySubElement]

    node1 = MyTopElement(
        name="node1",
        value1="first",
        value2=2,
        value3=["one", "two"],
        subs=[MySubElement(name="orange", value1="tochange", value2=22), MySubElement(name="coconut")],
    )
    node2 = MyTopElement(
        name="node1",
        value1="FIRST",
        value3=["one", "three"],
        subs=[
            MySubElement(name="apple", state=HashableModelState.ABSENT),
            MySubElement(name="orange", value1="toreplace"),
        ],
    )

    expected_result = {
        "id": None,
        "name": "node1",
        "state": HashableModelState.PRESENT,
        "subs": [
            {"id": None, "state": HashableModelState.PRESENT, "name": "coconut", "value1": None, "value2": None},
            {"id": None, "state": HashableModelState.PRESENT, "name": "orange", "value1": "toreplace", "value2": 22},
        ],
        "value1": "FIRST",
        "value2": 2,
        "value3": ["one", "two", "three"],
    }

    assert DeepDiff(expected_result, node1.update(node2).model_dump()).to_dict() == {}


def test_update_rename():
    class MySubElement(HashableModel):
        _sort_by: List[str] = ["name"]
        name: str
        value1: Optional[str] = None
        value2: Optional[int] = None

    class MyTopElement(HashableModel):
        _sort_by: List[str] = ["name"]
        name: str
        value1: Optional[str] = None
        value2: Optional[int] = None
        value3: List[str]
        subs: List[MySubElement]

    node1 = MyTopElement(
        name="node1",
        value1="first",
        value2=2,
        value3=["one", "two"],
        subs=[MySubElement(id="123456", name="orange", value1="tochange", value2=22), MySubElement(name="coconut")],
    )
    node2 = MyTopElement(
        name="node1",
        value1="FIRST",
        value3=["one", "three"],
        subs=[
            MySubElement(name="apple", state=HashableModelState.ABSENT),
            MySubElement(id="123456", name="aa_orange", value1="toreplace"),
        ],
    )

    expected_result = {
        "id": None,
        "name": "node1",
        "state": HashableModelState.PRESENT,
        "subs": [
            {"id": None, "state": HashableModelState.PRESENT, "name": "coconut", "value1": None, "value2": None},
            {
                "id": "123456",
                "state": HashableModelState.PRESENT,
                "name": "aa_orange",
                "value1": "toreplace",
                "value2": 22,
            },
        ],
        "value1": "FIRST",
        "value2": 2,
        "value3": ["one", "two", "three"],
    }

    assert DeepDiff(expected_result, node1.update(node2).model_dump()).to_dict() == {}


def test_diff_simple_object():
    class ModelA(HashableModel):
        _sort_by: List[str] = ["name"]
        name: str
        value1: str
        value2: int
        value3: dict

    class ModelB(HashableModel):
        _sort_by: List[str] = ["name"]
        name: str
        value2: int
        value3: dict

    obj1 = ModelA(name="myobject", value1="my first object", value2=123, value3={"a": 123})
    obj11 = ModelA(name="myobject", value1="my first object", value2=123, value3={"a": 123})

    obj2 = ModelA(name="myobject", value1="my second object", value2=123, value3={"b": 321})
    obj3 = ModelB(name="myobject", value2=123, value3={"b": 321})

    diff_12 = obj1.diff(obj2)
    diff_13 = obj1.diff(obj3)

    assert obj1.diff(obj11).has_diff is False
    assert diff_12.has_diff is True
    assert diff_12.model_dump() == {"added": {}, "changed": {"value1": None, "value3": None}, "removed": {}}

    assert diff_13.has_diff is True
    assert diff_13.model_dump() == {"added": {"value1": None}, "changed": {"value3": None}, "removed": {}}


def test_diff_nested_objects():
    class MySubElement(HashableModel):
        _sort_by: List[str] = ["name"]
        name: str
        value1: Optional[str] = None
        value2: Optional[int] = None

    class MyTopElement(HashableModel):
        _sort_by: List[str] = ["name"]
        name: str
        value1: Optional[str] = None
        value2: Optional[int] = None
        value3: List[str]
        value4: MySubElement
        subs: List[MySubElement]

    node1 = MyTopElement(
        name="node1",
        value1="first",
        value2=2,
        value3=["one", "two"],
        value4=MySubElement(name="apple", value2=1254),
        subs=[MySubElement(name="orange", value1="tochange", value2=22), MySubElement(name="coconut")],
    )

    node2 = node1.duplicate()
    node2.subs[0].value1 = "new in node2"
    node2.value4.value2 = 987654

    diff1 = node1.diff(node2)
    assert diff1.has_diff
    assert diff1.model_dump() == {
        "added": {},
        "changed": {"subs": None, "value4": {"added": {}, "changed": {"value2": None}, "removed": {}}},
        "removed": {},
    }
