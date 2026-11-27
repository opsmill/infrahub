from dataclasses import dataclass


@dataclass
class HiddenMutationCase:
    name: str
    query: str


# A mutation reached through a top-level inline fragment or fragment spread, which the analyzer must
# still report as a mutation, in both single- and multi-operation documents.
HIDDEN_MUTATION_CASES = [
    HiddenMutationCase(
        name="single_operation_inline_fragment",
        query='mutation { ... on Mutation { TestPersonCreate(data: {name: {value: "x"}}) { ok } } }',
    ),
    HiddenMutationCase(
        name="single_operation_inline_fragment_without_type_condition",
        query='mutation { ... { TestPersonCreate(data: {name: {value: "x"}}) { ok } } }',
    ),
    HiddenMutationCase(
        name="single_operation_fragment_spread",
        query="mutation { ...Hidden }"
        ' fragment Hidden on Mutation { TestPersonCreate(data: {name: {value: "x"}}) { ok } }',
    ),
    HiddenMutationCase(
        name="multi_operation_inline_fragment",
        query="query A { __typename }"
        ' mutation B { ... on Mutation { TestPersonCreate(data: {name: {value: "x"}}) { ok } } }',
    ),
    HiddenMutationCase(
        name="multi_operation_inline_fragment_without_type_condition",
        query='query A { __typename } mutation B { ... { TestPersonCreate(data: {name: {value: "x"}}) { ok } } }',
    ),
    HiddenMutationCase(
        name="multi_operation_fragment_spread",
        query="query A { __typename } mutation B { ...Hidden }"
        ' fragment Hidden on Mutation { TestPersonCreate(data: {name: {value: "x"}}) { ok } }',
    ),
]
