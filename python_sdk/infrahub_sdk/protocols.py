# Generated by "invoke backend.generate", do not edit directly

from __future__ import annotations

from typing import TYPE_CHECKING

from .protocols_base import CoreNode, CoreNodeSync

if TYPE_CHECKING:
    from infrahub_sdk.node import RelatedNode, RelatedNodeSync, RelationshipManager, RelationshipManagerSync

    from .protocols_base import (
        URL,
        Boolean,
        BooleanOptional,
        DateTime,
        DateTimeOptional,
        Dropdown,
        Enum,
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

# pylint: disable=too-many-ancestors

# ---------------------------------------------
# ASYNC
# ---------------------------------------------


class BuiltinIPAddress(CoreNode):
    address: IPHost
    description: StringOptional
    ip_namespace: RelatedNode
    ip_prefix: RelatedNode


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
    ip_namespace: RelatedNode
    ip_addresses: RelationshipManager
    resource_pool: RelationshipManager
    parent: RelatedNode
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
    validator: RelatedNode


class CoreComment(CoreNode):
    text: String
    created_at: DateTimeOptional
    created_by: RelatedNode


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
    parent: RelatedNode
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
    change: RelatedNode
    comments: RelationshipManager
    created_by: RelatedNode


class CoreTransformation(CoreNode):
    name: String
    label: StringOptional
    description: StringOptional
    timeout: Integer
    query: RelatedNode
    repository: RelatedNode
    tags: RelationshipManager


class CoreValidator(CoreNode):
    label: StringOptional
    state: Enum
    conclusion: Enum
    completed_at: DateTimeOptional
    started_at: DateTimeOptional
    proposed_change: RelatedNode
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
    object: RelatedNode
    definition: RelatedNode


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
    targets: RelatedNode
    transformation: RelatedNode


class CoreArtifactThread(CoreThread):
    artifact_id: StringOptional
    storage_id: StringOptional
    line_number: IntegerOptional


class CoreArtifactValidator(CoreValidator):
    definition: RelatedNode


class CoreChangeComment(CoreComment):
    change: RelatedNode


class CoreChangeThread(CoreThread):
    pass


class CoreCheckDefinition(CoreTaskTarget):
    name: String
    description: StringOptional
    file_path: String
    class_name: String
    timeout: Integer
    parameters: JSONAttributeOptional
    repository: RelatedNode
    query: RelatedNode
    targets: RelatedNode
    tags: RelationshipManager


class CoreCustomWebhook(CoreWebhook, CoreTaskTarget):
    transformation: RelatedNode


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
    repository: RelatedNode


class CoreGeneratorCheck(CoreCheck):
    instance: String


class CoreGeneratorDefinition(CoreTaskTarget):
    name: String
    description: StringOptional
    parameters: JSONAttribute
    file_path: String
    class_name: String
    convert_query_response: BooleanOptional
    query: RelatedNode
    repository: RelatedNode
    targets: RelatedNode


class CoreGeneratorGroup(CoreGroup):
    pass


class CoreGeneratorInstance(CoreTaskTarget):
    name: String
    status: Enum
    object: RelatedNode
    definition: RelatedNode


class CoreGeneratorValidator(CoreValidator):
    definition: RelatedNode


class CoreGraphQLQuery(CoreNode):
    name: String
    description: StringOptional
    query: String
    variables: JSONAttributeOptional
    operations: ListAttributeOptional
    models: ListAttributeOptional
    depth: IntegerOptional
    height: IntegerOptional
    repository: RelatedNode
    tags: RelationshipManager


class CoreGraphQLQueryGroup(CoreGroup):
    parameters: JSONAttributeOptional
    query: RelatedNode


class CoreIPAddressPool(CoreResourcePool, LineageSource):
    default_address_type: String
    default_prefix_length: IntegerOptional
    resources: RelationshipManager
    ip_namespace: RelatedNode


class CoreIPPrefixPool(CoreResourcePool, LineageSource):
    default_prefix_length: IntegerOptional
    default_member_type: Enum
    default_prefix_type: StringOptional
    resources: RelationshipManager
    ip_namespace: RelatedNode


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
    created_by: RelatedNode
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
    repository: RelatedNode


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
    thread: RelatedNode


class CoreTransformJinja2(CoreTransformation):
    template_path: String


class CoreTransformPython(CoreTransformation):
    file_path: String
    class_name: String


class CoreUserValidator(CoreValidator):
    check_definition: RelatedNode
    repository: RelatedNode


class InternalAccountToken(CoreNode):
    name: StringOptional
    token: String
    expiration: DateTimeOptional
    account: RelatedNode


class InternalRefreshToken(CoreNode):
    expiration: DateTime
    account: RelatedNode


class IpamNamespace(BuiltinIPNamespace):
    default: BooleanOptional


# ---------------------------------------------
# SYNC
# ---------------------------------------------


class BuiltinIPAddressSync(CoreNodeSync):
    address: IPHost
    description: StringOptional
    ip_namespace: RelatedNodeSync
    ip_prefix: RelatedNodeSync


class BuiltinIPNamespaceSync(CoreNodeSync):
    name: String
    description: StringOptional
    ip_prefixes: RelationshipManagerSync
    ip_addresses: RelationshipManagerSync


class BuiltinIPPrefixSync(CoreNodeSync):
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
    ip_namespace: RelatedNodeSync
    ip_addresses: RelationshipManagerSync
    resource_pool: RelationshipManagerSync
    parent: RelatedNodeSync
    children: RelationshipManagerSync


class CoreArtifactTargetSync(CoreNodeSync):
    artifacts: RelationshipManagerSync


class CoreCheckSync(CoreNodeSync):
    name: StringOptional
    label: StringOptional
    origin: String
    kind: String
    message: StringOptional
    conclusion: Enum
    severity: Enum
    created_at: DateTimeOptional
    validator: RelatedNodeSync


class CoreCommentSync(CoreNodeSync):
    text: String
    created_at: DateTimeOptional
    created_by: RelatedNodeSync


class CoreGenericAccountSync(CoreNodeSync):
    name: String
    password: HashedPassword
    label: StringOptional
    description: StringOptional
    account_type: Enum
    role: Enum
    tokens: RelationshipManagerSync


class CoreGenericRepositorySync(CoreNodeSync):
    name: String
    description: StringOptional
    location: String
    username: StringOptional
    password: StringOptional
    admin_status: Dropdown
    tags: RelationshipManagerSync
    transformations: RelationshipManagerSync
    queries: RelationshipManagerSync
    checks: RelationshipManagerSync
    generators: RelationshipManagerSync


class CoreGroupSync(CoreNodeSync):
    name: String
    label: StringOptional
    description: StringOptional
    group_type: Enum
    members: RelationshipManagerSync
    subscribers: RelationshipManagerSync
    parent: RelatedNodeSync
    children: RelationshipManagerSync


class CoreProfileSync(CoreNodeSync):
    profile_name: String
    profile_priority: IntegerOptional


class CoreResourcePoolSync(CoreNodeSync):
    name: String
    description: StringOptional


class CoreTaskTargetSync(CoreNodeSync):
    pass


class CoreThreadSync(CoreNodeSync):
    label: StringOptional
    resolved: Boolean
    created_at: DateTimeOptional
    change: RelatedNodeSync
    comments: RelationshipManagerSync
    created_by: RelatedNodeSync


class CoreTransformationSync(CoreNodeSync):
    name: String
    label: StringOptional
    description: StringOptional
    timeout: Integer
    query: RelatedNodeSync
    repository: RelatedNodeSync
    tags: RelationshipManagerSync


class CoreValidatorSync(CoreNodeSync):
    label: StringOptional
    state: Enum
    conclusion: Enum
    completed_at: DateTimeOptional
    started_at: DateTimeOptional
    proposed_change: RelatedNodeSync
    checks: RelationshipManagerSync


class CoreWebhookSync(CoreNodeSync):
    name: String
    description: StringOptional
    url: URL
    validate_certificates: BooleanOptional


class LineageOwnerSync(CoreNodeSync):
    pass


class LineageSourceSync(CoreNodeSync):
    pass


class BuiltinTagSync(CoreNodeSync):
    name: String
    description: StringOptional


class CoreAccountSync(LineageOwnerSync, LineageSourceSync, CoreGenericAccountSync):
    pass


class CoreArtifactSync(CoreTaskTargetSync):
    name: String
    status: Enum
    content_type: Enum
    checksum: StringOptional
    storage_id: StringOptional
    parameters: JSONAttributeOptional
    object: RelatedNodeSync
    definition: RelatedNodeSync


class CoreArtifactCheckSync(CoreCheckSync):
    changed: BooleanOptional
    checksum: StringOptional
    artifact_id: StringOptional
    storage_id: StringOptional
    line_number: IntegerOptional


class CoreArtifactDefinitionSync(CoreTaskTargetSync):
    name: String
    artifact_name: String
    description: StringOptional
    parameters: JSONAttribute
    content_type: Enum
    targets: RelatedNodeSync
    transformation: RelatedNodeSync


class CoreArtifactThreadSync(CoreThreadSync):
    artifact_id: StringOptional
    storage_id: StringOptional
    line_number: IntegerOptional


class CoreArtifactValidatorSync(CoreValidatorSync):
    definition: RelatedNodeSync


class CoreChangeCommentSync(CoreCommentSync):
    change: RelatedNodeSync


class CoreChangeThreadSync(CoreThreadSync):
    pass


class CoreCheckDefinitionSync(CoreTaskTargetSync):
    name: String
    description: StringOptional
    file_path: String
    class_name: String
    timeout: Integer
    parameters: JSONAttributeOptional
    repository: RelatedNodeSync
    query: RelatedNodeSync
    targets: RelatedNodeSync
    tags: RelationshipManagerSync


class CoreCustomWebhookSync(CoreWebhookSync, CoreTaskTargetSync):
    transformation: RelatedNodeSync


class CoreDataCheckSync(CoreCheckSync):
    conflicts: JSONAttribute
    keep_branch: Enum


class CoreDataValidatorSync(CoreValidatorSync):
    pass


class CoreFileCheckSync(CoreCheckSync):
    files: ListAttributeOptional
    commit: StringOptional


class CoreFileThreadSync(CoreThreadSync):
    file: StringOptional
    commit: StringOptional
    line_number: IntegerOptional
    repository: RelatedNodeSync


class CoreGeneratorCheckSync(CoreCheckSync):
    instance: String


class CoreGeneratorDefinitionSync(CoreTaskTargetSync):
    name: String
    description: StringOptional
    parameters: JSONAttribute
    file_path: String
    class_name: String
    convert_query_response: BooleanOptional
    query: RelatedNodeSync
    repository: RelatedNodeSync
    targets: RelatedNodeSync


class CoreGeneratorGroupSync(CoreGroupSync):
    pass


class CoreGeneratorInstanceSync(CoreTaskTargetSync):
    name: String
    status: Enum
    object: RelatedNodeSync
    definition: RelatedNodeSync


class CoreGeneratorValidatorSync(CoreValidatorSync):
    definition: RelatedNodeSync


class CoreGraphQLQuerySync(CoreNodeSync):
    name: String
    description: StringOptional
    query: String
    variables: JSONAttributeOptional
    operations: ListAttributeOptional
    models: ListAttributeOptional
    depth: IntegerOptional
    height: IntegerOptional
    repository: RelatedNodeSync
    tags: RelationshipManagerSync


class CoreGraphQLQueryGroupSync(CoreGroupSync):
    parameters: JSONAttributeOptional
    query: RelatedNodeSync


class CoreIPAddressPoolSync(CoreResourcePoolSync, LineageSourceSync):
    default_address_type: String
    default_prefix_length: IntegerOptional
    resources: RelationshipManagerSync
    ip_namespace: RelatedNodeSync


class CoreIPPrefixPoolSync(CoreResourcePoolSync, LineageSourceSync):
    default_prefix_length: IntegerOptional
    default_member_type: Enum
    default_prefix_type: StringOptional
    resources: RelationshipManagerSync
    ip_namespace: RelatedNodeSync


class CoreNumberPoolSync(CoreResourcePoolSync, LineageSourceSync):
    node: String
    node_attribute: String
    start_range: Integer
    end_range: Integer


class CoreObjectThreadSync(CoreThreadSync):
    object_path: String


class CoreProposedChangeSync(CoreTaskTargetSync):
    name: String
    description: StringOptional
    source_branch: String
    destination_branch: String
    state: Enum
    approved_by: RelationshipManagerSync
    reviewers: RelationshipManagerSync
    created_by: RelatedNodeSync
    comments: RelationshipManagerSync
    threads: RelationshipManagerSync
    validations: RelationshipManagerSync


class CoreReadOnlyRepositorySync(LineageOwnerSync, LineageSourceSync, CoreGenericRepositorySync, CoreTaskTargetSync):
    ref: String
    commit: StringOptional


class CoreRepositorySync(LineageOwnerSync, LineageSourceSync, CoreGenericRepositorySync, CoreTaskTargetSync):
    default_branch: String
    commit: StringOptional


class CoreRepositoryValidatorSync(CoreValidatorSync):
    repository: RelatedNodeSync


class CoreSchemaCheckSync(CoreCheckSync):
    conflicts: JSONAttribute


class CoreSchemaValidatorSync(CoreValidatorSync):
    pass


class CoreStandardCheckSync(CoreCheckSync):
    pass


class CoreStandardGroupSync(CoreGroupSync):
    pass


class CoreStandardWebhookSync(CoreWebhookSync, CoreTaskTargetSync):
    shared_key: String


class CoreThreadCommentSync(CoreCommentSync):
    thread: RelatedNodeSync


class CoreTransformJinja2Sync(CoreTransformationSync):
    template_path: String


class CoreTransformPythonSync(CoreTransformationSync):
    file_path: String
    class_name: String


class CoreUserValidatorSync(CoreValidatorSync):
    check_definition: RelatedNodeSync
    repository: RelatedNodeSync


class InternalAccountTokenSync(CoreNodeSync):
    name: StringOptional
    token: String
    expiration: DateTimeOptional
    account: RelatedNodeSync


class InternalRefreshTokenSync(CoreNodeSync):
    expiration: DateTime
    account: RelatedNodeSync


class IpamNamespaceSync(BuiltinIPNamespaceSync):
    default: BooleanOptional
