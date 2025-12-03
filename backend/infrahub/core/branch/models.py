from __future__ import annotations

import inspect
import re
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional, Self, Union, cast
from uuid import UUID

import ujson
from infrahub_sdk.uuidt import UUIDT
from neo4j.graph import Node as Neo4jNode
from pydantic import BaseModel, Field, field_validator

from infrahub.core.branch.enums import BranchStatus
from infrahub.core.constants import GLOBAL_BRANCH_NAME, NULL_VALUE, SYSTEM_USER_ID
from infrahub.core.graph import GRAPH_VERSION
from infrahub.core.models import SchemaBranchHash  # noqa: TC001
from infrahub.core.node.standard import StandardNode
from infrahub.core.query import Query, QueryType
from infrahub.core.query.branch import (
    BranchNodeGetListQuery,
    DeleteBranchRelationshipsQuery,
    GetAllBranchInternalRelationshipQuery,
    InfrahubBranchNodeGetListQuery,
    RebaseBranchDeleteRelationshipQuery,
    RebaseBranchUpdateRelationshipQuery,
)
from infrahub.core.registry import registry
from infrahub.core.timestamp import Timestamp
from infrahub.exceptions import BranchNotFoundError, InitializationError, ValidationError

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class Branch(StandardNode):
    name: str = Field(
        max_length=250, min_length=3, description="Name of the branch (git ref standard)", validate_default=True
    )
    status: BranchStatus = BranchStatus.OPEN
    description: str = ""
    origin_branch: str = "main"
    branched_from: Optional[str] = Field(default=None, validate_default=True)
    hierarchy_level: int = 2
    is_default: bool = False
    is_global: bool = False
    is_protected: bool = False
    sync_with_git: bool = Field(
        default=True,
        description="Indicate if the branch should be extended to Git and if Infrahub should merge the branch in Git as part of a proposed change",
    )
    is_isolated: bool = True
    schema_changed_at: Optional[str] = None
    schema_hash: Optional[SchemaBranchHash] = None
    graph_version: int | None = None

    _exclude_attrs: list[str] = ["id", "uuid", "owner"]

    @field_validator("name", mode="before")
    @classmethod
    def validate_branch_name(cls, value: str) -> str:
        checks = [
            (r".*/\.", "/."),
            (r"\.\.", ".."),
            (r"^/", "starts with /"),
            (r"//", "//"),
            (r"@{", "@{"),
            (r"\\", "backslash (\\)"),
            (r"[\000-\037\177 ~^:?*[]", "disallowed ASCII characters/patterns"),
            (r"\.lock$", "ends with .lock"),
            (r"/$", "ends with /"),
            (r"\.$", "ends with ."),
        ]

        offending_patterns = []

        for pattern, description in checks:
            if re.search(pattern, value):
                offending_patterns.append(description)

        if value == GLOBAL_BRANCH_NAME:
            return value  # this is the only allowed exception

        if offending_patterns:
            error_text = ", ".join(offending_patterns)
            raise ValidationError(f"Branch name contains invalid patterns or characters: {error_text}")

        return value

    @field_validator("branched_from", mode="before")
    @classmethod
    def set_branched_from(cls, value: str) -> str:
        return Timestamp(value).to_string()

    def get_branched_from(self) -> str:
        if not self.branched_from:
            raise RuntimeError(f"branched_from not set for branch {self.name}")
        return self.branched_from

    @field_validator("created_at", mode="before")
    @classmethod
    def set_created_at(cls, value: str) -> str:
        return Timestamp(value).to_string()

    def get_created_at(self) -> str:
        if not self.created_at:
            raise RuntimeError(f"created_at not set for branch {self.name}")
        return self.created_at

    @property
    def active_schema_hash(self) -> SchemaBranchHash:
        if self.schema_hash:
            return self.schema_hash

        raise InitializationError("The schema_hash has not been loaded for this branch")

    @property
    def has_schema_changes(self) -> bool:
        if not self.schema_hash:
            return False

        origin_branch = self.get_origin_branch()
        if not origin_branch or not origin_branch.schema_hash:
            return False

        if self.schema_hash.main != origin_branch.schema_hash.main:
            return True

        return False

    def update_schema_hash(self, at: Timestamp | str | None = None) -> bool:
        latest_schema = registry.schema.get_schema_branch(name=self.name)
        new_hash = latest_schema.get_hash_full()
        if self.schema_hash and new_hash.main == self.schema_hash.main:
            return False

        self.schema_changed_at = Timestamp(at).to_string()
        self.schema_hash = new_hash
        return True

    @classmethod
    async def get_by_name(cls, name: str, db: InfrahubDatabase, ignore_deleting: bool = True) -> Branch:
        query = """
        MATCH (n:Branch)
        WHERE n.name = $name
        AND NOT n.status IN $ignore_statuses
        RETURN n
        """

        params: dict[str, Any] = {"name": name}
        params["ignore_statuses"] = []
        if ignore_deleting:
            params["ignore_statuses"].append(BranchStatus.DELETING.value)

        results = await db.execute_query(query=query, params=params, name="branch_get_by_name", type=QueryType.READ)

        if len(results) == 0:
            raise BranchNotFoundError(identifier=name)

        return cls.from_db(results[0].values()[0])

    @classmethod
    async def get_list(
        cls,
        db: InfrahubDatabase,
        limit: int = 1000,
        ids: list[str] | None = None,
        name: str | None = None,
        **kwargs: Any,
    ) -> list[Self]:
        query: Query = await BranchNodeGetListQuery.init(
            db=db, node_class=cls, ids=ids, node_name=name, limit=limit, **kwargs
        )
        await query.execute(db=db)

        return [cls.from_db(node=cast(Neo4jNode, result.get("n"))) for result in query.get_results()]

    @classmethod
    async def get_list_count(
        cls,
        db: InfrahubDatabase,
        limit: int = 1000,
        ids: list[str] | None = None,
        name: str | None = None,
        **kwargs: Any,
    ) -> int:
        query: Query = await BranchNodeGetListQuery.init(
            db=db, node_class=cls, ids=ids, node_name=name, limit=limit, exclude_global=True, **kwargs
        )
        return await query.count(db=db)

    @classmethod
    def isinstance(cls, obj: Any) -> bool:
        return isinstance(obj, cls)

    def get_origin_branch(self) -> Optional[Branch]:
        """Return the branch Object of the origin_branch."""
        if not self.origin_branch or self.origin_branch == self.name:
            return None

        return registry.get_branch_from_registry(branch=self.origin_branch)

    def get_branches_in_scope(self) -> list[str]:
        """Return the list of all the branches that are constituing this branch.

        For now, either a branch is the default branch or it must inherit from it so we can only have 2 values at best
        But the idea is that it will change at some point in a future version.
        """
        default_branch = registry.default_branch
        if self.name == default_branch:
            return [self.name]

        return [default_branch, self.name]

    def get_branches_and_times_to_query(self, at: Optional[Timestamp] = None) -> dict[frozenset, str]:
        """Return all the names of the branches that are constituing this branch with the associated times excluding the global branch"""

        at = Timestamp(at)

        if self.is_default:
            return {frozenset([self.name]): at.to_string()}

        time_default_branch = at

        # If the branch is isolated, and if the time requested is after the creation of the branch
        if self.is_isolated and at > Timestamp(self.branched_from):
            time_default_branch = Timestamp(self.branched_from)

        return {
            frozenset([self.origin_branch]): time_default_branch.to_string(),
            frozenset([self.name]): at.to_string(),
        }

    def get_branches_and_times_to_query_global(
        self,
        at: Optional[Timestamp] = None,
        is_isolated: bool = True,
    ) -> dict[frozenset, str]:
        """Return all the names of the branches that are constituting this branch with the associated times."""

        at = Timestamp(at)

        if self.is_default:
            return {frozenset((GLOBAL_BRANCH_NAME, self.name)): at.to_string()}

        time_default_branch = at

        # If the branch is isolated, and if the time requested is after the creation of the branch
        if self.is_isolated and is_isolated and at > Timestamp(self.branched_from):
            time_default_branch = Timestamp(self.branched_from)

        return {
            frozenset((GLOBAL_BRANCH_NAME, self.origin_branch)): time_default_branch.to_string(),
            frozenset((GLOBAL_BRANCH_NAME, self.name)): at.to_string(),
        }

    def get_branches_and_times_for_range(
        self, start_time: Timestamp, end_time: Timestamp
    ) -> tuple[dict[str, str], dict[str, str]]:
        """Return the names of the branches that are constituing this branch with the start and end times."""

        start = {}
        end = {}

        time_branched_from = Timestamp(self.branched_from)
        time_created_at = Timestamp(self.created_at)

        # Ensure start time is not older than the creation of the branch (time_created_at)
        time_query_start = start_time
        if start_time < time_created_at:
            time_query_start = time_created_at

        start[self.name] = time_query_start.to_string()

        # START
        if not self.is_default and time_query_start <= time_branched_from:
            start[self.origin_branch] = time_branched_from.to_string()
        elif not self.is_default and time_query_start > time_branched_from:
            start[self.origin_branch] = time_query_start.to_string()

        # END
        end[self.name] = end_time.to_string()
        if not self.is_default:
            end[self.origin_branch] = end_time.to_string()

        return start, end

    @field_validator("graph_version", mode="before")
    @classmethod
    def set_graph_version(cls, value: int) -> int:  # noqa: ARG003
        return GRAPH_VERSION

    async def delete(self, db: InfrahubDatabase) -> None:
        if self.is_default:
            raise ValidationError(f"Unable to delete {self.name} it is the default branch.")
        if self.is_global:
            raise ValidationError(f"Unable to delete {self.name} this is an internal branch.")

        self.status = BranchStatus.DELETING
        await self.save(db=db)

        query = await DeleteBranchRelationshipsQuery.init(db=db, branch_name=self.name)
        await query.execute(db=db)
        await super().delete(db=db)

    def get_query_filter_relationships(
        self, rel_labels: list, at: Optional[Timestamp] = None, include_outside_parentheses: bool = False
    ) -> tuple[list, dict]:
        """
        Generate a CYPHER Query filter based on a list of relationships to query a part of the graph at a specific time and on a specific branch.
        """

        filters = []
        params: dict[str, Any] = {}

        if not isinstance(rel_labels, list):
            raise TypeError(f"rel_labels must be a list, not a {type(rel_labels)}")

        at = Timestamp(at)
        branches_times = self.get_branches_and_times_to_query_global(at=at)

        for idx, (branch_name, time_to_query) in enumerate(branches_times.items()):
            params[f"branch{idx}"] = list(branch_name)
            params[f"time{idx}"] = time_to_query

        for rel in rel_labels:
            filters_per_rel = []
            for idx in range(len(branches_times)):
                filters_per_rel.append(
                    f"({rel}.branch IN $branch{idx} AND {rel}.from <= $time{idx} AND {rel}.to IS NULL)"
                )
                filters_per_rel.append(
                    f"({rel}.branch IN $branch{idx} AND {rel}.from <= $time{idx} AND {rel}.to >= $time{idx})"
                )

            if not include_outside_parentheses:
                filters.append("\n OR ".join(filters_per_rel))

            filters.append("(" + "\n OR ".join(filters_per_rel) + ")")

        return filters, params

    def get_query_filter_path(
        self,
        at: Optional[Union[Timestamp, str]] = None,
        is_isolated: bool = True,
        branch_agnostic: bool = False,
        variable_name: str = "r",
        params_prefix: str = "",
    ) -> tuple[str, dict]:
        """
        Generate a CYPHER Query filter based on a path to query a part of the graph at a specific time and on a specific branch.

        Examples:
            >>> rels_filter, rels_params = self.branch.get_query_filter_path(at=self.at)
            >>> self.params.update(rels_params)
            >>> query += "\n WHERE all(r IN relationships(p) WHERE %s)" % rels_filter

            There is a currently an assumption that the relationship in the path will be named 'r'
        """
        pp = params_prefix
        params: dict[str, Any] = {}
        at = Timestamp(at)
        at_str = at.to_string()
        if branch_agnostic:
            filter_str = f"{variable_name}.from <= ${pp}time1 AND ({variable_name}.to IS NULL or {variable_name}.to >= ${pp}time1)"
            params[f"{pp}time1"] = at_str
            return filter_str, params

        branches_times = self.get_branches_and_times_to_query_global(at=at, is_isolated=is_isolated)

        for idx, (branch_name, time_to_query) in enumerate(branches_times.items()):
            params[f"{pp}branch{idx}"] = list(branch_name)
            params[f"{pp}time{idx}"] = time_to_query

        filters = []
        for idx in range(len(branches_times)):
            filters.append(
                f"({variable_name}.branch IN ${pp}branch{idx} AND {variable_name}.from <= ${pp}time{idx} AND {variable_name}.to IS NULL)"
            )
            filters.append(
                f"({variable_name}.branch IN ${pp}branch{idx} AND {variable_name}.from <= ${pp}time{idx} AND {variable_name}.to >= ${pp}time{idx})"
            )

        filter_str = "(" + "\n OR ".join(filters) + ")"

        return filter_str, params

    def get_query_filter_relationships_range(
        self,
        rel_labels: list,
        start_time: Timestamp,
        end_time: Timestamp,
        include_outside_parentheses: bool = False,
        include_global: bool = False,
    ) -> tuple[list, dict]:
        """Generate a CYPHER Query filter based on a list of relationships to query a range of values in the graph.
        The goal is to return all the values that are valid during this timerange.
        """

        filters = []
        params = {}

        if not isinstance(rel_labels, list):
            raise TypeError(f"rel_labels must be a list, not a {type(rel_labels)}")

        start_time = Timestamp(start_time)
        end_time = Timestamp(end_time)

        if include_global:
            branches_times = self.get_branches_and_times_to_query_global(at=start_time)
        else:
            branches_times = self.get_branches_and_times_to_query(at=start_time)

        params["branches"] = list({branch for branches in branches_times for branch in branches})
        params["start_time"] = start_time.to_string()
        params["end_time"] = end_time.to_string()

        for rel in rel_labels:
            filters_per_rel = [
                f"({rel}.branch IN $branches AND {rel}.from <= $end_time AND {rel}.to IS NULL)",
                f"({rel}.branch IN $branches AND ({rel}.from <= $end_time OR ({rel}.to >= $start_time AND {rel}.to <= $end_time)))",
            ]

            if not include_outside_parentheses:
                filters.append("\n OR ".join(filters_per_rel))

            filters.append("(" + "\n OR ".join(filters_per_rel) + ")")

        return filters, params

    def get_query_filter_relationships_diff(
        self, rel_labels: list, diff_from: Timestamp, diff_to: Timestamp
    ) -> tuple[list, dict]:
        """
        Generate a CYPHER Query filter to query all events that are applicable to a given branch based
        - The time when the branch as created
        - The branched_from time of the branch
        - The diff_to and diff_from time as provided
        """

        if not isinstance(rel_labels, list):
            raise TypeError(f"rel_labels must be a list, not a {type(rel_labels)}")

        start_times, end_times = self.get_branches_and_times_for_range(start_time=diff_from, end_time=diff_to)

        filters = []
        params = {}

        for idx, branch_name in enumerate(start_times.keys()):
            params[f"branch{idx}"] = branch_name
            params[f"start_time{idx}"] = start_times[branch_name]
            params[f"end_time{idx}"] = end_times[branch_name]

        for rel in rel_labels:
            filters_per_rel = []
            for idx in range(len(start_times)):
                filters_per_rel.extend(
                    [
                        f"""({rel}.branch = $branch{idx}
                             AND {rel}.from >= $start_time{idx}
                             AND {rel}.from <= $end_time{idx}
                             AND ( r2.to is NULL or r2.to >= $end_time{idx}))""",
                        f"""({rel}.branch = $branch{idx} AND {rel}.from >= $start_time{idx}
                            AND {rel}.to <= $start_time{idx})""",
                    ]
                )

            filters.append("(" + "\n OR ".join(filters_per_rel) + ")")

        return filters, params

    def get_query_filter_range(self, rel_label: list, start_time: Timestamp, end_time: Timestamp) -> tuple[list, dict]:
        """
        Generate a CYPHER Query filter to query a range of values in the graph between start_time and end_time."""

        filters = []
        params = {}

        start_time = Timestamp(start_time)
        end_time = Timestamp(end_time)

        params["branches"] = self.get_branches_in_scope()
        params["start_time"] = start_time.to_string()
        params["end_time"] = end_time.to_string()

        filters_per_rel = [
            f"""({rel_label}.branch IN $branches AND {rel_label}.from >= $start_time
                 AND {rel_label}.from <= $end_time AND {rel_label}.to IS NULL)""",
            f"""({rel_label}.branch IN $branches AND (({rel_label}.from >= $start_time
                 AND {rel_label}.from <= $end_time) OR ({rel_label}.to >= $start_time
                 AND {rel_label}.to <= $end_time)))""",
        ]

        filters.append("(" + "\n OR ".join(filters_per_rel) + ")")

        return filters, params

    async def rebase(self, db: InfrahubDatabase, at: Optional[Union[str, Timestamp]] = None) -> None:
        """Rebase the current Branch with its origin branch"""

        at = Timestamp(at)

        # Find all relationships with the name of the branch
        # Delete all relationship that have a to date defined in the past
        # Update the from time on all other relationships
        # If conflict is set, ignore the one with Drop

        await self.rebase_graph(db=db, at=at)

        # FIXME, we must ensure that there is no conflict before rebasing a branch
        #   Otherwise we could endup with a complicated situation
        self.branched_from = at.to_string()
        self.status = BranchStatus.OPEN
        await self.save(db=db)

        # Update the branch in the registry after the rebase
        registry.branch[self.name] = self

    async def rebase_graph(self, db: InfrahubDatabase, at: Optional[Timestamp] = None) -> None:
        at = Timestamp(at)

        query = await GetAllBranchInternalRelationshipQuery.init(db=db, branch=self)
        await query.execute(db=db)

        rels_to_delete = []
        rels_to_update = []
        for result in query.get_results():
            element_id = result.get("r").element_id

            conflict_status = result.get("r").get("conflict", None)
            if conflict_status and conflict_status == "drop":
                rels_to_delete.append(element_id)
                continue

            time_to_str = result.get("r").get("to", None)
            time_from_str = result.get("r").get("from")
            time_from = Timestamp(time_from_str)

            if not time_to_str and time_from_str and time_from <= at:
                rels_to_update.append(element_id)
                continue

            if not time_to_str and time_from_str and time_from > at:
                rels_to_delete.append(element_id)
                continue

            time_to = Timestamp(time_to_str)
            if time_to < at:
                rels_to_delete.append(element_id)
                continue

            rels_to_update.append(element_id)

        update_query = await RebaseBranchUpdateRelationshipQuery.init(db=db, ids=rels_to_update, at=at)
        await update_query.execute(db=db)

        delete_query = await RebaseBranchDeleteRelationshipQuery.init(db=db, ids=rels_to_delete, at=at)
        await delete_query.execute(db=db)


