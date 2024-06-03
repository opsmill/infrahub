# Generated by "invoke backend.generate", do not edit directly

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from enum import Enum

    from infrahub.core.attribute import (
        URL,
        Boolean,
        Dropdown,
        HashedPassword,
        Integer,
        IPHost,
        IPNetwork,
        JSONAttribute,
        ListAttribute,
        String,
    )
    from infrahub.core.relationship import RelationshipManager


class CoreNode(Protocol):
    id: str

    def get_id(self) -> str: ...
    def get_kind(self) -> str: ...
    async def save(self) -> None: ...


class LineageOwner(CoreNode):
    pass


class CoreProfile(CoreNode):
    profile_name: String
    profile_priority: Integer


class LineageSource(CoreNode):
    pass


class CoreComment(CoreNode):
    text: String
    created_at: String
    created_by: RelationshipManager


class CoreThread(CoreNode):
    label: String
    resolved: Boolean
    created_at: String
    change: RelationshipManager
    comments: RelationshipManager
    created_by: RelationshipManager


class CoreGroup(CoreNode):
    name: String
    label: String
    description: String
    members: RelationshipManager
    subscribers: RelationshipManager


class CoreValidator(CoreNode):
    label: String
    state: Enum
    conclusion: Enum
    completed_at: String
    started_at: String
    proposed_change: RelationshipManager
    checks: RelationshipManager


class CoreCheck(CoreNode):
    name: String
    label: String
    origin: String
    kind: String
    message: String
    conclusion: Enum
    severity: Enum
    created_at: String
    validator: RelationshipManager


class CoreTransformation(CoreNode):
    name: String
    label: String
    description: String
    timeout: Integer
    query: RelationshipManager
    repository: RelationshipManager
    tags: RelationshipManager


class CoreArtifactTarget(CoreNode):
    artifacts: RelationshipManager


class CoreTaskTarget(CoreNode):
    pass


class CoreWebhook(CoreNode):
    name: String
    description: String
    url: URL
    validate_certificates: Boolean


class CoreGenericRepository(CoreNode):
    name: String
    description: String
    location: String
    username: String
    password: String
    tags: RelationshipManager
    transformations: RelationshipManager
    queries: RelationshipManager
    checks: RelationshipManager
    generators: RelationshipManager


class BuiltinIPNamespace(CoreNode):
    name: String
    description: String
    ip_prefixes: RelationshipManager
    ip_addresses: RelationshipManager


class BuiltinIPPrefix(CoreNode):
    prefix: IPNetwork
    description: String
    member_type: Dropdown
    is_pool: Boolean
    is_top_level: Boolean
    utilization: Integer
    netmask: String
    hostmask: String
    network_address: String
    broadcast_address: String
    ip_namespace: RelationshipManager
    ip_addresses: RelationshipManager


class BuiltinIPAddress(CoreNode):
    address: IPHost
    description: String
    ip_namespace: RelationshipManager
    ip_prefix: RelationshipManager


class CoreResourcePool(CoreNode):
    name: String
    description: String


class CoreStandardGroup(CoreGroup):
    pass


class CoreGeneratorGroup(CoreGroup):
    pass


class CoreGraphQLQueryGroup(CoreGroup):
    parameters: JSONAttribute
    query: RelationshipManager


class BuiltinTag(CoreNode):
    name: String
    description: String


class CoreAccount(LineageOwner, LineageSource):
    name: String
    password: HashedPassword
    label: String
    description: String
    type: Enum
    role: Enum
    tokens: RelationshipManager


class InternalAccountToken(CoreNode):
    name: String
    token: String
    expiration: String
    account: RelationshipManager


class InternalRefreshToken(CoreNode):
    expiration: String
    account: RelationshipManager


class CoreProposedChange(CoreTaskTarget):
    name: String
    description: String
    source_branch: String
    destination_branch: String
    state: Enum
    approved_by: RelationshipManager
    reviewers: RelationshipManager
    created_by: RelationshipManager
    comments: RelationshipManager
    threads: RelationshipManager
    validations: RelationshipManager


class CoreChangeThread(CoreThread):
    pass


