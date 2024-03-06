from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union

from pydantic import BaseModel

from infrahub import config
from infrahub.core import registry
from infrahub.core.constants import RelationshipDirection
from infrahub.core.query import QueryNode, QueryRel, QueryRelDirection
from infrahub.core.relationship import Relationship

from .generated.relationship_schema import GeneratedRelationshipSchema

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.query import QueryElement
    from infrahub.core.schema import GenericSchema, NodeSchema
    from infrahub.database import InfrahubDatabase


class RelationshipSchema(GeneratedRelationshipSchema):
    _exclude_from_hash: List[str] = ["filters"]
    _sort_by: List[str] = ["name"]

    @property
    def is_attribute(self) -> bool:
        return False

    @property
    def is_relationship(self) -> bool:
        return True

    def get_class(self) -> type[Relationship]:
        return Relationship

    def get_peer_schema(self, branch: Optional[Union[Branch, str]] = None) -> Union[NodeSchema, GenericSchema]:
        return registry.schema.get(name=self.peer, branch=branch, duplicate=False)

    @property
    def internal_peer(self) -> bool:
        return self.peer.startswith("Internal")

    def get_identifier(self) -> str:
        if not self.identifier:
            raise ValueError("RelationshipSchema is not initialized")
        return self.identifier

    def get_query_arrows(self) -> QueryArrows:
        """Return (in 4 parts) the 2 arrows for the relationship R1 and R2 based on the direction of the relationship."""

        if self.direction == RelationshipDirection.OUTBOUND:
            return QueryArrows(left=QueryArrowOutband(), right=QueryArrowOutband())
        if self.direction == RelationshipDirection.INBOUND:
            return QueryArrows(left=QueryArrowInband(), right=QueryArrowInband())

        return QueryArrows(left=QueryArrowOutband(), right=QueryArrowInband())

    async def get_query_filter(
        self,
        db: InfrahubDatabase,
        filter_name: str,
        filter_value: Optional[Union[str, int, bool]] = None,
        name: Optional[str] = None,  # pylint: disable=unused-argument
        branch: Optional[Branch] = None,
        include_match: bool = True,
        param_prefix: Optional[str] = None,
        partial_match: bool = False,
    ) -> Tuple[List[QueryElement], Dict[str, Any], List[str]]:
        """Generate Query String Snippet to filter the right node."""

        query_filter: List[QueryElement] = []
        query_params: Dict[str, Any] = {}
        query_where: List[str] = []

        prefix = param_prefix or f"rel_{self.name}"

        query_params[f"{prefix}_rel_name"] = self.identifier

        rel_type = self.get_class().rel_type
        peer_schema = self.get_peer_schema(branch=branch)

        if include_match:
            query_filter.append(QueryNode(name="n"))

        # Determine in which direction the relationships should point based on the side of the query
        rels_direction = {
            "r1": QueryRelDirection.OUTBOUND,
            "r2": QueryRelDirection.INBOUND,
        }
        if self.direction == RelationshipDirection.OUTBOUND:
            rels_direction = {
                "r1": QueryRelDirection.OUTBOUND,
                "r2": QueryRelDirection.OUTBOUND,
            }
        if self.direction == RelationshipDirection.INBOUND:
            rels_direction = {
                "r1": QueryRelDirection.INBOUND,
                "r2": QueryRelDirection.INBOUND,
            }

        if filter_name == "id":
            query_filter.extend(
                [
                    QueryRel(name="r1", labels=[rel_type], direction=rels_direction["r1"]),
                    QueryNode(name="rl", labels=["Relationship"], params={"name": f"${prefix}_rel_name"}),
                    QueryRel(name="r2", labels=[rel_type], direction=rels_direction["r2"]),
                    QueryNode(name="peer", labels=["Node"]),
                ]
            )

            if filter_value is not None:
                query_filter[-1].params = {"uuid": f"${prefix}_peer_id"}
                query_params[f"{prefix}_peer_id"] = filter_value

            return query_filter, query_params, query_where

        if filter_name == "ids":
            query_filter.extend(
                [
                    QueryRel(name="r1", labels=[rel_type], direction=rels_direction["r1"]),
                    QueryNode(name="rl", labels=["Relationship"], params={"name": f"${prefix}_rel_name"}),
                    QueryRel(name="r2", labels=[rel_type], direction=rels_direction["r2"]),
                    QueryNode(name="peer", labels=["Node"]),
                ]
            )

            if filter_value is not None:
                query_params[f"{prefix}_peer_ids"] = filter_value
                query_where.append(f"peer.uuid IN ${prefix}_peer_ids")

            return query_filter, query_params, query_where

        if "__" not in filter_name:
            return query_filter, query_params, query_where

        # -------------------------------------------------------------------
        # Check if the filter is matching
        # -------------------------------------------------------------------
        filter_field_name, filter_next_name = filter_name.split("__", maxsplit=1)

        if filter_field_name not in peer_schema.valid_input_names:
            return query_filter, query_params, query_where

        if self.hierarchical:
            query_filter.extend(
                [
                    QueryRel(
                        labels=[rel_type],
                        direction=rels_direction["r1"],
                        length_min=2,
                        length_max=config.SETTINGS.database.max_depth_search_hierarchy * 2,
                        params={"hierarchy": self.hierarchical},
                    ),
                    QueryNode(name="peer", labels=[self.hierarchical]),
                ]
            )
        else:
            query_filter.extend(
                [
                    QueryRel(name="r1", labels=[rel_type], direction=rels_direction["r1"]),
                    QueryNode(name="rl", labels=["Relationship"], params={"name": f"${prefix}_rel_name"}),
                    QueryRel(name="r2", labels=[rel_type], direction=rels_direction["r2"]),
                    QueryNode(name="peer", labels=["Node"]),
                ]
            )

        field = peer_schema.get_field(filter_field_name)

        field_filter, field_params, field_where = await field.get_query_filter(
            db=db,
            name=filter_field_name,
            filter_name=filter_next_name,
            filter_value=filter_value,
            branch=branch,
            include_match=False,
            param_prefix=prefix if param_prefix else None,
            partial_match=partial_match,
        )

        query_filter.extend(field_filter)
        query_where.extend(field_where)
        query_params.update(field_params)

        return query_filter, query_params, query_where


class QueryArrow(BaseModel):
    start: str
    end: str


class QueryArrowInband(QueryArrow):
    start: str = "<-"
    end: str = "-"


class QueryArrowOutband(QueryArrow):
    start: str = "-"
    end: str = "->"


class QueryArrowBidir(QueryArrow):
    start: str = "-"
    end: str = "-"


class QueryArrows(BaseModel):
    left: QueryArrow
    right: QueryArrow
