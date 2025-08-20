from collections import defaultdict
from typing import Any

from pydantic import BaseModel, Field

from infrahub.core.constants import DiffAction
from infrahub.core.diff.model.path import NodeIdentifier
from infrahub.core.query.utils import filter_and, filter_or


class IncExclFilterOptions(BaseModel):
    includes: list[str] = Field(default_factory=list)
    excludes: list[str] = Field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        if not self.includes and not self.excludes:
            return True
        return False


class IncExclActionFilterOptions(BaseModel):
    includes: set[DiffAction] = Field(default_factory=set)
    excludes: set[DiffAction] = Field(default_factory=set)

    @property
    def is_empty(self) -> bool:
        if not self.includes and not self.excludes:
            return True
        return False


class EnrichedDiffQueryFilters(BaseModel):
    ids: list[str] = Field(default_factory=list)
    kind: IncExclFilterOptions = IncExclFilterOptions()
    identifiers: list[NodeIdentifier] = Field(default_factory=list)
    namespace: IncExclFilterOptions = IncExclFilterOptions()
    status: IncExclActionFilterOptions = IncExclActionFilterOptions()
    only_conflicted: bool = Field(default=False)

    @property
    def is_empty(self) -> bool:
        if (
            not self.ids
            and not self.identifiers
            and self.only_conflicted is False
            and self.kind.is_empty
            and self.namespace.is_empty
            and self.status.is_empty
        ):
            return True
        return False

    def generate(self) -> tuple[str, dict]:
        default_filter = ""

        params: dict[str, Any] = {}

        if self.ids:
            params["ids"] = self.ids
            return "diff_node.uuid in $ids", params

        if self.identifiers:
            params["ids"] = [n.uuid for n in self.identifiers]
            id_kind_map: dict[str, list[str]] = defaultdict(list)
            for node_identifier in self.identifiers:
                id_kind_map[node_identifier.uuid].append(node_identifier.kind)
            params["id_kind_map"] = id_kind_map
            return "diff_node.uuid in $ids AND diff_node.kind IN $id_kind_map[diff_node.uuid]", params

        filters_list = []

        if self.is_empty:
            return default_filter, params

        # KIND, Pass the list directly
        if not self.kind.is_empty:
            filter_kind = []
            if self.kind.includes:
                filter_kind.append("diff_node.kind IN $filter_kind_includes")
                params["filter_kind_includes"] = self.kind.includes

            if self.kind.excludes:
                filter_kind.append("NOT(diff_node.kind IN $filter_kind_excludes)")
                params["filter_kind_excludes"] = self.kind.excludes

            filters_list.append(filter_and(filter_kind))

        # NAMESPACE, match on the start of the kind
        if not self.namespace.is_empty:
            filter_namespace = []
            if self.namespace.includes:
                filter_namespace.append(
                    filter_or([f'diff_node.kind STARTS WITH "{ns}"' for ns in self.namespace.includes])
                )
            if self.namespace.excludes:
                filter_namespace.append(
                    filter_and([f'NOT(diff_node.kind STARTS WITH "{ns}")' for ns in self.namespace.excludes])
                )
            filters_list.append(filter_and(filter_namespace))

        # STATUS, Pass the list directly
        if not self.status.is_empty:
            filter_action = []
            if self.status.includes:
                filter_action.append("diff_node.action IN $filter_status_includes")
                params["filter_status_includes"] = [str(item.value).lower() for item in self.status.includes]

            if self.status.excludes:
                filter_action.append("NOT(diff_node.action IN $filter_status_excludes)")
                params["filter_status_excludes"] = [str(item.value).lower() for item in self.status.excludes]

            filters_list.append(filter_and(filter_action))

        # ONLY NODES WITH CONFLICTS
        if self.only_conflicted is True:
            filters_list.append("diff_node.contains_conflict = TRUE")

        return filter_and(filters_list), params
