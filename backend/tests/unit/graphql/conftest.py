import pytest

from infrahub.dependencies.registry import build_component_registry


@pytest.fixture(scope="module", autouse=True)
def load_component_dependency_registry():
    build_component_registry()


@pytest.fixture
def query_01() -> str:
    """Simple query with one document"""
    query = """
    query {
        TestPerson {
            edges {
                node {
                    name {
                        value
                    }
                    cars {
                        edges {
                            node {
                                name {
                                    value
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    """
    return query


@pytest.fixture
def query_02() -> str:
    query = """
    query {
        TestPerson {
            edges {
                node {
                    name {
                        value
                    }

                    cars {
                        edges {
                            node {
                                name {
                                    value
                                }
                                ... on TestElectricCar {
                                    nbr_engine {
                                        value
                                    }
                                    member_of_groups {
                                        edges {
                                            node {
                                                id
                                            }
                                        }
                                    }
                                }
                                ... on TestGazCar {
                                    mpg {
                                        value
                                        is_protected
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    """
    return query


@pytest.fixture
def query_03() -> str:
    """Advanced Query with 2 documents"""
    query = """
    query FirstQuery {
        TestPerson {
            edges {
                node {
                    name {
                        value
                    }
                    cars {
                        edges {
                            node {
                                name {
                                    value
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    mutation FirstMutation {
        TestPersonCreate(
            data: {
                name: { value: "person1"}
            }
        ){
            ok
            object {
                id
            }
        }
    }
    """
    return query


@pytest.fixture
def query_04() -> str:
    """Simple query with variables"""
    query = """
    query ($person: String!){
        TestPerson(name__value: $person) {
            edges {
                node {
                    name {
                        value
                    }
                }
            }
        }
    }
    """
    return query


@pytest.fixture
def query_05() -> str:
    query = """
    query MyQuery {
        CoreRepository {
            edges {
                node {
                    name {
                        value
                    }
                    tags {
                        edges {
                            node {
                                id
                            }
                        }
                    }
                }
            }
        }
    }
    mutation MyMutation($myvar: String) {
        CoreRepositoryCreate (data: {
            name: { value: $myvar},
            location: { value: "location1"},
        }) {
            ok
        }
    }
    """

    return query


@pytest.fixture
def query_06() -> str:
    """Simple query with variables"""
    query = """
    query (
        $str1: String,
        $str2: String = "default2",
        $str3: String!
        $int1: Int,
        $int2: Int = 12,
        $int3: Int!
        $bool1: Boolean,
        $bool2: Boolean = true,
        $bool3: Boolean!
    ){
        TestPerson(name__value: $person) {
            edges {
                node {
                    name {
                        value
                    }
                }
            }
        }
    }
    """
    return query


@pytest.fixture
def bad_query_01() -> str:
    query = """
    query {
        TestPerson {
            edges {
                node {
                    name {
                        value
                    }
                    cars {
                        edges {
                            node {
                                name {
                                    value
                                }
                            }
                        }
                    }
                }
            }
    """
    return query


@pytest.fixture
def query_introspection() -> str:
    query = """
        query IntrospectionQuery {
            __schema {
                queryType {
                    name
                }
                mutationType {
                    name
                }
                subscriptionType {
                    name
                }
                types {
                    ...FullType
                }
                directives {
                    name
                    description
                    locations
                    args {
                        ...InputValue
                    }
                }
            }
        }

        fragment FullType on __Type {
            kind
            name
            description
            fields(includeDeprecated: true) {
                name
                description
                args {
                    ...InputValue
                }
                type {
                    ...TypeRef
                }
                isDeprecated
                deprecationReason
            }
            inputFields {
                ...InputValue
            }
            interfaces {
                ...TypeRef
            }
            enumValues(includeDeprecated: true) {
                name
                description
                isDeprecated
                deprecationReason
            }
            possibleTypes {
                ...TypeRef
            }
        }

        fragment InputValue on __InputValue {
            name
            description
            type {
                ...TypeRef
            }
                defaultValue
            }

            fragment TypeRef on __Type {
            kind
            name
            ofType {
                kind
                name
                ofType {
                    kind
                    name
                    ofType {
                        kind
                        name
                        ofType {
                            kind
                            name
                            ofType {
                                kind
                                name
                                ofType {
                                    kind
                                    name
                                    ofType {
                                        kind
                                        name
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    """
    return query
