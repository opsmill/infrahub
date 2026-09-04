"""Map an analyzed transform GraphQL query into the schema elements it reads."""

from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.schema.derived_path import DerivedPathResolver
from infrahub.core.schema.schema_branch_computed import TransformReadSet
from infrahub.core.schema.schema_branch_computed.python_transform import (
    IMPRECISE_READ_FIELDS,
    derived_read_is_scopable,
)

if TYPE_CHECKING:
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.graphql.analyzer import GraphQLQueryReport


def transform_read_set_from_query_report(
    *, report: GraphQLQueryReport, schema_branch: SchemaBranch
) -> TransformReadSet:
    """Map an analyzed GraphQL query report into the kinds and fields it reads."""
    read_fields_by_kind = {kind: access.fields for kind, access in report.requested_read.items()}

    scopable_derived_kinds = {
        kind
        for kind, fields in read_fields_by_kind.items()
        if derived_reads_are_scopable(schema_branch=schema_branch, kind=kind, read_fields=frozenset(fields))
    }

    return TransformReadSet.from_read_fields(read_fields_by_kind, scopable_derived_kinds=scopable_derived_kinds)


def derived_reads_are_scopable(*, schema_branch: SchemaBranch, kind: str, read_fields: frozenset[str]) -> bool:
    """Whether every derived field read on one kind can be held against that kind alone."""
    derived_reads = read_fields & IMPRECISE_READ_FIELDS
    if not derived_reads or not schema_branch.has(name=kind):
        return False

    node_schema = schema_branch.get(name=kind, duplicate=False)
    path_resolver = DerivedPathResolver(schema_branch=schema_branch)
    return all(
        derived_read_is_scopable(path_resolver=path_resolver, node_schema=node_schema, field_name=field_name)
        for field_name in derived_reads
    )
