from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from pydantic import BaseModel, Field

from infrahub.utils import InfrahubStringEnum

if TYPE_CHECKING:
    from infrahub.core.constants import BranchSupportType, RelationshipStatus

# Root & Branch nodes are described in their own files


class GraphRelDirection(InfrahubStringEnum):
    EITHER = "either"
    OUTBOUND = "outbound"
    INBOUND = "inbound"


class GraphRelationship(BaseModel):
    peer: str
    direction: GraphRelDirection


# -----------------------------------------------------
# Node
# -----------------------------------------------------
class GraphNodeProperties(BaseModel):
    branch_support: BranchSupportType = Field(..., description="Type of branch support for the node")
    kind: str = Field(..., description="Kind of the Node")
    namespace: str = Field(
        ...,
        description="Namespace of the Node, already included in the kind "
        "but having it as a separate properties makes it easier to query by namespace",
    )
    uuid: str = Field(..., description="UUID of the node")


class GraphNodeRelationships(BaseModel):
    IS_RELATED: GraphRelationship = Field(
        GraphRelationship(peer="Relationship", direction=GraphRelDirection.EITHER),
        description="Attach a Relationship to a node",
    )
    HAS_ATTRIBUTE: GraphRelationship = Field(
        GraphRelationship(peer="Attribute", direction=GraphRelDirection.OUTBOUND),
        description="Attach an Attribute to a node",
    )
    IS_PART_OF: GraphRelationship = Field(
        GraphRelationship(peer="Root", direction=GraphRelDirection.OUTBOUND),
        description="Attach the node with the Root node",
    )
    # for the properties
    HAS_SOURCE: GraphRelationship = Field(
        GraphRelationship(peer="Attribute|Relationship", direction=GraphRelDirection.INBOUND),
        description="Identify the node as the source of the object on the other side",
    )
    HAS_OWNER: GraphRelationship = Field(
        GraphRelationship(peer="Attribute|Relationship", direction=GraphRelDirection.INBOUND),
        description="Identify the node as the owner of the object on the other side",
    )


class GraphNodeNode(BaseModel):
    default_label: str = "Node"  # Most node also have CoreNode
    properties: GraphNodeProperties
    relationships: GraphNodeRelationships


# -----------------------------------------------------
# Relationship
# -----------------------------------------------------
class GraphRelationshipProperties(BaseModel):
    branch_support: BranchSupportType = Field(..., description="Type of branch support for the relationship")
    name: str = Field(..., description="identifier of the relationship")
    uuid: str = Field(..., description="UUID of the relationship")


class GraphRelationshipRelationships(BaseModel):
    IS_RELATED: GraphRelationship = Field(
        GraphRelationship(peer="Node", direction=GraphRelDirection.EITHER),
        description="Attach a Relationship to a node",
    )
    HAS_SOURCE: GraphRelationship = Field(
        GraphRelationship(peer="Node", direction=GraphRelDirection.OUTBOUND), description=""
    )
    HAS_OWNER: GraphRelationship = Field(
        GraphRelationship(peer="Node", direction=GraphRelDirection.OUTBOUND), description=""
    )
    IS_VISIBLE: GraphRelationship = Field(
        GraphRelationship(peer="Boolean", direction=GraphRelDirection.OUTBOUND), description=""
    )
    IS_PROTECTED: GraphRelationship = Field(
        GraphRelationship(peer="Boolean", direction=GraphRelDirection.OUTBOUND), description=""
    )


class GraphRelationshipNode(BaseModel):
    default_label: str = "Relationship"
    properties: GraphRelationshipProperties
    relationships: GraphRelationshipRelationships


# -----------------------------------------------------
# Attribute
# -----------------------------------------------------
class GraphAttributeProperties(BaseModel):
    branch_support: BranchSupportType = Field(..., description="Type of branch support for the attribute")
    name: str = Field(..., description="name of the attribute as defined in the schema")
    uuid: str = Field(..., description="UUID of the attribute, must be unique")


class GraphAttributeRelationships(BaseModel):
    HAS_ATTRIBUTE: GraphRelationship = Field(
        GraphRelationship(peer="Node", direction=GraphRelDirection.INBOUND),
        description="Identify the node for this Attribute",
    )
    HAS_VALUE: GraphRelationship = Field(
        GraphRelationship(peer="AttributeValue", direction=GraphRelDirection.OUTBOUND),
        description="Attach a Value to an Attribute",
    )
    HAS_SOURCE: GraphRelationship = Field(
        GraphRelationship(peer="Node", direction=GraphRelDirection.OUTBOUND), description=""
    )
    HAS_OWNER: GraphRelationship = Field(
        GraphRelationship(peer="Node", direction=GraphRelDirection.OUTBOUND), description=""
    )
    IS_VISIBLE: GraphRelationship = Field(
        GraphRelationship(peer="Boolean", direction=GraphRelDirection.OUTBOUND), description=""
    )
    IS_PROTECTED: GraphRelationship = Field(
        GraphRelationship(peer="Boolean", direction=GraphRelDirection.OUTBOUND), description=""
    )


