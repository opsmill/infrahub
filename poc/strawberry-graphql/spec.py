"""Synthetic Infrahub-like schema shared by the Graphene, Strawberry and graphql-core builders."""

from __future__ import annotations

import random
from dataclasses import dataclass, field


@dataclass
class Rel:
    name: str
    peer: str
    cardinality: str  # "one" | "many"


@dataclass
class Kind:
    name: str
    attrs: list[str]
    rels: list[Rel] = field(default_factory=list)
    inherit_from: list[str] = field(default_factory=list)
    is_generic: bool = False


ATTR_FILTER_SUFFIXES = ("value", "values", "is_protected", "source__id", "owner__id", "isnull")


def build_spec(n_nodes: int, n_generics: int, n_attrs: int, n_rels: int, seed: int = 1) -> list[Kind]:
    rnd = random.Random(seed)
    generics = [Kind(name=f"TestGeneric{i}", attrs=[f"gattr{i}"], is_generic=True) for i in range(n_generics)]
    nodes = []
    for i in range(n_nodes):
        inherit = sorted({g.name for g in rnd.sample(generics, k=min(2, len(generics)))})
        attrs = [f"attr{j}" for j in range(n_attrs)]
        for g in generics:
            if g.name in inherit:
                attrs = g.attrs + attrs
        nodes.append(Kind(name=f"TestNode{i}", attrs=attrs, inherit_from=inherit))
    for node in nodes:
        for j in range(n_rels):
            peer = rnd.choice(nodes + generics)
            node.rels.append(Rel(name=f"rel{j}", peer=peer.name, cardinality="one" if j % 2 == 0 else "many"))
    return generics + nodes


def attr_filter_names(attr: str) -> list[str]:
    return [f"{attr}__{suffix}" for suffix in ATTR_FILTER_SUFFIXES]


def make_rows(kind: Kind, count: int) -> list[dict]:
    rows = []
    for i in range(count):
        row: dict = {"__typename": kind.name, "id": f"{kind.name}-{i}", "display_label": f"label {i}"}
        for attr in kind.attrs:
            row[attr] = {"id": f"{attr}-{i}", "value": f"v{i}", "is_protected": False, "updated_at": "2026-01-01"}
        rows.append(row)
    return rows


QUERY_TEMPLATE = """
query {{
  {kind}(limit: 1000, attr0__value: "x") {{
    count
    edges {{
      node {{
        id
        display_label
        {attrs}
        rel0 {{ node {{ id display_label }} }}
        rel1 {{ count }}
      }}
    }}
  }}
}}
"""


def make_query(kind: Kind) -> str:
    attrs = "\n        ".join(f"{a} {{ id value is_protected updated_at }}" for a in kind.attrs)
    return QUERY_TEMPLATE.format(kind=kind.name, attrs=attrs)
