from __future__ import annotations

import importlib.metadata

from infrahub_sdk.analyzer import GraphQLOperation, GraphQLQueryAnalyzer, GraphQLQueryVariable
from infrahub_sdk.batch import InfrahubBatch
from infrahub_sdk.branch import InfrahubBranchManager, InfrahubBranchManagerSync
from infrahub_sdk.client import InfrahubClient, InfrahubClientSync
from infrahub_sdk.config import Config
from infrahub_sdk.exceptions import (
    AuthenticationError,
    Error,
    FilterNotFound,
    GraphQLError,
    NodeNotFound,
    ServerNotReacheableError,
    ServerNotResponsiveError,
    ValidationError,
)
from infrahub_sdk.graphql import Mutation, Query
from infrahub_sdk.node import InfrahubNode, InfrahubNodeSync
from infrahub_sdk.schema import (
    AttributeSchema,
    InfrahubRepositoryConfig,
    InfrahubSchema,
    NodeSchema,
    RelationshipCardinality,
    RelationshipKind,
    RelationshipSchema,
    SchemaRoot,
)
from infrahub_sdk.store import NodeStore, NodeStoreSync
from infrahub_sdk.timestamp import Timestamp
from infrahub_sdk.uuidt import UUIDT, generate_uuid

__all__ = [
    "AttributeSchema",
    "AuthenticationError",
    "Config",
    "Error",
    "InfrahubBatch",
    "InfrahubBranchManager",
    "InfrahubBranchManagerSync",
    "InfrahubClient",
    "InfrahubClientSync",
    "InfrahubNode",
    "InfrahubNodeSync",
    "InfrahubRepositoryConfig",
    "InfrahubSchema",
    "FilterNotFound",
    "generate_uuid",
    "GraphQLQueryAnalyzer",
    "GraphQLQueryVariable",
    "GraphQLError",
    "GraphQLOperation",
    "NodeNotFound",
    "NodeSchema",
    "Mutation",
    "NodeStore",
    "NodeStoreSync",
    "Query",
    "RelationshipSchema",
    "RelationshipCardinality",
    "RelationshipKind",
    "SchemaRoot",
    "ServerNotReacheableError",
    "ServerNotResponsiveError",
    "Timestamp",
    "UUIDT",
    "ValidationError",
]

__version__ = importlib.metadata.version("infrahub-sdk")
