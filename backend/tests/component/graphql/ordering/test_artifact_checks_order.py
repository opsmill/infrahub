from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from infrahub.core.constants import NULL_VALUE, InfrahubKind
from infrahub.core.migrations.query.node_duplicate import NodeDuplicateQuery, SchemaNodeInfo
from infrahub.core.node import Node
from infrahub.core.query.node import NodeListGetAttributeQuery
from infrahub.graphql.initialization import prepare_graphql_params
from tests.helpers.graphql import graphql

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


@dataclass(frozen=True)
class CheckSetup:
    name: str
    node_id: str
    conclusion: str | None


ARTIFACT_CHECKS = (
    CheckSetup(name="zeta-unknown", node_id="00000000-0000-4000-8000-000000000001", conclusion="unknown"),
    CheckSetup(name="zulu-failure", node_id="00000000-0000-4000-8000-000000000002", conclusion="failure"),
    CheckSetup(name="alpha-success", node_id="00000000-0000-4000-8000-000000000003", conclusion="success"),
    CheckSetup(name="delta-unset", node_id="00000000-0000-4000-8000-000000000004", conclusion=None),
    CheckSetup(name="alpha-failure", node_id="00000000-0000-4000-8000-000000000005", conclusion="failure"),
    CheckSetup(name="beta-success", node_id="00000000-0000-4000-8000-000000000006", conclusion="success"),
    CheckSetup(name="middle-failure", node_id="00000000-0000-4000-8000-000000000007", conclusion="failure"),
)


@dataclass(frozen=True)
class ArtifactChecksDataset:
    artifact_validator_id: str
    schema_validator_id: str


