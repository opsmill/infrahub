from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from infrahub.core.graph.schema import GraphAttributeValueIndexedNode, GraphAttributeValueNode
from infrahub.core.query import Query, QueryType
from infrahub.types import is_large_attribute_type

if TYPE_CHECKING:
    from collections.abc import Generator

    from infrahub.core.schema.basenode_schema import SchemaAttributePath
    from infrahub.database import InfrahubDatabase


@dataclass(frozen=True)
class TargetedUniquenessViolation:
    """One changed node sharing its full constraint-value tuple with at least one other node."""

    changed_uuid: str
    element_values: tuple[Any, ...]
    partner_uuids: tuple[str, ...]


class TargetedUniquenessValidationQuery(Query):
    """Find uniqueness violations for a set of changed nodes.

    For one uniqueness constraint group, resolve the changed nodes' current values, then narrow the
    population with a single conjunctive pre-filter: a candidate must have an edge to *every* one of
    those values before any per-candidate work happens. Surviving candidate rows are streamed
    through the per-element current-value comparisons and only the final collision partners are
    collected. A changed node is reported only if at least one other node shares its full value
    tuple after the last element.

    The pre-filter deliberately carries no branch or time predicate, so it matches any edge that
    ever existed. That makes it a necessary-but-not-sufficient condition: it can only shrink the
    candidate set, never decide membership. Each surviving candidate's current value is still
    resolved under the normal branch/time rules before it counts as a collision.

    Requiring all values at once, rather than anchoring on one element and filtering afterwards,
    keeps peak memory proportional to the surviving candidates instead of to the population sharing
    any single value. It also leaves the choice of which value to seek first to the query planner.

    Values are compared as stored in the graph: enum values in their raw form and null attribute
    values as the null sentinel, so two nulls collide. A node without a live value for an element
    (e.g. a relationship with no peer) contributes no tuple and cannot collide on that group.

    Changed nodes and candidate partners must themselves be live: their latest IS_PART_OF edge on
    a visible branch must be active. This excludes nodes deleted on the branch and stale same-uuid
    duplicates left behind by kind or inheritance migrations.

    Supported constraint elements are node attributes (compared by value) and cardinality-one
    relationships (compared by peer uuid). Attributes of related peers are not supported.
    """

    name = "uniqueness_constraint_validation_targeted"
    type = QueryType.READ
    insert_return = False

    def __init__(
        self,
        kind: str,
        constraint_elements: list[SchemaAttributePath],
        node_uuids: list[str],
        **kwargs: Any,
    ) -> None:
        if not constraint_elements:
            raise ValueError("At least one constraint element is required")
        for element in constraint_elements:
            if element.relationship_schema is not None and element.attribute_schema is not None:
                raise ValueError(
                    f"{element.to_string()} is not supported for a targeted uniqueness check: "
                    "attributes of related peers cannot be part of a uniqueness constraint"
                )
            if element.relationship_schema is None and element.attribute_schema is None:
                raise ValueError("A constraint element requires an attribute or a relationship")
            if element.attribute_schema is not None and (element.attribute_property_name or "value") != "value":
                raise ValueError(
                    f"{element.attribute_property_name} is not a valid property for a uniqueness constraint"
                )
        self.kind = kind
        self.constraint_elements = constraint_elements
        self.node_uuids = node_uuids
        super().__init__(**kwargs)

    def get_context(self) -> dict[str, str]:
        return {"kind": self.kind}

    def _render_liveness_check(self, source_var: str, alias: str, branch_filter: str) -> str:
        """Render a subquery keeping only rows whose node is live.

        The latest IS_PART_OF edge on a visible branch decides: a node deleted on the branch, or a
        stale same-uuid duplicate left by a kind or inheritance migration, resolves to a non-active
        winner and the row is eliminated.
        """
        return """
CALL (%(source_var)s) {
    MATCH (%(source_var)s)-[r:IS_PART_OF]->(:Root)
    WHERE %(branch_filter)s
    WITH r.status = "active" AS is_active
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    WITH is_active
    LIMIT 1
    WITH is_active
    WHERE is_active = TRUE
    RETURN TRUE AS %(alias)s
}
        """ % {
            "source_var": source_var,
            "alias": alias,
            "branch_filter": branch_filter,
        }

    def _is_large_type(self, element: SchemaAttributePath) -> bool:
        return element.attribute_schema is not None and is_large_attribute_type(element.attribute_schema.kind)

    def _render_value_resolution(
        self, source_var: str, element: SchemaAttributePath, index: int, value_var: str, branch_filter: str
    ) -> tuple[str, dict[str, Any]]:
        """Render a subquery resolving the current value of one constraint element for one node.

        The winning edge per step is the latest one on the deepest branch; the row is eliminated
        when the winner is not active, so a node without a live value yields no row.
        """
        if element.attribute_schema is not None:
            attr_name_var = f"attr_name_{index}"
            query = """
CALL (%(source_var)s) {
    MATCH (%(source_var)s)-[r:HAS_ATTRIBUTE]->(attr:Attribute {name: $%(attr_name_var)s})
    WHERE %(branch_filter)s
    WITH attr, r.status = "active" AS is_active
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    WITH attr, is_active
    LIMIT 1
    WITH attr, is_active
    WHERE is_active = TRUE
    MATCH (attr)-[r:HAS_VALUE]->(av:AttributeValue)
    WHERE %(branch_filter)s
    WITH av, r.status = "active" AS is_active
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    WITH av, is_active
    LIMIT 1
    WITH av, is_active
    WHERE is_active = TRUE
    RETURN av.value AS %(value_var)s
}
            """ % {
                "source_var": source_var,
                "attr_name_var": attr_name_var,
                "branch_filter": branch_filter,
                "value_var": value_var,
            }
            return query, {attr_name_var: element.attribute_schema.name}

        relationship_schema = element.active_relationship_schema
        rel_identifier_var = f"rel_identifier_{index}"
        query_arrows = self.get_query_arrows(direction=relationship_schema.direction)
        query = """
CALL (%(source_var)s) {
    MATCH (%(source_var)s)%(lstart)s[r:IS_RELATED]%(lend)s(rel:Relationship {name: $%(rel_identifier_var)s})
    WHERE %(branch_filter)s
    WITH rel, r.status = "active" AS is_active
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    WITH rel, is_active
    LIMIT 1
    WITH rel, is_active
    WHERE is_active = TRUE
    MATCH (rel)%(rstart)s[r:IS_RELATED]%(rend)s(peer:Node)
    WHERE %(branch_filter)s AND peer.uuid <> %(source_var)s.uuid
    WITH peer, r.status = "active" AS is_active
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    WITH peer, is_active
    LIMIT 1
    WITH peer, is_active
    WHERE is_active = TRUE
    RETURN peer.uuid AS %(value_var)s
}
        """ % {
            "source_var": source_var,
            "rel_identifier_var": rel_identifier_var,
            "lstart": query_arrows.left.start,
            "lend": query_arrows.left.end,
            "rstart": query_arrows.right.start,
            "rend": query_arrows.right.end,
            "branch_filter": branch_filter,
            "value_var": value_var,
        }
        return query, {rel_identifier_var: relationship_schema.get_identifier()}

    def _render_prefilter(self, branch_filter: str) -> str:
        """Render the single population-wide narrowing step.

        Requires a candidate to have an edge to every one of the changed node's constraint values
        at once. The patterns carry no branch or time predicate, so they match any edge that ever
        existed -- this only shrinks the candidate set, it never decides membership. Which value the
        planner seeks first is left to it; every value vertex reachable here is index-backed.
        """
        patterns: list[str] = []
        for index, element in enumerate(self.constraint_elements):
            head = f"(candidate:{self.kind})" if index == 0 else "(candidate)"
            if element.attribute_schema is not None:
                attr_value_label = (
                    GraphAttributeValueNode.get_default_label()
                    if self._is_large_type(element)
                    else GraphAttributeValueIndexedNode.get_default_label()
                )
                patterns.append(
                    "    MATCH %(head)s-[:HAS_ATTRIBUTE]->(:Attribute {name: $attr_name_%(index)s})"
                    "-[:HAS_VALUE]->(:%(attr_value_label)s {value: value_%(index)s})"
                    % {"head": head, "index": index, "attr_value_label": attr_value_label}
                )
            else:
                query_arrows = self.get_query_arrows(direction=element.active_relationship_schema.direction)
                patterns.append(
                    "    MATCH %(head)s%(lstart)s[:IS_RELATED]%(lend)s"
                    "(:Relationship {name: $rel_identifier_%(index)s})"
                    "%(rstart)s[:IS_RELATED]%(rend)s(:Node {uuid: value_%(index)s})"
                    % {
                        "head": head,
                        "index": index,
                        "lstart": query_arrows.left.start,
                        "lend": query_arrows.left.end,
                        "rstart": query_arrows.right.start,
                        "rend": query_arrows.right.end,
                    }
                )

        candidate_liveness = self._render_liveness_check(
            source_var="candidate", alias="candidate_is_live", branch_filter=branch_filter
        )
        value_args = ", ".join(f"value_{index}" for index in range(len(self.constraint_elements)))
        return """
CALL (changed, %(value_args)s) {
%(patterns)s
    WHERE candidate.uuid <> changed.uuid
    WITH DISTINCT candidate
    %(candidate_liveness)s
    RETURN candidate
}
        """ % {
            "value_args": value_args,
            "patterns": "\n".join(patterns),
            "candidate_liveness": candidate_liveness,
        }

    def _render_reduction_probe(
        self,
        element: SchemaAttributePath,
        index: int,
        value_var: str,
        branch_filter: str,
        carried_vars: list[str],
    ) -> str:
        """Render the filter keeping only surviving candidates whose current value still matches.

        Candidate rows remain streamed in the outer scope, so only the per-candidate value
        resolution needs a subquery. A changed node whose candidates are all eliminated produces
        no row for the final aggregation, which is what removes it.
        """
        candidate_resolution, _ = self._render_value_resolution(
            source_var="candidate",
            element=element,
            index=index,
            value_var=f"cand_value_{index}",
            branch_filter=branch_filter,
        )
        carried = ", ".join(carried_vars)
        return """
%(candidate_resolution)s
WITH %(carried)s, candidate, cand_value_%(index)s
WHERE cand_value_%(index)s = %(value_var)s
        """ % {
            "value_var": value_var,
            "candidate_resolution": candidate_resolution,
            "index": index,
            "carried": carried,
        }

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string(), is_isolated=False)
        self.params.update(branch_params)
        self.params["node_uuids"] = self.node_uuids

        query_parts = [
            "MATCH (changed:Node)\nWHERE changed.uuid IN $node_uuids",
            self._render_liveness_check(source_var="changed", alias="changed_is_live", branch_filter=branch_filter),
        ]
        resolved_value_vars: list[str] = []
        for element_index, element in enumerate(self.constraint_elements):
            value_var = f"value_{element_index}"
            resolution, element_params = self._render_value_resolution(
                source_var="changed",
                element=element,
                index=element_index,
                value_var=value_var,
                branch_filter=branch_filter,
            )
            self.params.update(element_params)
            query_parts.append(resolution)
            resolved_value_vars.append(value_var)

        query_parts.append(self._render_prefilter(branch_filter=branch_filter))

        carried_vars = ["changed", *resolved_value_vars]
        for element_index, element in enumerate(self.constraint_elements):
            query_parts.append(
                self._render_reduction_probe(
                    element=element,
                    index=element_index,
                    value_var=f"value_{element_index}",
                    branch_filter=branch_filter,
                    carried_vars=carried_vars,
                )
            )

        element_values = ", ".join(f"value_{index}" for index in range(len(self.constraint_elements)))
        query_parts.append(
            "WITH changed, %(element_values)s, collect(DISTINCT candidate.uuid) AS partner_uuids\n"
            "RETURN changed.uuid AS changed_uuid,\n"
            "    [%(element_values)s] AS element_values,\n"
            "    partner_uuids" % {"element_values": element_values}
        )

        self.add_to_query("\n".join(query_parts))
        self.return_labels = ["changed_uuid", "element_values", "partner_uuids"]

    def get_data(self) -> Generator[TargetedUniquenessViolation, None, None]:
        for result in self.results:
            yield TargetedUniquenessViolation(
                changed_uuid=result.get_as_type("changed_uuid", return_type=str),
                element_values=result.get_as_type("element_values", return_type=tuple),
                partner_uuids=tuple(result.get_as_list_of_type("partner_uuids", return_type=str)),
            )
