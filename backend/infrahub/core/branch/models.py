from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Optional, Union

from pydantic import Field, field_validator

from infrahub.core.constants import (
    GLOBAL_BRANCH_NAME,
)
from infrahub.core.models import SchemaBranchHash  # noqa: TC001
from infrahub.core.node.standard import StandardNode
from infrahub.core.query import QueryType
from infrahub.core.query.branch import (
    DeleteBranchRelationshipsQuery,
    GetAllBranchInternalRelationshipQuery,
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
    status: str = "OPEN"  # OPEN, CLOSED
    description: str = ""
    origin_branch: str = "main"
    branched_from: Optional[str] = Field(default=None, validate_default=True)
    hierarchy_level: int = 2
    created_at: Optional[str] = Field(default=None, validate_default=True)
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
    async def get_by_name(cls, name: str, db: InfrahubDatabase) -> Branch:
        query = """
        MATCH (n:Branch)
        WHERE n.name = $name
        RETURN n
        """

        params = {"name": name}

        results = await db.execute_query(query=query, params=params, name="branch_get_by_name", type=QueryType.READ)

        if len(results) == 0:
            raise BranchNotFoundError(identifier=name)

        return cls.from_db(results[0].values()[0])

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

    def get_branches_and_times_to_query(self, at: Optional[Union[Timestamp, str]] = None) -> dict[frozenset, str]:
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
        at: Optional[Union[Timestamp, str]] = None,
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

    async def delete(self, db: InfrahubDatabase) -> None:
        if self.is_default:
            raise ValidationError(f"Unable to delete {self.name} it is the default branch.")
        if self.is_global:
            raise ValidationError(f"Unable to delete {self.name} this is an internal branch.")
        await super().delete(db=db)
        query = await DeleteBranchRelationshipsQuery.init(db=db, branch_name=self.name)
        await query.execute(db=db)

    def get_query_filter_relationships(
        self, rel_labels: list, at: Optional[Union[Timestamp, str]] = None, include_outside_parentheses: bool = False
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

        branches_times = self.get_branches_and_times_to_query_global(at=at_str, is_isolated=is_isolated)

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
        start_time: Union[Timestamp, str],
        end_time: Union[Timestamp, str],
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

    def get_query_filter_range(
        self, rel_label: list, start_time: Union[Timestamp, str], end_time: Union[Timestamp, str]
    ) -> tuple[list, dict]:
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


registry.branch_object = Branch
