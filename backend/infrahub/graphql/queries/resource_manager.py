from __future__ import annotations

from typing import TYPE_CHECKING

from graphene import Field, Float, Int, List, ObjectType, String

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo


class IPPoolUtilizationResource(ObjectType):
    id = Field(String, required=True, description="The ID of the current resource")
    display_label = Field(String, required=True, description="The common name of the resource")
    kind = Field(String, required=True, description="The resource kind")
    weight = Field(Int, required=True, description="The relative weight of this resource.")
    utilization = Field(Float, required=True, description="The overall utilization of the resource.")
    utilization_branches = Field(
        Float,
        required=True,
        description="The utilization of the resource across all branches aside from the default one.",
    )
    utilization_default_branch = Field(
        Float, required=True, description="The overall utilization of the resource isolated to the default branch."
    )


class IPPrefixUtilizationEdge(ObjectType):
    node = Field(IPPoolUtilizationResource, required=True)


class IPPrefixPoolUtilization(ObjectType):
    count = Field(Int, required=True, description="The number of resources within the selected pool.")
    utilization = Field(Float, required=True, description="The overall utilization of the pool.")
    utilization_branches = Field(
        Float, required=True, description="The utilization of the pool across all branches aside from the default one."
    )
    utilization_default_branch = Field(
        Float, required=True, description="The overall utilization of the pool isolated to the default branch."
    )
    edges = Field(List(of_type=IPPrefixUtilizationEdge, required=True), required=True)

    @staticmethod
    async def resolve(  # pylint: disable=unused-argument
        root: dict,
        info: GraphQLResolveInfo,
        pool_id: str,
    ) -> dict:
        return {
            "count": 2,
            "utilization": 46,
            "utilization_branches": 12,
            "utilization_default_branch": 34,
            "edges": [
                {
                    "node": {
                        "id": "imaginary-id-1",
                        "kind": "IpamIPPrefix",
                        "display_label": "10.24.16.0/18",
                        "weight": 18,
                        "utilization": 50,
                        "utilization_branches": 26,
                        "utilization_default_branch": 76,
                    }
                },
                {
                    "node": {
                        "id": "imaginary-id-2",
                        "kind": "IpamIPPrefix",
                        "display_label": "10.28.0.0/16",
                        "weight": 16,
                        "utilization": 20,
                        "utilization_branches": 0,
                        "utilization_default_branch": 20,
                    }
                },
            ],
        }


InfrahubResourcePoolUtilization = Field(
    IPPrefixPoolUtilization,
    pool_id=String(required=True),
    resolver=IPPrefixPoolUtilization.resolve,
)
