from infrahub.events.models import InfrahubEvent
from infrahub.utils import get_all_subclasses


def get_all_events() -> list[type[InfrahubEvent]]:
    """Recursively get all subclasses of the given class."""
    subclasses = get_all_subclasses(InfrahubEvent)
    return [cls for cls in subclasses if isinstance(cls.event_name, str)]
