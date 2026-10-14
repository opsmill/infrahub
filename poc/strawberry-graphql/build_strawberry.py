"""Builds the same synthetic schema with Strawberry, entirely at runtime."""

import inspect
import types as pytypes
from typing import Any, Optional

import strawberry
from strawberry.annotation import StrawberryAnnotation
from strawberry.schema.config import StrawberryConfig
from strawberry.tools import create_type
from strawberry.types.arguments import StrawberryArgument
from strawberry.types.field import StrawberryField
from strawberry.types.fields.resolver import StrawberryResolver

from spec import Kind, attr_filter_names

# Same SDL name as Graphene's scalar, so clients see no difference.
GenericScalar = strawberry.scalar(
    pytypes.new_class("GenericScalar"),
    name="GenericScalar",
    description=(
        "The `GenericScalar` scalar type represents a generic\nGraphQL scalar value that could be:\n"
        "String, Boolean, Int, Float, List or Object."
    ),
    serialize=lambda v: v,
    parse_value=lambda v: v,
)


def dict_or_attr(obj: Any, name: str) -> Any:
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


@strawberry.type
class TextAttribute:
    id: Optional[str]
    value: Optional[str]
    is_protected: Optional[bool]
    updated_at: Optional[str]
    extra: Optional[GenericScalar]  # type: ignore[valid-type]


def _new_class(name: str, bases: tuple, annotations: dict[str, Any], namespace: dict[str, Any] | None = None) -> type:
    ns = dict(namespace or {})
    ns["__annotations__"] = annotations
    return pytypes.new_class(name, bases, {}, lambda n: n.update(ns))


def adapt(resolver: Any) -> Any:
    """Gives existing graphql-core style resolvers the raw GraphQLResolveInfo they expect."""
    if inspect.iscoroutinefunction(resolver):

        async def async_adapter(root: Any, info: strawberry.Info, **kwargs: Any) -> Any:
            return await resolver(root, info._raw_info, **kwargs)

        return async_adapter

    def adapter(root: Any, info: strawberry.Info, **kwargs: Any) -> Any:
        return resolver(root, info._raw_info, **kwargs)

    return adapter


def _field(
    name: str,
    type_: Any,
    resolver: Any = None,
    args: list[StrawberryArgument] | None = None,
    description: str | None = None,
) -> StrawberryField:
    field = StrawberryField(
        python_name=name,
        graphql_name=name,
        type_annotation=StrawberryAnnotation(type_),
        base_resolver=StrawberryResolver(adapt(resolver)) if resolver else None,
        description=description,
    )
    if args is not None:
        field.arguments = args
    return field


def _args(names: dict[str, Any]) -> list[StrawberryArgument]:
    return [
        StrawberryArgument(python_name=n, graphql_name=n, type_annotation=StrawberryAnnotation(Optional[t]))
        for n, t in names.items()
    ]


def build(spec: list[Kind], resolvers: dict[str, Any]) -> strawberry.Schema:
    classes: dict[str, type] = {}
    by_name = {k.name: k for k in spec}

    def resolve_type(cls: type, obj: dict, info: Any, abstract_type: Any) -> str:
        return obj["__typename"]

    node_iface = strawberry.interface(
        _new_class("CoreNode", (), {"id": str}, {"resolve_type": classmethod(resolve_type)})
    )
    classes["CoreNode"] = node_iface

    for kind in spec:
        if not kind.is_generic:
            continue
        ann = {"id": Optional[str], "display_label": Optional[str]} | {a: Optional[TextAttribute] for a in kind.attrs}
        classes[kind.name] = strawberry.interface(
            _new_class(kind.name, (), ann, {"resolve_type": classmethod(resolve_type)})
        )

    for kind in spec:
        if kind.is_generic:
            continue
        fields = {"id": strawberry.field(description=None)}
        ann: dict[str, Any] = {"id": str, "display_label": Optional[str]}
        for a in kind.attrs:
            ann[a] = Optional[TextAttribute]
            fields[a] = strawberry.field(description=f"{a} description")
        bases = tuple(classes[g] for g in kind.inherit_from) + (node_iface,)
        # Resolvers return dicts, so the default isinstance check against the class would reject every row.
        fields["is_type_of"] = classmethod(lambda cls, obj, info: True)
        classes[kind.name] = strawberry.type(_new_class(kind.name, bases, ann, fields))

    for kind in spec:
        for prefix in ("NestedEdged", "Edged"):
            classes[f"{prefix}{kind.name}"] = strawberry.type(
                _new_class(f"{prefix}{kind.name}", (), {"node": Optional[classes[kind.name]]})
            )
        for prefix, edge_prefix in (("NestedPaginated", "NestedEdged"), ("Paginated", "Edged")):
            classes[f"{prefix}{kind.name}"] = strawberry.type(
                _new_class(
                    f"{prefix}{kind.name}", (), {"count": int, "edges": list[classes[f"{edge_prefix}{kind.name}"]]}
                )
            )

    # Relationships are appended to the type definitions after every class exists.
    for kind in spec:
        definition = classes[kind.name].__strawberry_definition__
        for rel in kind.rels:
            peer = by_name[rel.peer]
            filters: dict[str, Any] = {"offset": int, "limit": int, "ids": list[strawberry.ID | None]}
            for a in peer.attrs:
                for f in attr_filter_names(a):
                    filters[f] = str
            if rel.cardinality == "one":
                field = _field(rel.name, classes[f"NestedEdged{peer.name}"], resolvers["one"], args=[])
            else:
                field = _field(rel.name, classes[f"NestedPaginated{peer.name}"], resolvers["many"], args=_args(filters))
            field.origin = classes[kind.name]
            definition.fields.append(field)

    query_fields = []
    for kind in spec:
        filters = {"offset": int, "limit": int, "ids": list[strawberry.ID | None]}
        for a in kind.attrs:
            for f in attr_filter_names(a):
                filters[f] = str
        for rel in kind.rels:
            for a in by_name[rel.peer].attrs:
                for f in attr_filter_names(a):
                    filters[f"{rel.name}__{f}"] = str
        query_fields.append(_field(kind.name, classes[f"Paginated{kind.name}"], resolvers["list"], args=_args(filters)))

    Query = create_type("Query", query_fields)

    @strawberry.input
    class CreateInput:
        name: str
        extra: Optional[GenericScalar] = strawberry.UNSET  # type: ignore[valid-type]

    @strawberry.type
    class TestCreate:
        ok: Optional[bool]

    def mutate(root: Any, info: Any, **kwargs: Any) -> Any:
        return TestCreate(
            ok=isinstance(kwargs["data"], CreateInput)
        )  # Strawberry hands resolvers an input class instance, not a dict

    mutation_field = _field(
        "TestCreate",
        Optional[TestCreate],
        mutate,
        args=[
            StrawberryArgument(
                python_name="data", graphql_name="data", type_annotation=StrawberryAnnotation(CreateInput)
            )
        ],
    )
    Mutation = create_type("Mutation", [mutation_field])

    return strawberry.Schema(
        query=Query,
        mutation=Mutation,
        types=list(classes.values()),
        config=StrawberryConfig(auto_camel_case=False, default_resolver=dict_or_attr),
    )
