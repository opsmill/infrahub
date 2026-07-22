from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from infrahub.core.constants import NULL_VALUE
from infrahub.core.preferences.constants import DateFormat
from infrahub.core.preferences.models import Preference
from infrahub.core.query import QueryResult, QueryType
from infrahub.core.query.standard_node import StandardNodeQuery

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


def _nullable_str(result: QueryResult, label: str) -> str | None:
    """Read an optional property column, mapping the stored NULL sentinel to None."""
    value = result.get_as_str(label)
    return None if value is None or value == NULL_VALUE else value


# The Preference columns to return: `elementId`/`uuid` and the audit fields must round-trip so a
# later save() updates the row in place instead of creating a duplicate or resetting its metadata.
_RETURN_LABELS = [
    "elementId(n) AS id",
    "n.uuid AS uuid",
    "n.owner_id AS owner_id",
    "n.date_format AS date_format",
    "n.timezone AS timezone",
    "n.created_at AS created_at",
    "n.created_by AS created_by",
    "n.updated_at AS updated_at",
    "n.updated_by AS updated_by",
]


class PreferenceReadQuery(StandardNodeQuery):
    """Shared read plumbing for Preference rows: the return columns and the row → Preference mapping."""

    type = QueryType.READ

    def _set_return_shape(self) -> None:
        # Copy the shared list: the base query appends to return_labels, which would otherwise
        # mutate the module-level constant across instances.
        self.return_labels = list(_RETURN_LABELS)
        # Deterministic order so reads are stable even in the (lock-prevented) event of a duplicate.
        self.order_by = ["uuid"]

    def get_preferences(self) -> list[Preference]:
        """Deserialize the result rows into Preference instances, in query order."""
        preferences: list[Preference] = []
        for result in self.get_results():
            date_format = _nullable_str(result, "date_format")
            preferences.append(
                Preference(
                    id=result.get_as_type("id", str),
                    uuid=UUID(result.get_as_type("uuid", str)),
                    owner_id=result.get_as_type("owner_id", str),
                    date_format=DateFormat(date_format) if date_format is not None else None,
                    timezone=_nullable_str(result, "timezone"),
                    created_at=_nullable_str(result, "created_at"),
                    created_by=result.get_as_type("created_by", str),
                    updated_at=_nullable_str(result, "updated_at"),
                    updated_by=_nullable_str(result, "updated_by"),
                )
            )
        return preferences


class PreferenceGetByOwnerQuery(PreferenceReadQuery):
    """Fetch the Preference rows for the given owner ids (account ids and/or the global sentinel).

    There is at most one row per owner (guaranteed by the per-owner upsert lock).
    """

    name = "preference_get_by_owner"

    def __init__(self, owner_ids: set[str], **kwargs: Any) -> None:
        self.owner_ids = owner_ids
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        # Cypher parameters cannot bind a set, so pass the ids as a list.
        self.params["owner_ids"] = list(self.owner_ids)

        # The label is the Preference StandardNode type name (Cypher labels can't be parameterised).
        query = """
        MATCH (n:Preference)
        WHERE n.owner_id IN $owner_ids
        """
        self.add_to_query(query=query)
        self._set_return_shape()


class PreferenceDeleteByOwnerQuery(StandardNodeQuery):
    """Delete every Preference row owned by one owner, in ONE query (no fetch-then-delete-each)."""

    name = "preference_delete_by_owner"
    type = QueryType.WRITE
    insert_return = False

    def __init__(self, owner_id: str, **kwargs: Any) -> None:
        self.owner_id = owner_id
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["owner_id"] = self.owner_id

        # The label is the Preference StandardNode type name (Cypher labels can't be parameterised).
        query = """
        MATCH (n:Preference { owner_id: $owner_id })
        DETACH DELETE n
        """
        self.add_to_query(query=query)


class PreferenceGetAllQuery(PreferenceReadQuery):
    """Fetch every Preference row, across all owners."""

    name = "preference_get_all"

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        # The label is the Preference StandardNode type name (Cypher labels can't be parameterised).
        query = """
        MATCH (n:Preference)
        """
        self.add_to_query(query=query)
        self._set_return_shape()
