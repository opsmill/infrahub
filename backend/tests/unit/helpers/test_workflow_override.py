from collections.abc import Iterator

import pytest
from fast_depends import Provider

from infrahub import config
from infrahub.workers.dependencies import build_workflow
from tests.adapters.workflow import WorkflowRecorder
from tests.helpers.workflow_override import override_workflow


@pytest.fixture
def provider() -> Provider:
    return Provider()


@pytest.fixture(autouse=True)
def no_global_override() -> Iterator[None]:
    original = config.OVERRIDE.workflow
    config.OVERRIDE.workflow = None
    yield
    config.OVERRIDE.workflow = original


def resolved(provider: Provider) -> object:
    return provider.overrides[build_workflow].call()


def test_override_is_removed_when_there_was_none_before(provider: Provider) -> None:
    recorder = WorkflowRecorder()

    with override_workflow(recorder, dependency_provider=provider) as active:
        assert active is recorder
        assert config.OVERRIDE.workflow is recorder
        assert resolved(provider) is recorder

    assert config.OVERRIDE.workflow is None
    assert build_workflow not in provider.overrides


def test_nested_override_gives_the_outer_one_back(provider: Provider) -> None:
    outer = WorkflowRecorder()
    inner = WorkflowRecorder()

    with override_workflow(outer, dependency_provider=provider):
        with override_workflow(inner, dependency_provider=provider):
            assert resolved(provider) is inner
            assert config.OVERRIDE.workflow is inner

        assert resolved(provider) is outer
        assert config.OVERRIDE.workflow is outer


def test_exception_inside_the_block_still_restores(provider: Provider) -> None:
    with pytest.raises(RuntimeError), override_workflow(WorkflowRecorder(), dependency_provider=provider):
        raise RuntimeError("boom")

    assert config.OVERRIDE.workflow is None
    assert build_workflow not in provider.overrides
