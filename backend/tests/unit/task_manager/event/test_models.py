from infrahub.task_manager.event.models import InfrahubEventFilter


class TestInfrahubEventFilter:
    def test_add_event_type_filter_with_exclude_prefixes_only(self) -> None:
        """When only exclude_prefixes is provided, the filter should scope to the infrahub namespace prefix."""
        event_filter = InfrahubEventFilter()
        event_filter.add_event_type_filter(exclude_prefixes=["infrahub.account."])

        assert event_filter.event is not None
        assert event_filter.event.prefix == ["infrahub."]
        assert event_filter.event.exclude_prefix == ["infrahub.account."]

    def test_add_event_type_filter_with_event_type_only(self) -> None:
        """When event_type is provided, it takes priority and no prefix is set."""
        event_filter = InfrahubEventFilter()
        event_filter.add_event_type_filter(event_type=["infrahub.branch.created"])

        assert event_filter.event is not None
        assert event_filter.event.name == ["infrahub.branch.created"]
        assert not event_filter.event.prefix

    def test_add_event_type_filter_with_no_args(self) -> None:
        """When no arguments are provided, the event filter is not set."""
        event_filter = InfrahubEventFilter()
        event_filter.add_event_type_filter()

        assert event_filter.event is None
