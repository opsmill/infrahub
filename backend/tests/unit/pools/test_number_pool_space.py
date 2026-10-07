import pytest
from structlog.testing import capture_logs

from infrahub.core.branch import Branch
from infrahub.core.schema import NodeSchema, SchemaRoot
from infrahub.core.schema.attribute_parameters import NumberAttributeParameters
from infrahub.core.schema.attribute_schema import AttributeSchema, NumberAttributeSchema
from infrahub.core.schema.manager import SchemaManager
from infrahub.pools.number_pool_space import SchemaAttributeDomains, attribute_domain
from infrahub.pools.number_ranges import NumberDomain, NumberSpan

MAIN = Branch(name="main")
FEATURE = Branch(name="feature")


def test_number_parameters_give_the_bounds_and_every_exclusion() -> None:
    attribute = NumberAttributeSchema(
        name="ticket_id",
        kind="Number",
        parameters=NumberAttributeParameters(min_value=10, max_value=30, excluded_values="12,14-16,20"),
    )

    assert attribute_domain(attribute=attribute) == NumberDomain(
        lower=10,
        upper=30,
        exclusions=(NumberSpan(start=12, end=12), NumberSpan(start=20, end=20), NumberSpan(start=14, end=16)),
    )


def test_an_attribute_without_number_parameters_is_unbounded() -> None:
    attribute = AttributeSchema(name="title", kind="Text")

    assert attribute_domain(attribute=attribute) == NumberDomain()


def test_a_missing_attribute_is_unbounded() -> None:
    assert attribute_domain(attribute=None) == NumberDomain()


def _ticket_schema(parameters: NumberAttributeParameters) -> SchemaRoot:
    ticket = NodeSchema(
        name="Ticket",
        namespace="Testing",
        attributes=[
            AttributeSchema(name="title", kind="Text"),
            NumberAttributeSchema(name="ticket_id", kind="Number", parameters=parameters),
        ],
    )
    return SchemaRoot(nodes=[ticket])


@pytest.fixture
def schema_manager() -> SchemaManager:
    """A schema whose ticket id is bounded on main and bounded differently on a feature branch."""
    schema_manager = SchemaManager()
    schema_manager.register_schema(
        schema=_ticket_schema(parameters=NumberAttributeParameters(min_value=1, max_value=100, excluded_values="50")),
        branch=MAIN.name,
    )
    schema_manager.register_schema(
        schema=_ticket_schema(parameters=NumberAttributeParameters(min_value=1, max_value=10)), branch=FEATURE.name
    )
    return schema_manager


@pytest.fixture
def domains(schema_manager: SchemaManager) -> SchemaAttributeDomains:
    return SchemaAttributeDomains(schema=schema_manager, branch=MAIN)


def test_the_domain_comes_from_the_attribute_the_pool_feeds_on_the_branch(
    schema_manager: SchemaManager, domains: SchemaAttributeDomains
) -> None:
    assert domains.domain_of(kind="TestingTicket", attribute_name="ticket_id") == NumberDomain(
        lower=1, upper=100, exclusions=(NumberSpan(start=50, end=50),)
    )
    feature_domains = SchemaAttributeDomains(schema=schema_manager, branch=FEATURE)
    assert feature_domains.domain_of(kind="TestingTicket", attribute_name="ticket_id") == NumberDomain(
        lower=1, upper=10
    )


def test_a_pool_feeding_a_kind_the_schema_no_longer_holds_is_unbounded(domains: SchemaAttributeDomains) -> None:
    with capture_logs() as records:
        domain = domains.domain_of(kind="TestingGone", attribute_name="ticket_id")

    assert domain == NumberDomain()
    assert records == [
        {
            "event": "Number pool feeds a kind missing from the schema, so it allocates from its full ranges without the attribute's limits",
            "log_level": "warning",
            "kind": "TestingGone",
            "attribute": "ticket_id",
            "branch": "main",
        }
    ]


def test_a_pool_feeding_an_attribute_the_kind_no_longer_holds_is_unbounded(domains: SchemaAttributeDomains) -> None:
    with capture_logs() as records:
        domain = domains.domain_of(kind="TestingTicket", attribute_name="gone")

    assert domain == NumberDomain()
    assert records == [
        {
            "event": "Number pool feeds an attribute missing from its kind, so it allocates from its full ranges without the attribute's limits",
            "log_level": "warning",
            "kind": "TestingTicket",
            "attribute": "gone",
            "branch": "main",
        }
    ]


def test_a_pool_feeding_a_non_number_attribute_is_unbounded(domains: SchemaAttributeDomains) -> None:
    assert domains.domain_of(kind="TestingTicket", attribute_name="title") == NumberDomain()
