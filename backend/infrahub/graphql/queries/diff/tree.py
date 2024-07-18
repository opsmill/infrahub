from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Optional, Union

from graphene import Boolean, DateTime, Field, Int, List, ObjectType, String
from graphene import Enum as GrapheneEnum
from infrahub_sdk.utils import extract_fields

from infrahub.core.constants import DiffAction

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

GrapheneDiffActionEnum = GrapheneEnum.from_enum(DiffAction)


class ConflictSelection(GrapheneEnum):
    BASE_BRANCH = "base"
    DIFF_BRANCH = "diff"


class ConflictDetails(ObjectType):
    uuid = String(required=True)
    base_branch_action = Field(GrapheneDiffActionEnum, required=True)
    base_branch_value = String()
    base_branch_changed_at = DateTime(required=True)
    diff_branch_action = Field(GrapheneDiffActionEnum, required=True)
    diff_branch_value = String()
    diff_branch_changed_at = DateTime(required=True)
    selected_branch = Field(ConflictSelection)


class DiffSummaryCounts(ObjectType):
    num_added = Int(required=False)
    num_updated = Int(required=False)
    num_removed = Int(required=False)
    num_conflicts = Int(required=False)


class DiffProperty(ObjectType):
    property_type = String(required=True)
    last_changed_at = DateTime(required=True)
    previous_value = String(required=False)
    new_value = String(required=False)
    status = Field(GrapheneDiffActionEnum, required=True)
    conflict = Field(ConflictDetails, required=False)


class DiffAttribute(DiffSummaryCounts):
    name = String(required=True)
    last_changed_at = DateTime(required=True)
    status = Field(GrapheneDiffActionEnum, required=True)
    properties = List(DiffProperty)
    contains_conflict = Boolean(required=True)


class DiffSingleRelationship(DiffSummaryCounts):
    last_changed_at = DateTime(required=False)
    status = Field(GrapheneDiffActionEnum, required=True)
    peer_id = String(required=True)
    contains_conflict = Boolean(required=True)
    conflict = Field(ConflictDetails, required=False)
    properties = List(DiffProperty)


class DiffRelationship(DiffSummaryCounts):
    name = String(required=True)
    last_changed_at = DateTime(required=False)
    status = Field(GrapheneDiffActionEnum, required=True)
    elements = List(DiffSingleRelationship, required=True)
    node_uuids = List(String, required=True)
    contains_conflict = Boolean(required=True)


class DiffNode(DiffSummaryCounts):
    uuid = String(required=True)
    kind = String(required=True)
    label = String(required=True)
    status = Field(GrapheneDiffActionEnum, required=True)
    contains_conflict = Boolean(required=True)
    last_changed_at = DateTime(required=False)
    attributes = List(DiffAttribute, required=True)
    relationships = List(DiffRelationship, required=True)


class DiffTree(DiffSummaryCounts):
    base_branch = String(required=True)
    diff_branch = String(required=True)
    from_time = DateTime(required=True)
    to_time = DateTime(required=True)
    nodes = List(DiffNode)