class FieldMetadata(BaseModel):
    updated_at: datetime | None = None
    updated_by: str | None = None


class NameValueField(FieldMetadata):
    value: str = Field(
        max_length=250, min_length=3, description="Name of the branch (git ref standard)", validate_default=True
    )


class DescriptionValueField(FieldMetadata):
    value: str = ""


class StatusValueField(FieldMetadata):
    value: BranchStatus = BranchStatus.OPEN


class OriginBranchValueField(FieldMetadata):
    value: str = "main"


class OptionalDatetimeValueField(FieldMetadata):
    value: datetime | None = Field(default=None, validate_default=True)


class HierarchyLevelValueField(FieldMetadata):
    value: int = 2


class BooleanValueField(FieldMetadata):
    value: bool = False


class SyncWithGitValueField(BooleanValueField):
    value: bool = Field(
        default=True,
        description="Indicate if the branch should be extended to Git and if Infrahub should merge the branch in Git as part of a proposed change",
    )


class TrueBooleanValueField(BooleanValueField):
    value: bool = True


class SchemaBranchHashValueField(FieldMetadata):
    value: SchemaBranchHash | None = None


class OptionalIntValueField(FieldMetadata):
    value: int | None = None


class InfrahubBranch(Branch):
    name: NameValueField
    description: DescriptionValueField
    status: StatusValueField
    origin_branch: OriginBranchValueField
    branched_from: OptionalDatetimeValueField
    hierarchy_level: HierarchyLevelValueField
    created_at: datetime | None
    created_by: str | None
    updated_at: datetime | None
    updated_by: str | None
    is_default: BooleanValueField
    is_global: BooleanValueField
    is_protected: BooleanValueField
    sync_with_git: SyncWithGitValueField
    is_isolated: TrueBooleanValueField
    schema_changed_at: OptionalDatetimeValueField
    schema_hash: SchemaBranchHashValueField
    graph_version: OptionalIntValueField

    @classmethod
    def from_branch(cls, branch: Branch) -> Self:
        at = Timestamp()
        return cls(
            name={"value": branch.name, "updated_at": at.to_string(), "updated_by": SYSTEM_USER_ID},
            description={"value": branch.description, "updated_at": at.to_string(), "updated_by": SYSTEM_USER_ID},
            status={"value": branch.status, "updated_at": at.to_string(), "updated_by": SYSTEM_USER_ID},
            origin_branch={"value": branch.origin_branch, "updated_at": at.to_string(), "updated_by": SYSTEM_USER_ID},
            branched_from={"value": branch.branched_from, "updated_at": at.to_string(), "updated_by": SYSTEM_USER_ID},
            hierarchy_level={
                "value": branch.hierarchy_level,
                "updated_at": at.to_string(),
                "updated_by": SYSTEM_USER_ID,
            },
            created_at=branch.created_at,
            created_by=branch.created_by,
            updated_at=branch.updated_at,
            updated_by=branch.updated_by,
            is_default={"value": branch.is_default, "updated_at": at.to_string(), "updated_by": SYSTEM_USER_ID},
            is_global={"value": branch.is_global, "updated_at": at.to_string(), "updated_by": SYSTEM_USER_ID},
            is_protected={"value": branch.is_protected, "updated_at": at.to_string(), "updated_by": SYSTEM_USER_ID},
            sync_with_git={"value": branch.sync_with_git, "updated_at": at.to_string(), "updated_by": SYSTEM_USER_ID},
            is_isolated={"value": branch.is_isolated, "updated_at": at.to_string(), "updated_by": SYSTEM_USER_ID},
            schema_changed_at={
                "value": branch.schema_changed_at,
                "updated_at": at.to_string(),
                "updated_by": SYSTEM_USER_ID,
            },
            schema_hash={"value": branch.schema_hash, "updated_at": at.to_string(), "updated_by": SYSTEM_USER_ID},
            graph_version={"value": branch.graph_version, "updated_at": at.to_string(), "updated_by": SYSTEM_USER_ID},
        )

    @field_validator("name", mode="before")
    @classmethod
    def validate_branch_name(cls, value: dict) -> dict:
        return {
            "value": super().validate_branch_name(value.get("value")),
            "updated_at": value.get("updated_at"),
            "updated_by": value.get("updated_by"),
        }

    @field_validator("branched_from", mode="before")
    @classmethod
    def set_branched_from(cls, value: dict) -> dict:
        return {
            "value": super().set_branched_from(value.get("value")),
            "updated_at": value.get("updated_at"),
            "updated_by": value.get("updated_by"),
        }

    @field_validator("graph_version", mode="before")
    @classmethod
    def set_graph_version(cls, value: dict) -> dict:
        return {"value": GRAPH_VERSION, "updated_at": value.get("updated_at"), "updated_by": value.get("updated_by")}

    @classmethod
    async def get_list(
        cls,
        db: InfrahubDatabase,
        limit: int = 1000,
        ids: list[str] | None = None,
        name: str | None = None,
        **kwargs: Any,
    ) -> list[Self]:
        query: Query = await InfrahubBranchNodeGetListQuery.init(
            db=db, node_class=cls, ids=ids, node_name=name, limit=limit, **kwargs
        )
        await query.execute(db=db)

        return [cls.from_db(node=cast(Neo4jNode, result.get("n"))) for result in query.get_results()]

    @classmethod
    async def get_list_count(
        cls,
        db: InfrahubDatabase,
        limit: int = 1000,
        ids: list[str] | None = None,
        name: str | None = None,
        **kwargs: Any,
    ) -> int:
        query: Query = await InfrahubBranchNodeGetListQuery.init(
            db=db, node_class=cls, ids=ids, node_name=name, limit=limit, exclude_global=True, **kwargs
        )
        return await query.count(db=db)

    @classmethod
    async def get_by_name(cls, name: str, db: InfrahubDatabase, ignore_deleting: bool = True) -> Self:
        query = """
        MATCH (n:InfrahubBranch)
        WHERE n.name__value = $name
        AND NOT n.status__value IN $ignore_statuses
        RETURN n
        """

        params: dict[str, Any] = {"name": name}
        params["ignore_statuses"] = []
        if ignore_deleting:
            params["ignore_statuses"].append(BranchStatus.DELETING.value)

        results = await db.execute_query(query=query, params=params, name="branch_get_by_name", type=QueryType.READ)

        if len(results) == 0:
            raise BranchNotFoundError(identifier=name)

        return cls.from_db(results[0].values()[0])

    @classmethod
    def from_db(cls, node: Neo4jNode, extras: Optional[dict[str, Any]] = None) -> Self:
        attrs = {}
        node_data = dict(node)
        extras = extras or {}
        node_data.update(extras)
        attrs["id"] = node.element_id

        processed_keys = set()
        datetime_fields = ["created_at", "updated_at", "branched_from", "schema_changed_at"]

        for key, value in node_data.items():
            if key in processed_keys:
                continue

            if "__value" in key:
                base_field_name = key.replace("__value", "")
                if base_field_name in cls.model_fields:
                    value_key = f"{base_field_name}__value"
                    updated_at_key = f"{base_field_name}__updated_at"
                    updated_by_key = f"{base_field_name}__updated_by"

                    field_value = node_data.get(value_key)
                    field_updated_at = (
                        Timestamp(node_data.get(updated_at_key)).to_datetime()
                        if node_data.get(updated_at_key) not in (None, NULL_VALUE)
                        else NULL_VALUE
                    )
                    field_updated_by = node_data.get(updated_by_key)

                    field_type = cls.guess_field_type(cls.model_fields[base_field_name])

                    deserialized_value = cls._get_flattened_field_value(
                        base_field_name, datetime_fields, field_type, field_value
                    )

                    attrs[base_field_name] = {
                        "value": deserialized_value,
                        "updated_at": None if field_updated_at == NULL_VALUE else field_updated_at,
                        "updated_by": None if field_updated_by == NULL_VALUE else field_updated_by,
                    }

                    processed_keys.add(value_key)
                    processed_keys.add(updated_at_key)
                    processed_keys.add(updated_by_key)
                    continue

            if key in datetime_fields:
                if value == NULL_VALUE:
                    attrs[key] = None
                else:
                    attrs[key] = Timestamp(value).to_datetime()
                continue

            if key in ["created_by", "updated_by"]:
                if value == NULL_VALUE:
                    attrs[key] = None
                else:
                    attrs[key] = value
                continue

            if key not in cls.model_fields:
                continue

            field_type = cls.guess_field_type(cls.model_fields[key])

            if value == NULL_VALUE:
                attrs[key] = None
            elif issubclass(field_type, int | float | bool | str | UUID):
                attrs[key] = value
            elif isinstance(value, str | bytes):
                attrs[key] = ujson.loads(value)

        return cls(**attrs)

    @classmethod
    def _get_flattened_field_value(
        cls, base_field_name: str, datetime_fields: list[str], field_type: Any, field_value: Any
    ) -> Any:
        deserialized_value = None
        if field_value == NULL_VALUE:
            deserialized_value = None
        elif inspect.isclass(field_type) and issubclass(field_type, FieldMetadata):
            value_field_type = cls.guess_field_type(field_type.model_fields.get("value"))

            if base_field_name in datetime_fields:
                deserialized_value = Timestamp(field_value).to_datetime()
            elif isinstance(field_value, str | bytes) and not issubclass(
                value_field_type, int | float | bool | str | UUID
            ):
                deserialized_value = ujson.loads(field_value)
            else:
                deserialized_value = field_value
        return deserialized_value

    def to_db(self) -> dict[str, Any]:
        data = {}

        if not self.uuid:
            data["uuid"] = str(UUIDT())
        else:
            data["uuid"] = str(self.uuid)

        for attr_name, field in self.model_fields.items():
            if attr_name in self._exclude_attrs:
                continue

            attr_value = getattr(self, attr_name)

            if attr_name in ["created_at", "created_by", "updated_at", "updated_by"]:
                if attr_value is None:
                    data[attr_name] = NULL_VALUE
                elif isinstance(attr_value, datetime):
                    data[attr_name] = Timestamp(attr_value).to_string()
                else:
                    data[attr_name] = attr_value
                continue

            field_type = self.guess_field_type(field)
            if inspect.isclass(field_type) and issubclass(field_type, FieldMetadata):
                if attr_value is None:
                    data[f"{attr_name}__value"] = NULL_VALUE
                    data[f"{attr_name}__updated_at"] = NULL_VALUE
                    data[f"{attr_name}__updated_by"] = NULL_VALUE
                else:
                    value = getattr(attr_value, "value", None)

                    if isinstance(value, Enum):
                        value = value.value

                    if value is None:
                        data[f"{attr_name}__value"] = NULL_VALUE
                    elif inspect.isclass(type(value)) and issubclass(type(value), BaseModel):
                        data[f"{attr_name}__value"] = value.model_dump_json()
                    else:
                        data[f"{attr_name}__value"] = value

                    updated_at = getattr(attr_value, "updated_at", None)
                    data[f"{attr_name}__updated_at"] = updated_at if updated_at is not None else NULL_VALUE

                    updated_by = getattr(attr_value, "updated_by", None)
                    data[f"{attr_name}__updated_by"] = updated_by if updated_by is not None else NULL_VALUE

        return data

    async def to_graphql(self, fields: dict) -> dict:
        data = await super().to_graphql(fields=fields)

        for key, value in data.items():
            if issubclass(type(value), FieldMetadata):
                data[key] = value.model_dump()

        if "node_metadata" in fields:
            data["node_metadata"] = {}
            for key in fields.get("node_metadata", {}):
                data["node_metadata"][key] = getattr(self, key, None)

        return data


registry.branch_object = Branch
