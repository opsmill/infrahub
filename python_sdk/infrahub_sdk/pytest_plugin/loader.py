from __future__ import annotations

from typing import Any, Iterable, Optional

import pytest
import yaml
from pytest import Item

from .exceptions import InvalidResourceConfigError
from .items import (
    InfrahubCheckIntegrationItem,
    InfrahubCheckSmokeItem,
    InfrahubCheckUnitProcessItem,
    InfrahubGraphQLQueryIntegrationItem,
    InfrahubGraphQLQuerySmokeItem,
    InfrahubItem,
    InfrahubJinja2TransformIntegrationItem,
    InfrahubJinja2TransformSmokeItem,
    InfrahubJinja2TransformUnitRenderItem,
    InfrahubPythonTransformIntegrationItem,
    InfrahubPythonTransformSmokeItem,
    InfrahubPythonTransformUnitProcessItem,
)
from .models import InfrahubTestFileV1, InfrahubTestGroup

MARKER_MAPPING = {
    "Check": pytest.mark.infrahub_check,
    "GraphQLQuery": pytest.mark.infrahub_graphql_query,
    "Jinja2Transform": pytest.mark.infrahub_jinja2_transform,
    "PythonTransform": pytest.mark.infrahub_python_transform,
}
CONFIG_MAPPING = {
    "Check": "get_check_definition",
    "GraphQLQuery": None,
    "Jinja2Transform": "get_jinja2_transform",
    "PythonTransform": "get_python_transform",
}

ITEMS_MAPPING = {
    "check-smoke": InfrahubCheckSmokeItem,
    "check-unit-process": InfrahubCheckUnitProcessItem,
    "check-integration": InfrahubCheckIntegrationItem,
    "graphql-query-smoke": InfrahubGraphQLQuerySmokeItem,
    "graphql-query-integration": InfrahubGraphQLQueryIntegrationItem,
    "jinja2-transform-smoke": InfrahubJinja2TransformSmokeItem,
    "jinja2-transform-unit-render": InfrahubJinja2TransformUnitRenderItem,
    "jinja2-transform-integration": InfrahubJinja2TransformIntegrationItem,
    "python-transform-smoke": InfrahubPythonTransformSmokeItem,
    "python-transform-unit-process": InfrahubPythonTransformUnitProcessItem,
    "python-transform-integration": InfrahubPythonTransformIntegrationItem,
}


class InfrahubYamlFile(pytest.File):
    def get_resource_config(self, group: InfrahubTestGroup) -> Optional[Any]:
        """Retrieve the resource configuration to apply to all tests in a group."""
        resource_config_function = CONFIG_MAPPING.get(group.resource)

        resource_config = None
        if resource_config_function is not None:
            func = getattr(self.session.infrahub_repo_config, resource_config_function)  # type:ignore[attr-defined]
            try:
                resource_config = func(group.resource_name)
            except KeyError:
                # Ignore error and just return None
                pass

        return resource_config

    def collect_group(self, group: InfrahubTestGroup) -> Iterable[Item]:
        """Collect all items for a group."""
        marker = MARKER_MAPPING[group.resource]
        resource_config = self.get_resource_config(group)

        for test in group.tests:
            item_class: type[pytest.Item] = ITEMS_MAPPING[test.spec.kind]  # type: ignore[assignment]
            item: InfrahubItem = item_class.from_parent(
                name=f"{marker.markname}__{group.resource_name}__{test.name}",
                parent=self,
                resource_name=group.resource_name,
                resource_config=resource_config,
                test=test,
            )  # type: ignore[assignment]

            # If item does not pass validation, mark it to be skipped
            try:
                item.validate_resource_config()
            except InvalidResourceConfigError as exc:
                item.add_marker(pytest.mark.skip(reason=str(exc)))

            item.add_marker(pytest.mark.infrahub)
            item.add_marker(marker)
            if "smoke" in test.spec.kind:
                item.add_marker(pytest.mark.infrahub_smoke)
            if "unit" in test.spec.kind:
                item.add_marker(pytest.mark.infrahub_unit)
            if "integration" in test.spec.kind:
                item.add_marker(pytest.mark.infrahub_integration)

            yield item

    def collect(self) -> Iterable[Item]:
        raw = yaml.safe_load(self.path.open(encoding="utf-8"))

        if "infrahub_tests" not in raw:
            return

        content = InfrahubTestFileV1(**raw)

        for test_group in content.infrahub_tests:
            yield from self.collect_group(test_group)
