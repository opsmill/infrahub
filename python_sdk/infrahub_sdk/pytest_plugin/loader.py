from __future__ import annotations

import warnings
from typing import Iterable

import pytest
import yaml
from pytest import Item

from .items import (
    InfrahubCheckIntegrationItem,
    InfrahubCheckUnitProcessItem,
    InfrahubGraphqlQueryIntegrationItem,
    InfrahubJinja2TransformIntegrationItem,
    InfrahubJinja2TransformUnitRenderItem,
    InfrahubPythonTransformIntegrationItem,
    InfrahubPythonTransformUnitProcessItem,
)
from .models import InfrahubTestFileV1, InfrahubTestResource

MARKER_MAPPING = {
    "Check": pytest.mark.infrahub_check,
    "GraphqlQuery": pytest.mark.infrahub_graphql_query,
    "Jinja2Transform": pytest.mark.infrahub_jinja2_transform,
    "PythonTransform": pytest.mark.infrahub_python_transform,
}

ITEMS_MAPPING = {
    "check-unit-process": InfrahubCheckUnitProcessItem,
    "check-integration": InfrahubCheckIntegrationItem,
    "graphql-query-integration": InfrahubGraphqlQueryIntegrationItem,
    "jinja2-transform-unit-render": InfrahubJinja2TransformUnitRenderItem,
    "jinja2-transform-integration": InfrahubJinja2TransformIntegrationItem,
    "python-transform-unit-process": InfrahubPythonTransformUnitProcessItem,
    "python-transform-integration": InfrahubPythonTransformIntegrationItem,
}


class InfrahubYamlFile(pytest.File):
    def collect(self) -> Iterable[Item]:
        raw = yaml.safe_load(self.path.open(encoding="utf-8"))

        if "infrahub_tests" not in raw:
            return

        content = InfrahubTestFileV1(**raw)

        for test_group in content.infrahub_tests:
            if test_group.resource == InfrahubTestResource.CHECK.value:
                marker = MARKER_MAPPING[test_group.resource](name=test_group.resource_name)
                try:
                    resource_config = self.session.infrahub_repo_config.get_check_definition(test_group.resource_name)  # type: ignore[attr-defined]
                except KeyError:
                    warnings.warn(
                        Warning(
                            f"Unable to find check definition {test_group.resource_name!r} in the repository config file."
                        )
                    )
                    continue

            if test_group.resource == InfrahubTestResource.GRAPHQL_QUERY.value:
                marker = MARKER_MAPPING[test_group.resource](name=test_group.resource_name)
                resource_config = None

            if test_group.resource == InfrahubTestResource.JINJA2_TRANSFORM.value:
                marker = MARKER_MAPPING[test_group.resource](name=test_group.resource_name)
                try:
                    resource_config = self.session.infrahub_repo_config.get_jinja2_transform(test_group.resource_name)  # type: ignore[attr-defined]
                except KeyError:
                    warnings.warn(
                        Warning(
                            f"Unable to find jinja2 transform {test_group.resource_name!r} in the repository config file."
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
                            f"Unable to find python transform {test_group.resource_name!r} in the repository config file."
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
                if "unit" in test.spec.kind:
                    item.add_marker(pytest.mark.infrahub_unit)
                if "integration" in test.spec.kind:
                    item.add_marker(pytest.mark.infrahub_integraton)

                yield item
