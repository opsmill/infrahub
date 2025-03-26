from infrahub.events.models import InfrahubEvent
from infrahub.utils import get_all_subclasses


def get_all_events() -> list[type[InfrahubEvent]]:
    """Recursively get all subclasses of the given class."""
    subclasses = get_all_subclasses(InfrahubEvent)
    return [cls for cls in subclasses if isinstance(cls.event_name, str)]


def get_all_infrahub_node_kind_events() -> list[str]:
    """Recursively get all events marked as infrahub.node.kind events.

    These events can be used to filter on a specific type for the webhooks
    """
    return [event.event_name for event in get_all_events() if event.infrahub_node_kind_event] + ["all"]
