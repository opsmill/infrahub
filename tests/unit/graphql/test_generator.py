from infrahub.graphql.generator import (
    generate_graphql_mutation_create,
    generate_graphql_mutation_update,
    generate_graphql_object,
)


def test_generate_graphql_object(default_branch, criticality_schema):

    result = generate_graphql_object(criticality_schema)
    assert result._meta.name == "Criticality"
    assert sorted(list(result._meta.fields.keys())) == ["color", "description", "id", "level", "name"]


def test_generate_graphql_mutation_create(default_branch, criticality_schema):

    result = generate_graphql_mutation_create(criticality_schema)
    assert result._meta.name == "CriticalityCreate"
    assert sorted(list(result._meta.fields.keys())) == ["object", "ok"]


def test_generate_graphql_mutation_update(default_branch, criticality_schema):

    result = generate_graphql_mutation_update(criticality_schema)
    assert result._meta.name == "CriticalityUpdate"
    assert sorted(list(result._meta.fields.keys())) == ["object", "ok"]
