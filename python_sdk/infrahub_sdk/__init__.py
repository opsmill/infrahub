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
    FilterNotFoundError,
    GraphQLError,
    NodeNotFoundError,
    ServerNotReachableError,
    ServerNotResponsiveError,
    ValidationError,
)
from infrahub_sdk.graphql import Mutation, Query
from infrahub_sdk.node import InfrahubNode, InfrahubNodeSync
from infrahub_sdk.schema import (
    AttributeSchema,
    GenericSchema,
    InfrahubRepositoryConfig,
    InfrahubSchema,
    MainSchemaTypes,
    NodeSchema,
    ProfileSchema,
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
    "FilterNotFoundError",
    "generate_uuid",
    "GenericSchema",
    "GraphQLQueryAnalyzer",
    "GraphQLQueryVariable",
    "GraphQLError",
    "GraphQLOperation",
    "MainSchemaTypes",
    "NodeNotFoundError",
    "NodeSchema",
    "Mutation",
    "NodeStore",
    "NodeStoreSync",
    "ProfileSchema",
    "Query",
    "RelationshipSchema",
    "RelationshipCardinality",
    "RelationshipKind",
    "SchemaRoot",
    "ServerNotReachableError",
    "ServerNotResponsiveError",
    "Timestamp",
    "UUIDT",
    "ValidationError",
]

__version__ = importlib.metadata.version("infrahub-sdk")
