from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional, Union

from graphene import Boolean, Field, Int, List, ObjectType, String
from graphene import Enum as GrapheneEnum
from graphene import Union as GrapheneUnion

from infrahub.core.constants import DiffAction
from infrahub.core.diff.branch_differ import BranchDiffer
from infrahub.core.diff.model import BranchDiffRelationshipMany, DiffElementType
from infrahub.core.diff.payload_builder import DiffPayloadBuilder

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.graphql import GraphqlContext


GrapheneDiffActionEnum = GrapheneEnum.from_enum(DiffAction)


class DiffSummaryCount(ObjectType):
    added = Int(default_value=0)
    updated = Int(default_value=0)
    removed = Int(default_value=0)


class DiffActionSummary(ObjectType):
    action = Field(GrapheneDiffActionEnum, required=True)
    summary = Field(DiffSummaryCount)


class DiffSummarySubElement(DiffActionSummary):
    name = String(required=True)


class DiffSummaryElement(DiffSummarySubElement):
    type = Field(GrapheneEnum.from_enum(DiffElementType), required=True)


class DiffSummaryElementRelationshipMany(DiffSummaryElement):
    peers = List(DiffActionSummary)


class OneDiffSummaryElement(GrapheneUnion):
    class Meta:
        types = (DiffSummaryElement, DiffSummaryElementRelationshipMany)

    @classmethod
    def resolve_type(cls, instance: Dict[str, Any], info: Any) -> type:
        if instance["type"] == DiffElementType.RELATIONSHIP_MANY.value or "peers" in instance:
            return DiffSummaryElementRelationshipMany
        return DiffSummaryElement


class DiffSummaryEntry(ObjectType):
    branch = String(required=True)
    id = String(required=True)
    kind = String(required=True)
    action = Field(GrapheneDiffActionEnum)
    display_label = String()
    elements = List(OneDiffSummaryElement)

    @staticmethod
    async def resolve(
        root: dict,  # pylint: disable=unused-argument
        info: GraphQLResolveInfo,
        branch_only: bool,
        time_from: Optional[str] = None,
        time_to: Optional[str] = None,
    ) -> list[Dict[str, Union[str, list[Dict[str, str]]]]]:
        return await DiffSummaryEntry.get_summary(
            info=info,
            branch_only=branch_only,
            time_from=time_from or None,
            time_to=time_to or None,
        )

    @classmethod
    async def get_summary(
        cls,
        info: GraphQLResolveInfo,
        branch_only: bool,
        time_from: Optional[str] = None,
        time_to: Optional[str] = None,
    ) -> list[Dict[str, Union[str, list[Dict[str, str]]]]]:
        context: GraphqlContext = info.context
        diff = await BranchDiffer.init(
            db=context.db, branch=context.branch, diff_from=time_from, diff_to=time_to, branch_only=branch_only
        )
        diff_payload_builder = DiffPayloadBuilder(db=context.db, diff=diff)
        branch_diff_nodes = await diff_payload_builder.get_branch_diff_nodes()
        serialized_summaries: List[Dict[str, Any]] = []

        for diff_node in branch_diff_nodes:
            serial_summary: Dict[str, Any] = {
                "branch": diff_node.branch,
                "id": diff_node.id,
                "kind": diff_node.kind,
                "action": diff_node.action,
                "display_label": diff_node.display_label,
            }
            serial_elements: List[Dict[str, Any]] = []
            for element_name, element in diff_node.elements.items():
                serial_element: Dict[str, Any] = {
                    "type": element.type.value,
                    "name": element_name,
                    "action": element.action,
                    "summary": element.summary,
                }
                if isinstance(element, BranchDiffRelationshipMany):
                    serial_element["peers"] = [
                        {"summary": peer.summary, "action": peer.action.value} for peer in element.peers
                    ]
                serial_elements.append(serial_element)
            serial_summary["elements"] = serial_elements
            serialized_summaries.append(serial_summary)
        return serialized_summaries


DiffSummary = Field(
    List(DiffSummaryEntry),
    time_from=String(required=False),
    time_to=String(required=False),
    branch_only=Boolean(required=False, default_value=False),
    resolver=DiffSummaryEntry.resolve,
)
