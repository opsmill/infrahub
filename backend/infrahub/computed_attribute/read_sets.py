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

    # Only a kind with a derived read is a candidate; the walrus keeps that read set for the check.
    scopable_derived_kinds = {
        kind
        for kind, fields in read_fields_by_kind.items()
        if (derived_reads := frozenset(fields) & IMPRECISE_READ_FIELDS)
        and derived_reads_are_scopable(schema_branch=schema_branch, kind=kind, derived_reads=derived_reads)
    }

    return TransformReadSet.from_read_fields(read_fields_by_kind, scopable_derived_kinds=scopable_derived_kinds)


def derived_reads_are_scopable(*, schema_branch: SchemaBranch, kind: str, derived_reads: frozenset[str]) -> bool:
    """Whether every one of a kind's derived field reads can be held against that kind alone.

    ``derived_reads`` are the kind's imprecise reads, already filtered by the caller, so an absent
    kind is the only reason the reads cannot be resolved.
    """
    if not schema_branch.has(name=kind):
        return False

    node_schema = schema_branch.get(name=kind, duplicate=False)
    path_resolver = DerivedPathResolver(schema_branch=schema_branch)
    return all(
        derived_read_is_scopable(path_resolver=path_resolver, node_schema=node_schema, field_name=field_name)
        for field_name in derived_reads
    )
