from infrahub.actions.triggers import TRIGGER_ACTION_RULE_UPDATE
from infrahub.branch.triggers import TRIGGER_BRANCH_MERGED
from infrahub.computed_attribute.triggers import (
    TRIGGER_COMPUTED_ATTRIBUTE_ALL_SCHEMA,
    TRIGGER_COMPUTED_ATTRIBUTE_PYTHON_SETUP_COMMIT,
)
from infrahub.schema.triggers import TRIGGER_SCHEMA_UPDATED
from infrahub.trigger.models import TriggerDefinition
from infrahub.webhook.triggers import TRIGGER_WEBHOOK_DELETE, TRIGGER_WEBHOOK_SETUP_UPDATE

builtin_triggers: list[TriggerDefinition] = [
    TRIGGER_ACTION_RULE_UPDATE,
    TRIGGER_BRANCH_MERGED,
    TRIGGER_COMPUTED_ATTRIBUTE_ALL_SCHEMA,
    TRIGGER_COMPUTED_ATTRIBUTE_PYTHON_SETUP_COMMIT,
    TRIGGER_SCHEMA_UPDATED,
    TRIGGER_WEBHOOK_DELETE,
    TRIGGER_WEBHOOK_SETUP_UPDATE,
]
