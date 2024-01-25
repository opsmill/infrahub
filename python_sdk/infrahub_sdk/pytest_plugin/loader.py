from __future__ import annotations

import warnings
from typing import Iterable

import pytest
import yaml
from pytest import Item

from .items import InfrahubJinja2TransformUnitRenderItem, InfrahubPythonTransformUnitProcessItem
from .models import InfrahubTestFileV1, InfrahubTestResource

MARKER_MAPPING = {
    "Jinja2Transform": pytest.mark.infrahub_jinja2_transform,
    "PythonTransform": pytest.mark.infrahub_python_transform,
}

ITEMS_MAPPING = {
    "jinja2-transform-unit-render": InfrahubJinja2TransformUnitRenderItem,
    "python-transform-unit-process": InfrahubPythonTransformUnitProcessItem,
}


class InfrahubYamlFile(pytest.File):
    def collect(self) -> Iterable[Item]:
        raw = yaml.safe_load(self.path.open(encoding="utf-8"))

        if "infrahub_tests" not in raw:
            return

        content = InfrahubTestFileV1(**raw)

        for test_group in content.infrahub_tests:
            if test_group.resource == InfrahubTestResource.JINJA2_TRANSFORM.value:
                marker = MARKER_MAPPING[test_group.resource](name=test_group.resource_name)
                try:
                    resource_config = self.session.infrahub_repo_config.get_jinja2_transform(test_group.resource_name)  # type: ignore[attr-defined]
                except KeyError:
                    warnings.warn(
                        Warning(
                            f"Unable to find the jinja2 transform {test_group.resource_name!r} in the repository config file."
                        )
                    )
                    continue

            if test_group.resource == InfrahubTestResource.PYTHON_TRANSFORM.value:
                marker = MARKER_MAPPING[test_group.resource](name=test_group.resource_name)
                try:
                    resource_config = self.session.infrahub_repo_config.get_python_transform(test_group.resource_name)  # type: ignore[attr-defined]
                except KeyError:
                    warnings.warn(
                        Warning(
                            f"Unable to find the python transform {test_group.resource_name!r} in the repository config file."
                        )
                    )
                    continue

            for test in test_group.tests:
                name = f"{test_group.resource.value.lower()}__{test_group.resource_name}__{test.name}"

                item_class: type[pytest.Item] = ITEMS_MAPPING[test.spec.kind]  # type: ignore[assignment]
                item: pytest.Item = item_class.from_parent(
                    name=name,
                    parent=self,
                    resource_name=test_group.resource_name,
                    resource_config=resource_config,
                    test=test,
                )
                item.add_marker(marker)
                yield item
