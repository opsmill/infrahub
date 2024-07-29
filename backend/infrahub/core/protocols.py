# Generated by "invoke backend.generate", do not edit directly

from __future__ import annotations

from typing import TYPE_CHECKING

from .protocols_base import CoreNode

if TYPE_CHECKING:
    from enum import Enum

    from infrahub.core.attribute import (
        URL,
        Boolean,
        BooleanOptional,
        DateTime,
        DateTimeOptional,
        Dropdown,
        HashedPassword,
        Integer,
        IntegerOptional,
        IPHost,
        IPNetwork,
        JSONAttribute,
        JSONAttributeOptional,
        ListAttributeOptional,
        String,
        StringOptional,
    )
    from infrahub.core.relationship import RelationshipManager


class BuiltinIPAddress(CoreNode):
    address: IPHost
    description: StringOptional
    ip_namespace: RelationshipManager
    ip_prefix: RelationshipManager


class BuiltinIPNamespace(CoreNode):
    name: String
    description: StringOptional
    ip_prefixes: RelationshipManager
    ip_addresses: RelationshipManager


class BuiltinIPPrefix(CoreNode):
    prefix: IPNetwork
    description: StringOptional
    member_type: Dropdown
    is_pool: Boolean
    is_top_level: BooleanOptional
    utilization: IntegerOptional
    netmask: StringOptional
    hostmask: StringOptional
    network_address: StringOptional
    broadcast_address: StringOptional
    ip_namespace: RelationshipManager
    ip_addresses: RelationshipManager
    resource_pool: RelationshipManager
    parent: RelationshipManager
    children: RelationshipManager


class CoreArtifactTarget(CoreNode):
    artifacts: RelationshipManager


class CoreCheck(CoreNode):
    name: StringOptional
    label: StringOptional
    origin: String
    kind: String
    message: StringOptional
    conclusion: Enum
    severity: Enum
    created_at: DateTimeOptional
    validator: RelationshipManager


class CoreComment(CoreNode):
    text: String
    created_at: DateTimeOptional
    created_by: RelationshipManager


class CoreGenericAccount(CoreNode):
    name: String
    password: HashedPassword
    label: StringOptional
    description: StringOptional
    account_type: Enum
    role: Enum
    tokens: RelationshipManager


class CoreGenericRepository(CoreNode):
    name: String
    description: StringOptional
    location: String
    username: StringOptional
    password: StringOptional
    admin_status: Dropdown
    tags: RelationshipManager
    transformations: RelationshipManager
    queries: RelationshipManager
    checks: RelationshipManager
    generators: RelationshipManager


class CoreGroup(CoreNode):
    name: String
    label: StringOptional
    description: StringOptional
    group_type: Enum
    members: RelationshipManager
    subscribers: RelationshipManager
    parent: RelationshipManager
    children: RelationshipManager


class CoreProfile(CoreNode):
    profile_name: String
    profile_priority: IntegerOptional


class CoreResourcePool(CoreNode):
    name: String
    description: StringOptional


class CoreTaskTarget(CoreNode):
    pass


class CoreThread(CoreNode):
    label: StringOptional
    resolved: Boolean
    created_at: DateTimeOptional
    change: RelationshipManager
    comments: RelationshipManager
    created_by: RelationshipManager


class CoreTransformation(CoreNode):
    name: String
    label: StringOptional
    description: StringOptional
    timeout: Integer
    query: RelationshipManager
    repository: RelationshipManager
    tags: RelationshipManager


class CoreValidator(CoreNode):
    label: StringOptional
    state: Enum
    conclusion: Enum
    completed_at: DateTimeOptional
    started_at: DateTimeOptional
    proposed_change: RelationshipManager
    checks: RelationshipManager


class CoreWebhook(CoreNode):
    name: String
    description: StringOptional
    url: URL
    validate_certificates: BooleanOptional


class LineageOwner(CoreNode):
    pass


class LineageSource(CoreNode):
    pass


class BuiltinTag(CoreNode):
    name: String
    description: StringOptional


class CoreAccount(LineageOwner, LineageSource, CoreGenericAccount):
    pass


class CoreArtifact(CoreTaskTarget):
    name: String
    status: Enum
    content_type: Enum
    checksum: StringOptional
    storage_id: StringOptional
    parameters: JSONAttributeOptional
    object: RelationshipManager
    definition: RelationshipManager


class CoreArtifactCheck(CoreCheck):
    changed: BooleanOptional
    checksum: StringOptional
    artifact_id: StringOptional
    storage_id: StringOptional
    line_number: IntegerOptional


class CoreArtifactDefinition(CoreTaskTarget):
    name: String
    artifact_name: String
    description: StringOptional
    parameters: JSONAttribute
    content_type: Enum
    targets: RelationshipManager
    transformation: RelationshipManager


