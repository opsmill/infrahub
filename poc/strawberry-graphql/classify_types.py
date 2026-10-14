"""Splits the GraphQL types of the core Infrahub schema into hand-written and generated types.

Runs in the Infrahub environment (`uv run python poc/strawberry-graphql/classify_types.py` from the repository root)
and writes type_classification.json, which combined.py reads.

- generated: types whose name is a schema kind or is derived from one (Edged, Paginated, Create, UpdateInput, ...).
- schema_dependent_static: hand-written types that reference a generated type, directly or through other
  hand-written types; they have to be built for each schema together with the generated types.
- static: every other hand-written type; they never change and can be built once per process.
"""

import json
import pathlib

from graphql import GraphQLInputObjectType, GraphQLInterfaceType, GraphQLObjectType, get_named_type
from infrahub import config

config.SETTINGS.initialize_and_exit()

from infrahub.core.schema import SchemaRoot, core_models, internal_schema  # noqa: E402
from infrahub.core.schema.schema_branch import SchemaBranch  # noqa: E402
from infrahub.graphql.manager import GraphQLSchemaManager  # noqa: E402

PREFIXES = ("NestedPaginated", "NestedEdged", "Paginated", "Edged")
SUFFIXES = ("CreateInput", "UpdateInput", "UpsertInput", "Create", "Update", "Upsert", "Delete")
MANAGER_TYPES = {"RelationshipProperty", "InfrahubNodeMetadata", "InfrahubRelationshipMetadata"}
ROOTS = {"Query", "Mutation", "Subscription"}


def main() -> None:
    schema = SchemaRoot(**internal_schema).merge(schema=SchemaRoot(**core_models))
    schema_branch = SchemaBranch(cache={}, name="default")
    schema_branch.load_schema(schema=schema)
    schema_branch.process()
    gql = GraphQLSchemaManager(schema=schema_branch).generate()
    kinds = set(schema_branch.get_all(duplicate=False).keys()) | {"CoreNode"}

    def is_generated(name: str) -> bool:
        if name in kinds or name in MANAGER_TYPES:
            return True
        if any(name.startswith(p) and name[len(p) :] in kinds for p in PREFIXES):
            return True
        return any(name.endswith(s) and name[: -len(s)] in kinds for s in SUFFIXES)

    def is_generated_root_field(name: str) -> bool:
        return name in kinds or any(name == k + s for k in kinds for s in SUFFIXES)

    def references(type_name: str) -> set[str]:
        t = gql.type_map[type_name]
        out: set[str] = set()
        if isinstance(t, GraphQLObjectType | GraphQLInterfaceType | GraphQLInputObjectType):
            for field in t.fields.values():
                out.add(get_named_type(field.type).name)
                out |= {get_named_type(a.type).name for a in getattr(field, "args", {}).values()}
        if isinstance(t, GraphQLObjectType | GraphQLInterfaceType):
            out |= {i.name for i in t.interfaces}
        return out

    names = [n for n in gql.type_map if not n.startswith("__") and n not in ROOTS]
    generated = {n for n in names if is_generated(n)}
    dependent: set[str] = set()
    changed = True
    while changed:
        changed = False
        for name in names:
            if name not in generated and name not in dependent and references(name) & (generated | dependent):
                dependent.add(name)
                changed = True
    static = set(names) - generated - dependent

    static_root_fields = {}
    for attr in ("query_type", "mutation_type", "subscription_type"):
        root = getattr(gql, attr)
        static_root_fields[attr] = sorted(
            name
            for name, field in root.fields.items()
            if not is_generated_root_field(name)
            and get_named_type(field.type).name in static
            and all(get_named_type(a.type).name in static for a in field.args.values())
        )

    output = {
        "static": sorted(static),
        "schema_dependent_static": sorted(dependent),
        "generated": sorted(generated),
        "static_root_fields": static_root_fields,
    }
    path = pathlib.Path(__file__).parent / "type_classification.json"
    path.write_text(json.dumps(output, indent=2) + "\n")
    print({k: len(v) for k, v in output.items() if isinstance(v, list)})
    print({k: len(v) for k, v in static_root_fields.items()})
    print("schema-dependent hand-written types:", sorted(dependent))


if __name__ == "__main__":
    main()
