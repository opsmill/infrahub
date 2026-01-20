from infrahub_sdk.utils import compare_lists

from infrahub.core.constants import EventType as MainEventType
from infrahub.events.utils import get_all_events


def test_event_type_mapping() -> None:
    event_names = [event.event_name for event in get_all_events()]
    main_event_types = MainEventType.available_types()

    _, missing_events, wrong_events = compare_lists(list1=event_names, list2=main_event_types)

    assert not missing_events, f"Missing event types: {missing_events}"
    assert not wrong_events, f"Wrong event types: {wrong_events}"