class CoreArtifactThread(CoreThread):
    artifact_id: StringOptional
    storage_id: StringOptional
    line_number: IntegerOptional


class CoreArtifactValidator(CoreValidator):
    definition: RelationshipManager


class CoreChangeComment(CoreComment):
    change: RelationshipManager


class CoreChangeThread(CoreThread):
    pass


class CoreCheckDefinition(CoreTaskTarget):
    name: String
    description: StringOptional
    file_path: String
    class_name: String
    timeout: Integer
    parameters: JSONAttributeOptional
    repository: RelationshipManager
    query: RelationshipManager
    targets: RelationshipManager
    tags: RelationshipManager


class CoreCustomWebhook(CoreWebhook, CoreTaskTarget):
    transformation: RelationshipManager


class CoreDataCheck(CoreCheck):
    conflicts: JSONAttribute
    keep_branch: Enum


class CoreDataValidator(CoreValidator):
    pass


class CoreFileCheck(CoreCheck):
    files: ListAttributeOptional
    commit: StringOptional


class CoreFileThread(CoreThread):
    file: StringOptional
    commit: StringOptional
    line_number: IntegerOptional
    repository: RelationshipManager


class CoreGeneratorCheck(CoreCheck):
    instance: String


class CoreGeneratorDefinition(CoreTaskTarget):
    name: String
    description: StringOptional
    parameters: JSONAttribute
    file_path: String
    class_name: String
    convert_query_response: BooleanOptional
    query: RelationshipManager
    repository: RelationshipManager
    targets: RelationshipManager


class CoreGeneratorGroup(CoreGroup):
    pass


class CoreGeneratorInstance(CoreTaskTarget):
    name: String
    status: Enum
    object: RelationshipManager
    definition: RelationshipManager


class CoreGeneratorValidator(CoreValidator):
    definition: RelationshipManager


class CoreGraphQLQuery(CoreNode):
    name: String
    description: StringOptional
    query: String
    variables: JSONAttributeOptional
    operations: ListAttributeOptional
    models: ListAttributeOptional
    depth: IntegerOptional
    height: IntegerOptional
    repository: RelationshipManager
    tags: RelationshipManager


class CoreGraphQLQueryGroup(CoreGroup):
    parameters: JSONAttributeOptional
    query: RelationshipManager


class CoreIPAddressPool(CoreResourcePool, LineageSource):
    default_address_type: String
    default_prefix_length: IntegerOptional
    resources: RelationshipManager
    ip_namespace: RelationshipManager


class CoreIPPrefixPool(CoreResourcePool, LineageSource):
    default_prefix_length: IntegerOptional
    default_member_type: Enum
    default_prefix_type: StringOptional
    resources: RelationshipManager
    ip_namespace: RelationshipManager


class CoreNumberPool(CoreResourcePool, LineageSource):
    node: String
    node_attribute: String
    start_range: Integer
    end_range: Integer


class CoreObjectThread(CoreThread):
    object_path: String


class CoreProposedChange(CoreTaskTarget):
    name: String
    description: StringOptional
    source_branch: String
    destination_branch: String
    state: Enum
    approved_by: RelationshipManager
    reviewers: RelationshipManager
    created_by: RelationshipManager
    comments: RelationshipManager
    threads: RelationshipManager
    validations: RelationshipManager


class CoreReadOnlyRepository(LineageOwner, LineageSource, CoreGenericRepository, CoreTaskTarget):
    ref: String
    commit: StringOptional


class CoreRepository(LineageOwner, LineageSource, CoreGenericRepository, CoreTaskTarget):
    default_branch: String
    commit: StringOptional


class CoreRepositoryValidator(CoreValidator):
    repository: RelationshipManager


class CoreSchemaCheck(CoreCheck):
    conflicts: JSONAttribute


class CoreSchemaValidator(CoreValidator):
    pass


class CoreStandardCheck(CoreCheck):
    pass


class CoreStandardGroup(CoreGroup):
    pass


class CoreStandardWebhook(CoreWebhook, CoreTaskTarget):
    shared_key: String


class CoreThreadComment(CoreComment):
    thread: RelationshipManager


class CoreTransformJinja2(CoreTransformation):
    template_path: String


class CoreTransformPython(CoreTransformation):
    file_path: String
    class_name: String


class CoreUserValidator(CoreValidator):
    check_definition: RelationshipManager
    repository: RelationshipManager


class InternalAccountToken(CoreNode):
    name: StringOptional
    token: String
    expiration: DateTimeOptional
    account: RelationshipManager


class InternalRefreshToken(CoreNode):
    expiration: DateTime
    account: RelationshipManager


class IpamNamespace(BuiltinIPNamespace):
    default: BooleanOptional