class TestArtifactChecksOrder:
    @pytest.fixture(scope="class")
    async def dataset(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_core_models_schema_scope_class: SchemaBranch,
    ) -> ArtifactChecksDataset:
        proposed_change = await Node.init(db=db, schema=InfrahubKind.PROPOSEDCHANGE)
        await proposed_change.new(
            db=db, name="artifact-order", source_branch="artifact-order", destination_branch="main"
        )
        await proposed_change.save(db=db)
        repository = await Node.init(db=db, schema=InfrahubKind.REPOSITORY)
        await repository.new(db=db, name="artifact-order", location="https://github.com/test/artifacts.git")
        await repository.save(db=db)
        group = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
        await group.new(db=db, name="artifact-order-targets")
        await group.save(db=db)
        query = await Node.init(db=db, schema=InfrahubKind.GRAPHQLQUERY)
        await query.new(db=db, name="ArtifactOrderQuery", query="query { CoreRepository { edges { node { id } } } }")
        await query.save(db=db)
        transformation = await Node.init(db=db, schema=InfrahubKind.TRANSFORMJINJA2)
        await transformation.new(
            db=db, name="artifact-order-transform", query=query, repository=repository, template_path="template.j2"
        )
        await transformation.save(db=db)
        definition = await Node.init(db=db, schema=InfrahubKind.ARTIFACTDEFINITION)
        await definition.new(
            db=db,
            name="artifact-order-definition",
            artifact_name="configuration",
            content_type="text/plain",
            parameters={"value": {}},
            targets=group,
            transformation=transformation,
        )
        await definition.save(db=db)
        artifact_validator = await Node.init(db=db, schema=InfrahubKind.ARTIFACTVALIDATOR)
        await artifact_validator.new(db=db, proposed_change=proposed_change, definition=definition)
        await artifact_validator.save(db=db)
        schema_validator = await Node.init(db=db, schema=InfrahubKind.SCHEMAVALIDATOR)
        await schema_validator.new(db=db, proposed_change=proposed_change)
        await schema_validator.save(db=db)

        for setup in reversed(ARTIFACT_CHECKS):
            check = await Node.init(db=db, schema=InfrahubKind.ARTIFACTCHECK)
            await check.new(
                db=db,
                id=setup.node_id,
                name=setup.name,
                origin=repository.id,
                kind="ArtifactDefinition",
                conclusion={"value": setup.conclusion},
                validator=artifact_validator,
            )
            await check.save(db=db)
            if setup.conclusion is None:
                check.get_attribute("conclusion").value = None
                await check.save(db=db)
                attribute_query = await NodeListGetAttributeQuery.init(
                    db=db,
                    ids=[check.id],
                    branch=default_branch_scope_class,
                    fields={"conclusion": True},
                )
                await attribute_query.execute(db=db)
                conclusion, _ = attribute_query.get_result_by_id_and_name(node_id=check.id, attr_name="conclusion")
                assert conclusion.value == NULL_VALUE

        for setup in (
            CheckSetup(name="schema-failure", node_id="00000000-0000-4000-8000-000000000012", conclusion="failure"),
            CheckSetup(name="schema-success", node_id="00000000-0000-4000-8000-000000000011", conclusion="success"),
        ):
            check = await Node.init(db=db, schema=InfrahubKind.STANDARDCHECK)
            await check.new(
                db=db,
                id=setup.node_id,
                name=setup.name,
                origin=repository.id,
                kind="Schema",
                conclusion=setup.conclusion,
                validator=schema_validator,
            )
            await check.save(db=db)

        # Removing inherited labels retains the old vertex under the same UUID.
        await db.execute_query(
            query="MATCH (check:CoreArtifactCheck {uuid: $id}) SET check:CoreTaskTarget",
            params={"id": "00000000-0000-4000-8000-000000000005"},
        )
        check_schema = register_core_models_schema_scope_class.get_node(name=InfrahubKind.ARTIFACTCHECK)
        duplicate = await NodeDuplicateQuery.init(
            db=db,
            branch=default_branch_scope_class,
            kind_updates_map={
                InfrahubKind.ARTIFACTCHECK: SchemaNodeInfo(
                    name=check_schema.name,
                    namespace=check_schema.namespace,
                    branch_support=check_schema.branch.value,
                    labels=check_schema.get_labels(),
                    kind=check_schema.kind,
                )
            },
        )
        await duplicate.execute(db=db)
        assert duplicate.stats.get_counter(name="nodes_created") == 1
        default_branch_scope_class.update_schema_hash()
        return ArtifactChecksDataset(
            artifact_validator_id=artifact_validator.id,
            schema_validator_id=schema_validator.id,
        )

    async def test_failed_first_orders_all_checks_before_taking_each_page(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, dataset: ArtifactChecksDataset
    ) -> None:
        query = """
        query($id: ID!, $offset: Int!) {
            CoreValidator(ids: [$id]) {
                edges {
                    node {
                        ... on CoreArtifactValidator {
                            checks(failed_first: true, offset: $offset, limit: 2) {
                                count
                                edges { node { name { value } } }
                            }
                        }
                    }
                }
            }
        }
        """
        expected_pages = (
            ["zulu-failure", "alpha-failure"],
            ["middle-failure", "zeta-unknown"],
            ["alpha-success", "delta-unset"],
            ["beta-success"],
        )
        for page, expected_checks in enumerate(expected_pages):
            gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)
            result = await graphql(
                schema=gql_params.schema,
                source=query,
                context_value=gql_params.context,
                variable_values={"id": dataset.artifact_validator_id, "offset": page * 2},
            )
            assert result.errors is None
            assert result.data is not None
            checks = result.data["CoreValidator"]["edges"][0]["node"]["checks"]
            assert checks["count"] == 7
            assert [edge["node"]["name"]["value"] for edge in checks["edges"]] == expected_checks

    async def test_aliases_keep_failed_first_separate_from_default_and_disabled_ordering(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, dataset: ArtifactChecksDataset
    ) -> None:
        query = """
        query($id: ID!) {
            CoreArtifactValidator(ids: [$id]) {
                edges {
                    node {
                        failed: checks(failed_first: true) { edges { node { name { value } } } }
                        default: checks { edges { node { name { value } } } }
                        disabled: checks(failed_first: false) { edges { node { name { value } } } }
                        failedAgain: checks(failed_first: true) { edges { node { name { value } } } }
                    }
                }
            }
        }
        """
        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)
        result = await graphql(
            schema=gql_params.schema,
            source=query,
            context_value=gql_params.context,
            variable_values={"id": dataset.artifact_validator_id},
        )
        assert result.errors is None
        assert result.data is not None
        validator = result.data["CoreArtifactValidator"]["edges"][0]["node"]
        actual = {
            alias: [edge["node"]["name"]["value"] for edge in connection["edges"]]
            for alias, connection in validator.items()
        }
        default_names = [
            "zeta-unknown",
            "zulu-failure",
            "alpha-success",
            "delta-unset",
            "alpha-failure",
            "beta-success",
            "middle-failure",
        ]
        failed_first_names = [
            "zulu-failure",
            "alpha-failure",
            "middle-failure",
            "zeta-unknown",
            "alpha-success",
            "delta-unset",
            "beta-success",
        ]
        assert actual == {
            "failed": failed_first_names,
            "default": default_names,
            "disabled": default_names,
            "failedAgain": failed_first_names,
        }

    async def test_other_validator_checks_keep_uuid_order_without_failed_first_argument(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, dataset: ArtifactChecksDataset
    ) -> None:
        query = """
        query($id: ID!) {
            CoreSchemaValidator(ids: [$id]) {
                edges { node { checks { edges { node { name { value } } } } } }
            }
        }
        """
        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)
        result = await graphql(
            schema=gql_params.schema,
            source=query,
            context_value=gql_params.context,
            variable_values={"id": dataset.schema_validator_id},
        )
        assert result.errors is None
        assert result.data is not None
        checks = result.data["CoreSchemaValidator"]["edges"][0]["node"]["checks"]["edges"]
        assert [edge["node"]["name"]["value"] for edge in checks] == ["schema-success", "schema-failure"]

        for kind in ("CoreSchemaValidator", "CoreValidator"):
            result = await graphql(
                schema=gql_params.schema,
                source=f"""
                    query($id: ID!) {{
                        {kind}(ids: [$id]) {{
                            edges {{ node {{ checks(failed_first: true) {{ count }} }} }}
                        }}
                    }}
                """,
                context_value=gql_params.context,
                variable_values={"id": dataset.schema_validator_id},
            )
            assert result.errors is not None
            assert [error.message for error in result.errors] == [
                f"Unknown argument 'failed_first' on field '{kind}.checks'."
            ]

    async def test_failed_first_rejects_explicit_order_but_accepts_empty_order(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, dataset: ArtifactChecksDataset
    ) -> None:
        query = """
        query($id: ID!, $order: OrderInput) {
            CoreArtifactValidator(ids: [$id]) {
                edges {
                    node {
                        checks(failed_first: true, order: $order, limit: 2) {
                            edges { node { name { value } } }
                        }
                    }
                }
            }
        }
        """
        for order in (
            {"by": [{"field": "name__value", "direction": "ASC"}]},
            {"node_metadata": {"created_at": "DESC"}},
            {"disable": True},
        ):
            gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)
            result = await graphql(
                schema=gql_params.schema,
                source=query,
                context_value=gql_params.context,
                variable_values={"id": dataset.artifact_validator_id, "order": order},
            )
            assert result.errors is not None
            assert [error.message for error in result.errors] == [
                "failed_first cannot be combined with an explicit order"
            ]

        for order in ({}, {"disable": False}):
            gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)
            result = await graphql(
                schema=gql_params.schema,
                source=query,
                context_value=gql_params.context,
                variable_values={"id": dataset.artifact_validator_id, "order": order},
            )
            assert result.errors is None
            assert result.data is not None
            checks = result.data["CoreArtifactValidator"]["edges"][0]["node"]["checks"]["edges"]
            assert [edge["node"]["name"]["value"] for edge in checks] == ["zulu-failure", "alpha-failure"]
