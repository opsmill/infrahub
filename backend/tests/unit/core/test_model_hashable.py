from typing import List, Optional

from deepdiff import DeepDiff

from infrahub.core.models import HashableModel


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
        "name": "node1",
        "subs": [
            {"name": "coconut", "value1": None, "value2": None},
            {"name": "apple", "value1": None, "value2": None},
            {"name": "orange", "value1": "toreplace", "value2": 22},
        ],
        "value1": "FIRST",
        "value2": 2,
        "value3": ["one", "two", "three"],
    }

    assert DeepDiff(expected_result, node1.update(node2).model_dump()).to_dict() == {}
