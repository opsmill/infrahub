from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

from prefect.events.schemas.automations import Automation  # noqa: TCH002
from pydantic import BaseModel, Field
from typing_extensions import Self

from .constants import AUTOMATION_NAME_PREFIX

if TYPE_CHECKING:
    from infrahub.core.schema.schema_branch_computed import PythonDefinition


class ComputedAttributeAutomations(BaseModel):
    data: dict[str, dict[str, Automation]] = Field(default_factory=lambda: defaultdict(dict))

    @classmethod
    def from_prefect(cls, automations: list[Automation]) -> Self:
        obj = cls()
        for automation in automations:
            if not automation.name.startswith(AUTOMATION_NAME_PREFIX):
                continue

            name_split = automation.name.split("::")
            if len(name_split) != 3:
                continue

            identifier = name_split[1]
            scope = name_split[2]

            obj.data[identifier][scope] = automation

        return obj

    def get(self, identifier: str, scope: str) -> Automation:
        if identifier in self.data and scope in self.data[identifier]:
            return self.data[identifier][scope]
        raise KeyError(f"Unable to find an automation for {identifier} {scope}")

    def has(self, identifier: str, scope: str) -> bool:
        if identifier in self.data and scope in self.data[identifier]:
            return True
        return False


@dataclass
class PythonTransformComputedAttribute:
    name: str
    repository_id: str
    repository_name: str
    repository_kind: str
    query_name: str
    query_models: list[str]
    computed_attribute: PythonDefinition
