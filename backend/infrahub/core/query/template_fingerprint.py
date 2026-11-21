from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Unpack

from infrahub.core.query import Query, QueryInitKwargs, QueryType
from infrahub.core.template_fingerprint.models import TemplateFingerprint

if TYPE_CHECKING:
    from collections.abc import Generator

LABEL = TemplateFingerprint.get_type()


@dataclass(frozen=True)
class TemplateFingerprintGetQueryResult:
    branch: str
    kind: str
    fingerprint: str


class TemplateFingerprintGetByFamilyQuery(Query):
    name = "template-fingerprint-get-by-family"
    type = QueryType.READ

    def __init__(self, family: str, **kwargs: Unpack[QueryInitKwargs]) -> None:
        super().__init__(**kwargs)
        self.params["family"] = family
        self.add_to_query(f"MATCH (f:{LABEL} {{ family: $family }})")
        self.return_labels = [
            "f.branch AS branch",
            "f.kind AS kind",
            "f.fingerprint AS fingerprint",
        ]
        # The read is paginated by the size limit, so the order must be stable across pages.
        self.order_by = ["branch", "kind"]

    def get_data(self) -> Generator[TemplateFingerprintGetQueryResult]:
        for result in self.get_results():
            yield TemplateFingerprintGetQueryResult(
                branch=result.get_as_type("branch", str),
                kind=result.get_as_type("kind", str),
                fingerprint=result.get_as_type("fingerprint", str),
            )


@dataclass(frozen=True)
class TemplateFingerprintInsertMissingQueryResult:
    created: int


class TemplateFingerprintUpsertQuery(Query):
    """Create or overwrite one record per entry, skipping the entries whose branch has no Branch vertex."""

    name = "template-fingerprint-upsert"
    type = QueryType.WRITE
    insert_return = False

    def __init__(self, records: list[dict[str, Any]], **kwargs: Unpack[QueryInitKwargs]) -> None:
        super().__init__(**kwargs)
        self.params["records"] = records
        self.add_to_query(
            f"""
            UNWIND $records AS r
            MATCH (:Branch {{ name: r.branch }})
            MERGE (f:{LABEL} {{ family: r.family, branch: r.branch, kind: r.kind }})
            ON CREATE SET f.uuid = r.uuid
            SET f.fingerprint = r.fingerprint
            """
        )


class TemplateFingerprintInsertMissingQuery(Query):
    """Create the records that do not exist yet and never overwrite one.

    Each entry carries a fresh uuid, so a vertex holding that uuid after the merge is one this query created.
    """

    name = "template-fingerprint-insert-missing"
    type = QueryType.WRITE

    def __init__(self, records: list[dict[str, Any]], **kwargs: Unpack[QueryInitKwargs]) -> None:
        super().__init__(**kwargs)
        self.params["records"] = records
        self.add_to_query(
            f"""
            UNWIND $records AS r
            MATCH (:Branch {{ name: r.branch }})
            MERGE (f:{LABEL} {{ family: r.family, branch: r.branch, kind: r.kind }})
            ON CREATE SET f.uuid = r.uuid, f.fingerprint = r.fingerprint
            """
        )
        self.return_labels = ["sum(CASE WHEN f.uuid = r.uuid THEN 1 ELSE 0 END) AS created"]

    def get_data(self) -> Generator[TemplateFingerprintInsertMissingQueryResult]:
        for result in self.get_results():
            yield TemplateFingerprintInsertMissingQueryResult(created=result.get_as_type("created", int))


class TemplateFingerprintDeleteQuery(Query):
    name = "template-fingerprint-delete"
    type = QueryType.WRITE
    insert_return = False

    def __init__(self, keys: list[dict[str, str]], **kwargs: Unpack[QueryInitKwargs]) -> None:
        super().__init__(**kwargs)
        self.params["keys"] = keys
        self.add_to_query(
            f"""
            UNWIND $keys AS k
            MATCH (f:{LABEL} {{ family: k.family, branch: k.branch, kind: k.kind }})
            DETACH DELETE f
            """
        )


class TemplateFingerprintDeleteBranchQuery(Query):
    name = "template-fingerprint-delete-branch"
    type = QueryType.WRITE
    insert_return = False

    def __init__(self, branch_name: str, **kwargs: Unpack[QueryInitKwargs]) -> None:
        super().__init__(**kwargs)
        self.params["branch_name"] = branch_name
        self.add_to_query(
            f"""
            MATCH (f:{LABEL} {{ branch: $branch_name }})
            DETACH DELETE f
            """
        )
