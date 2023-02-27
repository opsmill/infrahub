from __future__ import annotations

# class FilterSchema(BaseModel):
#     name: str
#     kind: str
#     description: Optional[str]

# class AttributeSchema(BaseModel):
#     name: str
#     kind: str
#     label: Optional[str]
#     description: Optional[str]
#     default_value: Optional[Any]
#     inherited: bool = False
#     unique: bool = False
#     branch: bool = True
#     optional: bool = False


# class RelationshipSchema(BaseModel):
#     name: str
#     peer: str
#     label: Optional[str]
#     description: Optional[str]
#     identifier: Optional[str]
#     inherited: bool = False
#     cardinality: str = "many"
#     branch: bool = True
#     optional: bool = True


# class BaseNodeSchema(BaseModel):
#     name: str
#     kind: str
#     description: Optional[str]
#     attributes: List[AttributeSchema] = Field(default_factory=list)
#     relationships: List[RelationshipSchema] = Field(default_factory=list)


# class GenericSchema(BaseNodeSchema):
#     """A Generic can be either an Interface or a Union depending if there are some Attributes or Relationships defined."""

#     label: Optional[str]


# class NodeSchema(BaseNodeSchema):
#     label: Optional[str]
#     inherit_from: List[str] = Field(default_factory=list)
#     groups: List[str] = Field(default_factory=list)
#     branch: bool = True
#     default_filter: Optional[str]


# class GroupSchema(BaseModel):
#     name: str
#     kind: str
#     description: Optional[str]


# class SchemaRoot(BaseModel):
#     version: str
#     generics: List[GenericSchema] = Field(default_factory=list)
#     nodes: List[NodeSchema] = Field(default_factory=list)
#     groups: List[GroupSchema] = Field(default_factory=list)
