from infrahub.computed_attribute.triggers import (
    TRIGGER_COMPUTED_ATTRIBUTE_ALL_SCHEMA,
    TRIGGER_COMPUTED_ATTRIBUTE_PYTHON_SETUP_COMMIT,
)
from infrahub.trigger.models import TriggerDefinition
from infrahub.webhook.triggers import TRIGGER_WEBHOOK_DELETE, TRIGGER_WEBHOOK_SETUP_UPDATE

builtin_triggers: list[TriggerDefinition] = [
    TRIGGER_COMPUTED_ATTRIBUTE_ALL_SCHEMA,
    TRIGGER_COMPUTED_ATTRIBUTE_PYTHON_SETUP_COMMIT,
    TRIGGER_WEBHOOK_DELETE,
    TRIGGER_WEBHOOK_SETUP_UPDATE,
]
