from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.core.constants import GlobalPermissions, InfrahubKind, PermissionDecision
from infrahub.core.node import Node
from infrahub.dependencies.registry import build_component_registry

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreAccount
    from infrahub.database import InfrahubDatabase


@pytest.fixture(scope="module", autouse=True)
def load_component_dependency_registry() -> None:
    build_component_registry()


class PermissionsHelper:
    def __init__(self) -> None:
        self._first: CoreAccount | None = None
        self._second: CoreAccount | None = None
        self._default_branch: Branch | None = None

    @property
    def first(self) -> CoreAccount:
        if self._first:
            return self._first

        raise NotImplementedError()

    @property
    def second(self) -> CoreAccount:
        if self._second:
            return self._second

        raise NotImplementedError()

    @property
    def default_branch(self) -> Branch:
        if self._default_branch:
            return self._default_branch

        raise NotImplementedError()


@pytest.fixture(scope="module")
def permissions_helper() -> PermissionsHelper:
    return PermissionsHelper()


@pytest.fixture
def query_01() -> str:
    """Simple query with one document."""
    return """
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


@pytest.fixture
def query_02() -> str:
    return """
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


@pytest.fixture
def query_03() -> str:
    """Advanced Query with 2 documents."""
    return """
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


@pytest.fixture
def query_04() -> str:
    """Simple query with variables."""
    return """
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


@pytest.fixture
def query_05() -> str:
    return """
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


@pytest.fixture
def query_06() -> str:
    """Simple query with variables."""
    return """
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


@pytest.fixture
def bad_query_01() -> str:
    return """
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


@pytest.fixture
def query_introspection() -> str:
    return """
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


@pytest.fixture
async def session_global_prefs_manager(db: InfrahubDatabase, first_account: Node) -> AccountSession:
    """A session for an account granted the manage_global_preferences global permission via a role + group."""
    permission = await Node.init(db=db, schema=InfrahubKind.GLOBALPERMISSION)
    await permission.new(
        db=db,
        action=GlobalPermissions.MANAGE_GLOBAL_PREFERENCES.value,
        decision=PermissionDecision.ALLOW_ALL.value,
    )
    await permission.save(db=db)

    role = await Node.init(db=db, schema=InfrahubKind.ACCOUNTROLE)
    await role.new(db=db, name="prefs-manager", permissions=[permission])
    await role.save(db=db)

    group = await Node.init(db=db, schema=InfrahubKind.ACCOUNTGROUP)
    await group.new(db=db, name="prefs-managers", roles=[role])
    await group.save(db=db)

    await group.members.add(db=db, data={"id": first_account.id})  # type: ignore[attr-defined]
    await group.members.save(db=db)  # type: ignore[attr-defined]

    return AccountSession(authenticated=True, auth_type=AuthType.JWT, account_id=first_account.id)


@pytest.fixture
async def account_bob(db: InfrahubDatabase, default_branch: Branch) -> Node:
    bob = await Node.init(db=db, schema=InfrahubKind.ACCOUNT, branch=default_branch)
    await bob.new(db=db, name="bob", password=str(uuid4()))
    await bob.save(db=db)
    return bob


@pytest.fixture
async def account_bill(db: InfrahubDatabase, default_branch: Branch) -> Node:
    bill = await Node.init(db=db, schema=InfrahubKind.ACCOUNT, branch=default_branch)
    await bill.new(db=db, name="bill", password=str(uuid4()))
    await bill.save(db=db)
    return bill
