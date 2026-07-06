from __future__ import annotations

from infrahub.git.fingerprint.composer import ArtifactDefinitionFingerprintInput
from infrahub.git.fingerprint.registry import FingerprintKind, FingerprintRegistry
from tests.unit.git.fingerprint.conftest import build_composer


def _input(**overrides: object) -> ArtifactDefinitionFingerprintInput:
    defaults: dict[str, object] = {
        "name": "report",
        "transformation_name": "t",
        "parameters": {"name": "name__value"},
        "content_type": "text/plain",
        "artifact_name": "car-owner",
        "target_group_id": "group-1",
    }
    defaults.update(overrides)
    return ArtifactDefinitionFingerprintInput(**defaults)  # type: ignore[arg-type]


def _digest(*, transformation_fingerprint: str = "transform-fp", **overrides: object) -> str:
    registry = FingerprintRegistry()
    registry.register(kind=FingerprintKind.TRANSFORMATION, name="t", fingerprint=transformation_fingerprint)
    return build_composer(registry=registry).compose_artifact_definition(_input(**overrides))


def test_incorporates_transformation_fingerprint() -> None:
    assert _digest(transformation_fingerprint="a") != _digest(transformation_fingerprint="b")


def test_changes_on_each_hashed_field() -> None:
    base = _digest()
    assert base != _digest(parameters={"name": "other"})
    assert base != _digest(content_type="application/json")
    assert base != _digest(artifact_name="renamed")
    assert base != _digest(target_group_id="group-2")


def test_parameters_key_ordering_is_irrelevant() -> None:
    first = _digest(parameters={"a": "1", "b": "2"})
    second = _digest(parameters={"b": "2", "a": "1"})
    assert first == second
