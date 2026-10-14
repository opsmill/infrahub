"""Compares enum serialization and DateTime parsing between Graphene and Strawberry."""

import datetime
import enum
import inspect

import graphene
import strawberry
from graphql import graphql_sync
from strawberry.schema.config import StrawberryConfig


class Color(enum.Enum):
    LIGHT_BLUE = "light-blue"


SColor = strawberry.enum(Color, name="Color")


@strawberry.type
class SQuery:
    @strawberry.field
    def member(self) -> SColor:
        return Color.LIGHT_BLUE

    @strawberry.field
    def raw_value(self) -> SColor:
        return "light-blue"

    @strawberry.field
    def raw_name(self) -> SColor:
        return "LIGHT_BLUE"

    @strawberry.field
    def when(self, at: datetime.datetime) -> str:
        return at.isoformat()


GColor = graphene.Enum.from_enum(Color)


class GQuery(graphene.ObjectType):
    member = graphene.Field(GColor, resolver=lambda r, i: Color.LIGHT_BLUE)
    raw_value = graphene.Field(GColor, resolver=lambda r, i: "light-blue")
    raw_name = graphene.Field(GColor, resolver=lambda r, i: "LIGHT_BLUE")
    when = graphene.Field(
        graphene.String, at=graphene.DateTime(required=True), resolver=lambda r, i, at: at.isoformat()
    )


ss = strawberry.Schema(SQuery, config=StrawberryConfig(auto_camel_case=False))._schema
gs = graphene.Schema(GQuery, auto_camelcase=False).graphql_schema
for f in ("member", "raw_value", "raw_name"):
    query = "{ %s }" % f
    print(f"{f:10s} graphene={graphql_sync(gs, query).formatted}  strawberry={graphql_sync(ss, query).formatted}")
for v in [
    "2026-01-02T03:04:05Z",
    "2026-01-02T03:04:05.123+02:00",
    "2026-01-02",
    "20260102T030405Z",
    "2026-01-02 03:04:05",
]:
    q = '{ when(at: "%s") }' % v
    g = graphql_sync(gs, q)
    s = graphql_sync(ss, q)
    print(f"{v:32s} graphene={g.data or g.errors[0].message[:60]}  strawberry={s.data or s.errors[0].message[:60]}")
print("strawberry.scalar params:", list(inspect.signature(strawberry.scalar).parameters))