class DiffTreeResolver:
    the_time = datetime(year=2024, month=2, day=3, hour=4, minute=5, second=6, tzinfo=UTC)
    EXAMPLE_DIFF = DiffTree(
        base_branch="main",
        diff_branch="branch",
        from_time=the_time,
        to_time=the_time,
        num_added=1,
        num_updated=0,
        num_removed=0,
        num_conflicts=0,
        nodes=[
            DiffNode(
                uuid="cdea5cb3-36eb-4b26-87aa-0a1123dd7960",
                kind="SomethingKind",
                num_added=1,
                num_updated=0,
                num_removed=0,
                num_conflicts=0,
                last_changed_at=the_time,
                label="SomethingLabel",
                status=DiffAction.ADDED,
                contains_conflict=False,
                relationships=[],
                attributes=[
                    DiffAttribute(
                        name="SomethingAttribute",
                        last_changed_at=the_time,
                        status=DiffAction.ADDED,
                        num_added=1,
                        num_updated=0,
                        num_removed=0,
                        num_conflicts=0,
                        contains_conflict=False,
                        properties=[
                            DiffProperty(
                                property_type="value",
                                last_changed_at=the_time,
                                previous_value=None,
                                new_value=42,
                                status=DiffAction.ADDED,
                                conflict=None,
                            )
                        ],
                    )
                ],
            ),
            DiffNode(
                uuid="990e1eda-687b-454d-a6c3-dc6039f125dd",
                kind="ChildKind",
                num_added=0,
                num_updated=1,
                num_removed=0,
                num_conflicts=0,
                last_changed_at=the_time,
                label="ChildLabel",
                status=DiffAction.UPDATED,
                contains_conflict=False,
                relationships=[],
                attributes=[
                    DiffAttribute(
                        name="ChildAttribute",
                        last_changed_at=the_time,
                        status=DiffAction.UPDATED,
                        num_added=0,
                        num_updated=1,
                        num_removed=0,
                        num_conflicts=0,
                        contains_conflict=False,
                        properties=[
                            DiffProperty(
                                property_type="owner",
                                last_changed_at=the_time,
                                previous_value="herbert",
                                new_value="willy",
                                status=DiffAction.UPDATED,
                                conflict=None,
                            )
                        ],
                    )
                ],
            ),
            DiffNode(
                uuid="2beecc03-8d17-4360-b331-f242c9fb4997",
                kind="ParentKind",
                num_added=0,
                num_updated=0,
                num_removed=0,
                num_conflicts=0,
                last_changed_at=the_time,
                label="ParentLabel",
                status=DiffAction.UNCHANGED,
                contains_conflict=False,
                attributes=[],
                relationships=[
                    DiffRelationship(
                        name="child_relationship",
                        last_changed_at=the_time,
                        status=DiffAction.UPDATED,
                        contains_conflict=False,
                        elements=[],
                        node_uuids=["990e1eda-687b-454d-a6c3-dc6039f125dd"],
                    )
                ],
            ),
            DiffNode(
                uuid="a1b2f0c8-eda7-47e3-b3a2-5a055974c19c",
                kind="RelationshipConflictKind",
                num_added=0,
                num_updated=1,
                num_removed=0,
                num_conflicts=1,
                last_changed_at=the_time,
                label="RelationshipConflictLabel",
                status=DiffAction.UPDATED,
                contains_conflict=True,
                attributes=[],
                relationships=[
                    DiffRelationship(
                        name="conflict_relationship",
                        last_changed_at=the_time,
                        status=DiffAction.UPDATED,
                        contains_conflict=True,
                        node_uuids=[],
                        elements=[
                            DiffSingleRelationship(
                                last_changed_at=the_time,
                                status=DiffAction.UPDATED,
                                peer_id="7f0d1a04-1543-4d7e-b348-8fb1d19f7a8c",
                                contains_conflict=True,
                                properties=[
                                    DiffProperty(
                                        property_type="peer_id",
                                        last_changed_at=the_time,
                                        previous_value="87a4e7f8-5d7d-4b22-ab92-92b4d8890e75",
                                        new_value="c411c56f-d88b-402d-8753-0a35defaab1f",
                                        status=DiffAction.UPDATED,
                                        conflict=ConflictDetails(
                                            uuid="0a7a5898-e8a0-4baf-b7ae-1fac1fcdf468",
                                            base_branch_action=DiffAction.REMOVED,
                                            base_branch_value=None,
                                            base_branch_changed_at=the_time,
                                            diff_branch_action=DiffAction.UPDATED,
                                            diff_branch_value="c411c56f-d88b-402d-8753-0a35defaab1f",
                                            diff_branch_changed_at=the_time,
                                            selected_branch=None,
                                        ),
                                    ),
                                    DiffProperty(
                                        property_type="is_visible",
                                        last_changed_at=the_time,
                                        previous_value=False,
                                        new_value=True,
                                        status=DiffAction.UPDATED,
                                        conflict=ConflictDetails(
                                            uuid="60b2456b-0dcd-47c9-a9f1-590b30a597de",
                                            base_branch_action=DiffAction.REMOVED,
                                            base_branch_value=None,
                                            base_branch_changed_at=the_time,
                                            diff_branch_action=DiffAction.UPDATED,
                                            diff_branch_value=True,
                                            diff_branch_changed_at=the_time,
                                            selected_branch=ConflictSelection.DIFF_BRANCH,
                                        ),
                                    ),
                                ],
                            )
                        ],
                    )
                ],
            ),
        ],
    )

    def to_graphql(
        self, fields: dict[str, dict], diff_object: Optional[Any]
    ) -> Optional[Union[list[dict[str, Any]], dict[str, Any]]]:
        if diff_object is None:
            return None
        if isinstance(diff_object, list):
            list_response = True
            diff_elements = diff_object
        else:
            list_response = False
            diff_elements = [diff_object]

        response_list = []
        for diff_object_element in diff_elements:
            element_response = {}
            for field_name, sub_fields in fields.items():
                if sub_fields is None:
                    element_response[field_name] = getattr(diff_object_element, field_name, None)
                elif hasattr(diff_object_element, field_name):
                    element_response[field_name] = self.to_graphql(sub_fields, getattr(diff_object_element, field_name))
                else:
                    continue
            response_list.append(element_response)
        if list_response:
            return response_list
        return response_list[0]

    async def resolve(  # pylint: disable=unused-argument
        self,
        root: dict,
        info: GraphQLResolveInfo,
        **kwargs: Any,
    ) -> Optional[Union[list[dict[str, Any]], dict[str, Any]]]:
        full_fields = await extract_fields(info.field_nodes[0].selection_set)
        return self.to_graphql(fields=full_fields, diff_object=self.EXAMPLE_DIFF)


DiffTreeQuery = Field(
    DiffTree,
    name=String(),
    resolver=DiffTreeResolver().resolve,
    branches=List(String),
    from_time=DateTime(),
    to_time=DateTime(),
    root_node_uuids=List(String),
    max_depth=Int(),
    limit=Int(),
    offset=Int(),
)
