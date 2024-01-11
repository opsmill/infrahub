from __future__ import annotations

import warnings
from typing import Iterable

import pytest
import yaml
from pytest import Item

from .items import InfrahubPythonTransformUnitProcessItem, InfrahubRFileUnitRenderItem
from .models import InfrahubTestFileV1, InfrahubTestResource

MARKER_MAPPING = {"RFile": pytest.mark.infrahub_rfile, "PythonTransform": pytest.mark.infrahub_python_transform}

ITEMS_MAPPING = {
    "rfile-unit-render": InfrahubRFileUnitRenderItem,
    "python-transform-unit-process": InfrahubPythonTransformUnitProcessItem,
}


class InfrahubYamlFile(pytest.File):
    def collect(self) -> Iterable[Item]:
        raw = yaml.safe_load(self.path.open(encoding="utf-8"))

        if "infrahub_tests" not in raw:
            return

        content = InfrahubTestFileV1(**raw)

        for test_group in content.infrahub_tests:
            if test_group.resource == InfrahubTestResource.RFILE.value:
                marker = pytest.mark.infrahub_rfile(name=test_group.resource_name)
                try:
                    resource_config = self.session.infrahub_repo_config.get_rfile(test_group.resource_name)  # type: ignore[attr-defined]
                except KeyError:
                    warnings.warn(
                        Warning(f"Unable to find the rfile {test_group.resource_name!r} in the repository config file.")
                    )
                    continue

            if test_group.resource == InfrahubTestResource.PYTHON_TRANSFORM.value:
                marker = pytest.mark.infrahub_python_transform(name=test_group.resource_name)
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
