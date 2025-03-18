from typing import Any

from ...generic_schema import GenericSchema
from ...node_schema import NodeSchema
from .account import (
    core_account,
    core_account_token,
    core_credential,
    core_generic_account,
    core_password_credential,
    core_refresh_token,
)
from .artifact import core_artifact, core_artifact_definition, core_artifact_target
from .builtin import builtin_tag
from .check import core_check_definition
from .core import core_node, core_task_target
from .generator import core_generator_definition, core_generator_instance
from .graphql_query import core_graphql_query
from .group import core_generator_group, core_graphql_query_group, core_group, core_standard_group
from .ipam import builtin_ip_address, builtin_ip_prefix, builtin_ipam, core_ipam_namespace
from .lineage import lineage_owner, lineage_source
from .menu import generic_menu_item, menu_item
from .permission import (
    core_account_group,
    core_account_role,
    core_base_permission,
    core_global_permission,
    core_object_permission,
)
from .profile import core_profile_schema_definition
from .propose_change import core_proposed_change
from .propose_change_comment import (
    core_artifact_thread,
    core_change_comment,
    core_change_thread,
    core_file_thread,
    core_object_thread,
    core_propose_change_comment,
    core_thread,
    core_thread_comment,
)
from .propose_change_validator import (
    core_artifact_check,
    core_artifact_validator,
    core_check,
    core_data_check,
    core_data_validator,
    core_file_check,
    core_generator_check,
    core_generator_validator,
    core_propose_change_validator,
    core_repository_validator,
    core_schema_check,
    core_schema_validator,
    core_standard_check,
    core_user_validator,
)
from .repository import core_generic_repository, core_read_only_repository, core_repository
from .resource_pool import core_ip_address_pool, core_ip_prefix_pool, core_number_pool, core_resource_pool
from .template import core_object_component_template, core_object_template
from .transform import core_transform, core_transform_jinja2, core_transform_python
from .webhook import core_custom_webhook, core_standard_webhook, core_webhook

core_models_mixed: dict[str, list] = {
    "generics": [
        core_node,
        lineage_owner,
        core_profile_schema_definition,
        lineage_source,
        core_propose_change_comment,
        core_thread,
        core_group,
        core_propose_change_validator,
        core_check,
        core_transform,
        core_artifact_target,
        core_task_target,
        core_webhook,
        core_generic_repository,
        builtin_ipam,
        builtin_ip_prefix,
        builtin_ip_address,
        core_resource_pool,
        core_generic_account,
        core_base_permission,
        core_credential,
        core_object_template,
        core_object_component_template,
        generic_menu_item,
    ],
    "nodes": [
        menu_item,
        core_standard_group,
        core_generator_group,
        core_graphql_query_group,
        builtin_tag,
        core_account,
        core_account_token,
        core_password_credential,
        core_refresh_token,
        core_proposed_change,
        core_change_thread,
        core_file_thread,
        core_artifact_thread,
        core_object_thread,
        core_change_comment,
        core_thread_comment,
        core_repository,
        core_read_only_repository,
        core_transform_jinja2,
        core_data_check,
        core_standard_check,
        core_schema_check,
        core_file_check,
        core_artifact_check,
        core_generator_check,
        core_data_validator,
        core_repository_validator,
        core_user_validator,
        core_schema_validator,
        core_artifact_validator,
        core_generator_validator,
        core_check_definition,
        core_transform_python,
        core_graphql_query,
        core_artifact,
        core_artifact_definition,
        core_generator_definition,
        core_generator_instance,
        core_standard_webhook,
        core_custom_webhook,
        core_ipam_namespace,
        core_ip_prefix_pool,
        core_ip_address_pool,
        core_number_pool,
        core_global_permission,
        core_object_permission,
        core_account_role,
        core_account_group,
    ],
}


core_models: dict[str, Any] = {
    "generics": [item.to_dict() if isinstance(item, GenericSchema) else item for item in core_models_mixed["generics"]],
    "nodes": [item.to_dict() if isinstance(item, NodeSchema) else item for item in core_models_mixed["nodes"]],
}
