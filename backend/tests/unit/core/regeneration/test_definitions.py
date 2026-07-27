from __future__ import annotations

from typing import Any

from infrahub.core.constants import InfrahubKind
from infrahub.core.regeneration.definitions import parse_artifact_definitions

QUERY_PAYLOAD = "query { TestingCar { edges { node { name { value } } } } }"


def _attribute(value: Any) -> dict[str, Any]:
    """Wrap a value the way an attribute resolves in a GraphQL response.

    An unset optional attribute still resolves as an object; only its ``value`` is null.
    """
    return {"value": value}


def _artifact_definition_edge(
    *,
    transform_typename: str = InfrahubKind.TRANSFORMJINJA2,
    dependencies: list[str] | None = None,
    dependencies_complete: bool | None = None,
    fingerprint: str | None = None,
    query_models: list[str] | None = None,
) -> dict[str, Any]:
    """Build one edge of the artifact-definition gathering query's response."""
    transformation: dict[str, Any] = {
        "__typename": transform_typename,
        "timeout": _attribute(30),
        "dependencies": _attribute(dependencies),
        "dependencies_complete": _attribute(dependencies_complete),
        "query": {
            "node": {
                "id": "query-1",
                "name": _attribute("GetCars"),
                "models": _attribute(query_models),
                "query": _attribute(QUERY_PAYLOAD),
            }
        },
        "repository": {"node": {"id": "repo-1"}},
    }
    if transform_typename == InfrahubKind.TRANSFORMJINJA2:
        transformation["template_path"] = _attribute("templates/config.j2")
    elif transform_typename == InfrahubKind.TRANSFORMPYTHON:
        transformation["class_name"] = _attribute("CarTransform")
        transformation["file_path"] = _attribute("transforms/car.py")
        transformation["convert_query_response"] = _attribute(True)

    return {
        "node": {
            "id": "def-1",
            "name": _attribute("car-config"),
            "artifact_name": _attribute("config"),
            "content_type": _attribute("text/plain"),
            "fingerprint": _attribute(fingerprint),
            "targets": {"node": {"id": "group-1"}},
            "transformation": {"node": transformation},
        }
    }


def test_transform_without_a_computed_closure_parses() -> None:
    """A transform whose closure and fingerprint were never computed parses with those left unset.

    This is the state of every transform imported before closures existed, so it has to survive
    parsing: the untrusted-closure classification downstream is what turns it into a full
    regeneration, and it can only run on a parsed definition.
    """
    parsed = parse_artifact_definitions([_artifact_definition_edge()])

    assert len(parsed) == 1
    definition = parsed[0]
    assert definition.dependencies is None
    assert definition.dependencies_complete is None
    assert definition.fingerprint is None


def test_computed_closure_is_carried_through() -> None:
    parsed = parse_artifact_definitions(
        [
            _artifact_definition_edge(
                dependencies=[".infrahub.yml", "templates/config.j2"],
                dependencies_complete=True,
                fingerprint="abc123",
            )
        ]
    )

    definition = parsed[0]
    assert definition.dependencies == [".infrahub.yml", "templates/config.j2"]
    assert definition.dependencies_complete is True
    assert definition.fingerprint == "abc123"


def test_unset_query_models_parse_as_an_empty_list() -> None:
    """``query_models`` is typed as a plain list, so a null has to be absorbed at parse time."""
    parsed = parse_artifact_definitions([_artifact_definition_edge(query_models=None)])

    assert parsed[0].query_models == []


def test_jinja2_transform_carries_its_template_path() -> None:
    parsed = parse_artifact_definitions([_artifact_definition_edge(transform_typename=InfrahubKind.TRANSFORMJINJA2)])

    definition = parsed[0]
    assert definition.transform_kind == InfrahubKind.TRANSFORMJINJA2
    assert definition.template_path == "templates/config.j2"
    # The Python-only fields keep their defaults rather than leaking from the other branch.
    assert (definition.class_name, definition.file_path) == ("", "")


def test_python_transform_carries_its_entry_point() -> None:
    parsed = parse_artifact_definitions([_artifact_definition_edge(transform_typename=InfrahubKind.TRANSFORMPYTHON)])

    definition = parsed[0]
    assert definition.transform_kind == InfrahubKind.TRANSFORMPYTHON
    assert (definition.class_name, definition.file_path) == ("CarTransform", "transforms/car.py")
    assert definition.convert_query_response is True
    # The Jinja2-only field keeps its default rather than leaking from the other branch.
    assert (definition.template_path,) == ("",)
