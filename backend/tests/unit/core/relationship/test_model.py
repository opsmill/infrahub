from collections.abc import Callable
from dataclasses import dataclass

import pytest

from infrahub.core.branch import Branch
from infrahub.core.relationship.model import Relationship, RelationshipValidatorList
from tests.helpers.schema.person import PERSON


def _relationships(count: int) -> list[Relationship]:
    rel_schema = PERSON.get_relationship(name="cars")
    branch = Branch(name="main")
    return [
        Relationship(schema=rel_schema, branch=branch, source_kind=PERSON.kind, node_id="person-id")
        for _ in range(count)
    ]


@dataclass
class ValidatorListChangeCase:
    name: str
    change: Callable[[RelationshipValidatorList, list[Relationship]], object]
    expected: list[int]
    """Positions in the relationships of the fixture, in the order the list holds them after the change."""


VALIDATOR_LIST_CHANGE_CASES = [
    ValidatorListChangeCase(name="append", change=lambda result, rels: result.append(rels[2]), expected=[0, 1, 2]),
    ValidatorListChangeCase(
        name="append_duplicate", change=lambda result, rels: result.append(rels[0]), expected=[0, 1]
    ),
    ValidatorListChangeCase(name="insert", change=lambda result, rels: result.insert(0, rels[2]), expected=[2, 0, 1]),
    ValidatorListChangeCase(
        name="insert_duplicate", change=lambda result, rels: result.insert(0, rels[1]), expected=[0, 1]
    ),
    ValidatorListChangeCase(
        name="extend_with_duplicates",
        change=lambda result, rels: result.extend([rels[2], rels[2], rels[0]]),
        expected=[0, 1, 2],
    ),
    ValidatorListChangeCase(
        name="setitem", change=lambda result, rels: result.__setitem__(1, rels[2]), expected=[0, 2]
    ),
    ValidatorListChangeCase(name="delitem", change=lambda result, _: result.__delitem__(0), expected=[1]),
    ValidatorListChangeCase(name="pop_last", change=lambda result, _: result.pop(), expected=[0]),
    ValidatorListChangeCase(name="pop_first", change=lambda result, _: result.pop(0), expected=[1]),
    ValidatorListChangeCase(
        name="replace",
        change=lambda result, rels: result.replace(rel_to_insert=rels[2], rel_to_remove=rels[0]),
        expected=[1, 2],
    ),
    ValidatorListChangeCase(
        name="replace_with_held_relationship",
        change=lambda result, rels: result.replace(rel_to_insert=rels[1], rel_to_remove=rels[0]),
        expected=[1],
    ),
    ValidatorListChangeCase(name="remove", change=lambda result, rels: result.remove(rels[1]), expected=[0]),
    ValidatorListChangeCase(name="clear", change=lambda result, _: result.clear(), expected=[]),
]


@pytest.mark.parametrize("test_case", VALIDATOR_LIST_CHANGE_CASES, ids=lambda case: case.name)
def test_relationship_validate_change_keeps_ids_in_sync(test_case: ValidatorListChangeCase) -> None:
    rels = _relationships(count=3)
    result = RelationshipValidatorList(rels[0], rels[1], name="name")

    test_case.change(result, rels)

    # Read before len(), which corrects a count that a change left behind.
    assert result._relationships_count == len(test_case.expected)
    assert [rels.index(rel) for rel in result] == test_case.expected
    assert result._relationship_ids == {id(rels[position]) for position in test_case.expected}
    assert [rel in result for rel in rels] == [position in test_case.expected for position in range(3)]

    # A relationship the change removed can be added again, and one still held is not added twice.
    result.extend(rels)
    assert [rels.index(rel) for rel in result] == test_case.expected + [
        position for position in range(3) if position not in test_case.expected
    ]


def test_relationship_validate_init_duplicate() -> None:
    (rel,) = _relationships(count=1)

    result = RelationshipValidatorList(rel, rel, name="name")

    assert result.as_list() == [rel]
    assert result._relationships_count == 1
    assert result._relationship_ids == {id(rel)}