class GraphAttributeNode(BaseModel):
    default_label: str = "Attribute"
    properties: GraphAttributeProperties
    relationships: GraphAttributeRelationships


# -----------------------------------------------------
# AttributeValue
# -----------------------------------------------------
class GraphAttributeValueProperties(BaseModel):
    value: Any = Field(..., description="value of the attribute")


class GraphAttributeIPNetworkProperties(BaseModel):
    value: str = Field(..., description="value of the attribute")
    is_default: bool = Field(..., description="Flag to indicate if an attribute has the default value")
    binary_address: str = Field(..., description="Network address represented in binary format")
    version: int = Field(..., description="Version of IP, either 4 or 6")
    # num_addresses: int = Field(..., description="Total number of addresses available in this IPNetwork")


class GraphAttributeIPHostProperties(BaseModel):
    value: str = Field(..., description="value of the attribute")
    is_default: bool = Field(..., description="Flag to indicate if an attribute has the default value")
    binary_address: str = Field(..., description="Network address represented in binary format")
    version: int = Field(..., description="Version of IP, either 4 or 6")


class GraphAttributeValueRelationships(BaseModel):
    HAS_VALUE: GraphRelationship = Field(
        GraphRelationship(peer="Attribute", direction=GraphRelDirection.INBOUND),
        description="Attach the Value to an Attribute",
    )


class GraphAttributeValueNode(BaseModel):
    default_label: str = "AttributeValue"
    properties: GraphAttributeValueProperties
    relationships: GraphAttributeValueRelationships


class GraphAttributeIPNetworkNode(BaseModel):
    default_label: str = "AttributeIPNetwork"
    properties: GraphAttributeIPNetworkProperties
    relationships: GraphAttributeValueRelationships


class GraphAttributeIPHostNode(BaseModel):
    default_label: str = "AttributeIPHost"
    properties: GraphAttributeIPHostProperties
    relationships: GraphAttributeValueRelationships


# -----------------------------------------------------
# Boolean
# -----------------------------------------------------
class GraphBooleanProperties(BaseModel):
    value: bool = Field(..., description="Value of the Boolean")


class GraphBooleanRelationships(BaseModel):
    IS_VISIBLE: GraphRelationship = Field(
        GraphRelationship(peer="Attribute|Relationship", direction=GraphRelDirection.INBOUND), description=""
    )
    IS_PROTECTED: GraphRelationship = Field(
        GraphRelationship(peer="Attribute|Relationship", direction=GraphRelDirection.INBOUND), description=""
    )


class GraphBooleanNode(BaseModel):
    default_label: str = "Boolean"
    properties: GraphBooleanProperties
    relationships: GraphBooleanRelationships


class GraphRelationshipIsPartOf(BaseModel):
    from_: str = Field(..., description="Time from which the relationship is valid", alias="from")
    to_: Optional[str] = Field(None, description="Time until which the relationship is valid", alias="to")
    status: RelationshipStatus = Field(..., description="status of the relationship")


class GraphRelationshipDefault(BaseModel):
    branch: str = Field(
        ..., description="name of the branch this relationship is part of, global branch will be -global-"
    )
    branch_level: int = Field(
        ...,
        description="Indicator of the level of the branch compared to main, currently either 1 or 2 since we only support 1 level",
        ge=1,
    )
    from_: str = Field(..., description="Time from which the relationship is valid", alias="from")
    to_: Optional[str] = Field(None, description="Time until which the relationship is valid", alias="to")
    status: RelationshipStatus = Field(..., description="status of the relationship")
    hierarchy: Optional[str] = Field(None, description="Name of the hierarchy this relationship is part of")


GRAPH_SCHEMA: dict[str, dict[str, Any]] = {
    "nodes": {
        "Node": GraphNodeNode,
        "Relationship": GraphRelationshipNode,
        "Attribute": GraphAttributeNode,
        "AttributeValue": GraphAttributeValueNode,
        "AttributeIPNetwork": GraphAttributeIPNetworkNode,
        "AttributeIPHost": GraphAttributeIPHostNode,
        "Boolean": GraphBooleanNode,
    },
    "relationships": {
        # Ignoring IS_PART_OF for now, because there is a bit of cleanup required
        # "IS_PART_OF": GraphRelationshipIsPartOf,
        "HAS_VALUE": GraphRelationshipDefault,
        "HAS_ATTRIBUTE": GraphRelationshipDefault,
        "IS_RELATED": GraphRelationshipDefault,
        "HAS_SOURCE": GraphRelationshipDefault,
        "HAS_OWNER": GraphRelationshipDefault,
        "IS_VISIBLE": GraphRelationshipDefault,
        "IS_PROTECTED": GraphRelationshipDefault,
    },
}