class CoreFileThread(CoreThread):
    file: String
    commit: String
    line_number: Integer
    repository: RelationshipManager


class CoreArtifactThread(CoreThread):
    artifact_id: String
    storage_id: String
    line_number: Integer


class CoreObjectThread(CoreThread):
    object_path: String


class CoreChangeComment(CoreComment):
    change: RelationshipManager


class CoreThreadComment(CoreComment):
    thread: RelationshipManager


class CoreRepository(LineageOwner, LineageSource, CoreGenericRepository, CoreTaskTarget):
    default_branch: String
    commit: String


class CoreReadOnlyRepository(LineageOwner, LineageSource, CoreGenericRepository, CoreTaskTarget):
    ref: String
    commit: String


class CoreTransformJinja2(CoreTransformation):
    template_path: String


class CoreDataCheck(CoreCheck):
    conflicts: JSONAttribute
    keep_branch: Enum


class CoreStandardCheck(CoreCheck):
    pass


class CoreSchemaCheck(CoreCheck):
    conflicts: JSONAttribute


class CoreFileCheck(CoreCheck):
    files: ListAttribute
    commit: String


class CoreArtifactCheck(CoreCheck):
    changed: Boolean
    checksum: String
    artifact_id: String
    storage_id: String
    line_number: Integer


class CoreGeneratorCheck(CoreCheck):
    instance: String


class CoreDataValidator(CoreValidator):
    pass


class CoreRepositoryValidator(CoreValidator):
    repository: RelationshipManager


class CoreUserValidator(CoreValidator):
    check_definition: RelationshipManager
    repository: RelationshipManager


class CoreSchemaValidator(CoreValidator):
    pass


class CoreArtifactValidator(CoreValidator):
    definition: RelationshipManager


class CoreGeneratorValidator(CoreValidator):
    definition: RelationshipManager


class CoreCheckDefinition(CoreTaskTarget):
    name: String
    description: String
    file_path: String
    class_name: String
    timeout: Integer
    parameters: JSONAttribute
    repository: RelationshipManager
    query: RelationshipManager
    targets: RelationshipManager
    tags: RelationshipManager


class CoreTransformPython(CoreTransformation):
    file_path: String
    class_name: String


class CoreGraphQLQuery(CoreNode):
    name: String
    description: String
    query: String
    variables: JSONAttribute
    operations: ListAttribute
    models: ListAttribute
    depth: Integer
    height: Integer
    repository: RelationshipManager
    tags: RelationshipManager


class CoreArtifact(CoreTaskTarget):
    name: String
    status: Enum
    content_type: Enum
    checksum: String
    storage_id: String
    parameters: JSONAttribute
    object: RelationshipManager
    definition: RelationshipManager


class CoreArtifactDefinition(CoreTaskTarget):
    name: String
    artifact_name: String
    description: String
    parameters: JSONAttribute
    content_type: Enum
    targets: RelationshipManager
    transformation: RelationshipManager


class CoreGeneratorDefinition(CoreTaskTarget):
    name: String
    description: String
    parameters: JSONAttribute
    file_path: String
    class_name: String
    convert_query_response: Boolean
    query: RelationshipManager
    repository: RelationshipManager
    targets: RelationshipManager


class CoreGeneratorInstance(CoreTaskTarget):
    name: String
    status: Enum
    object: RelationshipManager
    definition: RelationshipManager


class CoreStandardWebhook(CoreWebhook, CoreTaskTarget):
    shared_key: String


class CoreCustomWebhook(CoreWebhook, CoreTaskTarget):
    transformation: RelationshipManager


class IpamNamespace(BuiltinIPNamespace):
    default: Boolean


class CoreIPPrefixPool(CoreResourcePool, LineageSource):
    default_prefix_length: Integer
    default_member_type: Enum
    default_prefix_type: String
    resources: RelationshipManager
    ip_namespace: RelationshipManager


class CoreIPAddressPool(CoreResourcePool, LineageSource):
    default_address_type: String
    default_prefix_length: Integer
    resources: RelationshipManager
    ip_namespace: RelationshipManager
