from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from prefect.events.schemas.automations import Automation  # noqa: TC002
from pydantic import BaseModel, Field
from typing_extensions import Self

if TYPE_CHECKING:
    from uuid import UUID

    from infrahub_sdk.data import RepositoryData

    from infrahub.core.schema.schema_branch_computed import PythonDefinition


class ComputedAttributeAutomations(BaseModel):
    data: dict[str, dict[str, Automation]] = Field(default_factory=lambda: defaultdict(dict))

    @classmethod
    def from_prefect(cls, automations: list[Automation], prefix: str = "") -> Self:
        obj = cls()
        for automation in automations:
            if not automation.name.startswith(prefix):
                continue

            name_split = automation.name.split("::")
            if len(name_split) != 3:
                continue

            scope = name_split[1]
            identifier = name_split[2]

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

    def return_obsolete(self, keep: list[UUID]) -> list[UUID]:
        return [automation_id for automation_id in self.all_automation_ids if automation_id not in keep]

    @property
    def all_automation_ids(self) -> list[UUID]:
        automation_ids: list[UUID] = []
        for identifier in self.data.values():
            for automation in identifier.values():
                automation_ids.append(automation.id)
        return automation_ids


@dataclass
class PythonTransformComputedAttribute:
    name: str
    repository_id: str
    repository_name: str
    repository_kind: str
    query_name: str
    query_models: list[str]
    computed_attribute: PythonDefinition
    default_schema: bool
    branch_commit: dict[str, str] = field(default_factory=dict)

    def populate_branch_commit(self, repository_data: RepositoryData | None = None) -> None:
        if repository_data:
            for branch, commit in repository_data.branches.items():
                self.branch_commit[branch] = commit


@dataclass
class PythonTransformTarget:
    kind: str
    object_id: str
