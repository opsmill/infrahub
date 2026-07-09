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


RESOLUTION_CASES = [
    ResolutionCase(
        name="user_value_wins_over_global",
        user=Preference(owner_id="account-a", date_format=DateFormat.ISO_8601, timezone="Europe/Paris"),
        global_=Preference(owner_id="root", date_format=DateFormat.US_12H, timezone="UTC"),
        expected_date_format=ResolvedPreference(value=DateFormat.ISO_8601, source=PreferenceSource.USER),
        expected_timezone=ResolvedPreference(value="Europe/Paris", source=PreferenceSource.USER),
    ),
    ResolutionCase(
        name="global_fills_fields_the_user_left_unset",
        user=Preference(owner_id="account-a", date_format=DateFormat.ISO_8601),
        global_=Preference(owner_id="root", date_format=DateFormat.US_12H, timezone="UTC"),
        expected_date_format=ResolvedPreference(value=DateFormat.ISO_8601, source=PreferenceSource.USER),
        expected_timezone=ResolvedPreference(value="UTC", source=PreferenceSource.GLOBAL),
    ),
    ResolutionCase(
        name="default_when_neither_layer_sets_a_field",
        user=Preference(owner_id="account-a"),
        global_=Preference(owner_id="root"),
        expected_date_format=ResolvedPreference(value=None, source=PreferenceSource.DEFAULT),
        expected_timezone=ResolvedPreference(value=None, source=PreferenceSource.DEFAULT),
    ),
    ResolutionCase(
        name="missing_layers_behave_as_nothing_set",
        user=None,
        global_=None,
        expected_date_format=ResolvedPreference(value=None, source=PreferenceSource.DEFAULT),
        expected_timezone=ResolvedPreference(value=None, source=PreferenceSource.DEFAULT),
    ),
    ResolutionCase(
        name="missing_user_layer_falls_back_to_global",
        user=None,
        global_=Preference(owner_id="root", timezone="UTC"),
        expected_date_format=ResolvedPreference(value=None, source=PreferenceSource.DEFAULT),
        expected_timezone=ResolvedPreference(value="UTC", source=PreferenceSource.GLOBAL),
    ),
]


@pytest.mark.parametrize("case", RESOLUTION_CASES, ids=lambda case: case.name)
def test_effective_preference_resolution(case: ResolutionCase) -> None:
    effective = EffectivePreferences(user=case.user, global_=case.global_)

    assert effective.resolved_date_format() == case.expected_date_format
    assert effective.resolved_timezone() == case.expected_timezone
