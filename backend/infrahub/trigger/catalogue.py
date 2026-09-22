from fast_depends import Depends, inject

from infrahub.actions.triggers import TRIGGER_ACTION_RULE_UPDATE
from infrahub.branch.triggers import TRIGGER_BRANCH_MERGED
from infrahub.computed_attribute.triggers import (
    TRIGGER_COMPUTED_ATTRIBUTE_ALL_SCHEMA,
    TRIGGER_COMPUTED_ATTRIBUTE_PYTHON_TRANSFORM_CREATED,
    TRIGGER_COMPUTED_ATTRIBUTE_PYTHON_TRANSFORM_DELETED,
    TRIGGER_COMPUTED_ATTRIBUTE_PYTHON_TRANSFORM_UPDATED,
)
from infrahub.display_labels.triggers import TRIGGER_DISPLAY_LABELS_ALL_SCHEMA
from infrahub.hfid.triggers import TRIGGER_HFID_ALL_SCHEMA
from infrahub.profiles.triggers import TRIGGER_PROFILE_REFRESH_SETUP
from infrahub.schema.triggers import TRIGGER_SCHEMA_UPDATED
from infrahub.trigger.models import TriggerDefinition
from infrahub.trigger.system import TRIGGER_CRASH_ZOMBIE_FLOWS
from infrahub.webhook.triggers import TRIGGER_KEYVALUE_WEBHOOK_INVALIDATE, TRIGGER_WEBHOOK_CONFIGURE

builtin_triggers: list[TriggerDefinition] = [
    TRIGGER_ACTION_RULE_UPDATE,
    TRIGGER_BRANCH_MERGED,
    TRIGGER_COMPUTED_ATTRIBUTE_ALL_SCHEMA,
    TRIGGER_COMPUTED_ATTRIBUTE_PYTHON_TRANSFORM_CREATED,
    TRIGGER_COMPUTED_ATTRIBUTE_PYTHON_TRANSFORM_DELETED,
    TRIGGER_COMPUTED_ATTRIBUTE_PYTHON_TRANSFORM_UPDATED,
    TRIGGER_CRASH_ZOMBIE_FLOWS,
    TRIGGER_DISPLAY_LABELS_ALL_SCHEMA,
    TRIGGER_HFID_ALL_SCHEMA,
    TRIGGER_KEYVALUE_WEBHOOK_INVALIDATE,
    TRIGGER_PROFILE_REFRESH_SETUP,
    TRIGGER_SCHEMA_UPDATED,
    TRIGGER_WEBHOOK_CONFIGURE,
]


# Use this dependency injection mechanism to easily add new triggers within infrahub-enterprise
def build_triggers_definitions() -> list[TriggerDefinition]:
    return builtin_triggers


@inject
def get_triggers(
    triggers: list[TriggerDefinition] = Depends(build_triggers_definitions),  # noqa: B008
) -> list[TriggerDefinition]:
    return triggers
