from __future__ import annotations

from dataclasses import dataclass

import pytest

from infrahub.core.preferences.constants import DateFormat, PreferenceSource
from infrahub.core.preferences.models import EffectivePreferences, Preference, ResolvedPreference


@dataclass
class ResolutionCase:
    name: str
    user: Preference | None
    global_: Preference | None
    expected_date_format: ResolvedPreference
    expected_timezone: ResolvedPreference
    # No defaults: a default would let a row's inherited expectation go silently unasserted.
    expected_inherited_date_format: ResolvedPreference
    expected_inherited_timezone: ResolvedPreference


RESOLUTION_CASES = [
    ResolutionCase(
        name="user_value_wins_over_global",
        user=Preference(owner_id="account-a", date_format=DateFormat.ISO_8601, timezone="Europe/Paris"),
        global_=Preference(owner_id="root", date_format=DateFormat.US_12H, timezone="UTC"),
        expected_date_format=ResolvedPreference(value=DateFormat.ISO_8601, source=PreferenceSource.USER),
        expected_timezone=ResolvedPreference(value="Europe/Paris", source=PreferenceSource.USER),
        # The shadowed global layer stays reportable: this is what clearing the override falls back to.
        expected_inherited_date_format=ResolvedPreference(value=DateFormat.US_12H, source=PreferenceSource.GLOBAL),
        expected_inherited_timezone=ResolvedPreference(value="UTC", source=PreferenceSource.GLOBAL),
    ),
    ResolutionCase(
        name="global_fills_fields_the_user_left_unset",
        user=Preference(owner_id="account-a", date_format=DateFormat.ISO_8601),
        global_=Preference(owner_id="root", date_format=DateFormat.US_12H, timezone="UTC"),
        expected_date_format=ResolvedPreference(value=DateFormat.ISO_8601, source=PreferenceSource.USER),
        expected_timezone=ResolvedPreference(value="UTC", source=PreferenceSource.GLOBAL),
        expected_inherited_date_format=ResolvedPreference(value=DateFormat.US_12H, source=PreferenceSource.GLOBAL),
        expected_inherited_timezone=ResolvedPreference(value="UTC", source=PreferenceSource.GLOBAL),
    ),
    ResolutionCase(
        name="default_when_neither_layer_sets_a_field",
        user=Preference(owner_id="account-a"),
        global_=Preference(owner_id="root"),
        expected_date_format=ResolvedPreference(value=None, source=PreferenceSource.DEFAULT),
        expected_timezone=ResolvedPreference(value=None, source=PreferenceSource.DEFAULT),
        expected_inherited_date_format=ResolvedPreference(value=None, source=PreferenceSource.DEFAULT),
        expected_inherited_timezone=ResolvedPreference(value=None, source=PreferenceSource.DEFAULT),
    ),
    ResolutionCase(
        name="missing_layers_behave_as_nothing_set",
        user=None,
        global_=None,
        expected_date_format=ResolvedPreference(value=None, source=PreferenceSource.DEFAULT),
        expected_timezone=ResolvedPreference(value=None, source=PreferenceSource.DEFAULT),
        expected_inherited_date_format=ResolvedPreference(value=None, source=PreferenceSource.DEFAULT),
        expected_inherited_timezone=ResolvedPreference(value=None, source=PreferenceSource.DEFAULT),
    ),
    ResolutionCase(
        name="missing_user_layer_falls_back_to_global",
        user=None,
        global_=Preference(owner_id="root", timezone="UTC"),
        expected_date_format=ResolvedPreference(value=None, source=PreferenceSource.DEFAULT),
        expected_timezone=ResolvedPreference(value="UTC", source=PreferenceSource.GLOBAL),
        expected_inherited_date_format=ResolvedPreference(value=None, source=PreferenceSource.DEFAULT),
        expected_inherited_timezone=ResolvedPreference(value="UTC", source=PreferenceSource.GLOBAL),
    ),
    ResolutionCase(
        # A user override can shadow nothing: the global row exists but leaves both fields unset.
        name="user_override_shadows_nothing_when_global_row_leaves_fields_unset",
        user=Preference(owner_id="account-a", date_format=DateFormat.EU_DATETIME, timezone="Europe/Paris"),
        global_=Preference(owner_id="root"),
        expected_date_format=ResolvedPreference(value=DateFormat.EU_DATETIME, source=PreferenceSource.USER),
        expected_timezone=ResolvedPreference(value="Europe/Paris", source=PreferenceSource.USER),
        expected_inherited_date_format=ResolvedPreference(value=None, source=PreferenceSource.DEFAULT),
        expected_inherited_timezone=ResolvedPreference(value=None, source=PreferenceSource.DEFAULT),
    ),
    ResolutionCase(
        # A missing global layer and an empty global row are indistinguishable to both projections.
        name="user_override_shadows_nothing_when_global_layer_is_missing",
        user=Preference(owner_id="account-a", date_format=DateFormat.US_12H, timezone="UTC"),
        global_=None,
        expected_date_format=ResolvedPreference(value=DateFormat.US_12H, source=PreferenceSource.USER),
        expected_timezone=ResolvedPreference(value="UTC", source=PreferenceSource.USER),
        expected_inherited_date_format=ResolvedPreference(value=None, source=PreferenceSource.DEFAULT),
        expected_inherited_timezone=ResolvedPreference(value=None, source=PreferenceSource.DEFAULT),
    ),
]


@pytest.mark.parametrize("case", RESOLUTION_CASES, ids=lambda case: case.name)
def test_effective_preference_resolution(case: ResolutionCase) -> None:
    effective = EffectivePreferences(user=case.user, global_=case.global_)

    assert effective.resolved_date_format() == case.expected_date_format
    assert effective.resolved_timezone() == case.expected_timezone
    assert effective.inherited_date_format() == case.expected_inherited_date_format
    assert effective.inherited_timezone() == case.expected_inherited_timezone


@pytest.mark.parametrize("case", RESOLUTION_CASES, ids=lambda case: case.name)
def test_inherited_never_reports_the_user_layer(case: ResolutionCase) -> None:
    """The inherited projection suppresses the user layer, so it can only ever be GLOBAL or DEFAULT."""
    effective = EffectivePreferences(user=case.user, global_=case.global_)

    assert effective.inherited_date_format().source != PreferenceSource.USER
    assert effective.inherited_timezone().source != PreferenceSource.USER


@pytest.mark.parametrize("case", RESOLUTION_CASES, ids=lambda case: case.name)
def test_inherited_equals_resolved_for_every_field_the_user_does_not_override(case: ResolutionCase) -> None:
    """A field with no user override already IS its own fallback, so both projections must agree."""
    effective = EffectivePreferences(user=case.user, global_=case.global_)

    not_overridden = [
        (resolved, inherited)
        for resolved, inherited in (
            (effective.resolved_date_format(), effective.inherited_date_format()),
            (effective.resolved_timezone(), effective.inherited_timezone()),
        )
        if resolved.source != PreferenceSource.USER
    ]

    assert all(inherited == resolved for resolved, inherited in not_overridden)
