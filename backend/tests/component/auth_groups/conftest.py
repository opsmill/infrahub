"""Shared fixtures for the auth_groups component tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub import config

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture
def autocreate_filter_enabled() -> Iterator[None]:
    """Enable the auto-creation filter for the duration of the test, restoring on teardown."""
    original_filter = config.SETTINGS.security.auto_create_groups_filter
    original_compiled = config.SETTINGS.security._auto_create_groups_filter_patterns

    config.SETTINGS.security.auto_create_groups_filter = r"^LDAP/group/(?P<name>.+)$"
    config.SETTINGS.security.recompile_auto_create_groups_filter_patterns()

    try:
        yield
    finally:
        config.SETTINGS.security.auto_create_groups_filter = original_filter
        config.SETTINGS.security._auto_create_groups_filter_patterns = original_compiled


@pytest.fixture
def autocreate_filter_with_low_cap(autocreate_filter_enabled: None) -> Iterator[int]:
    """Activate the auto-create filter and tighten `auto_create_groups_max_per_login` to 2."""
    original_cap = config.SETTINGS.security.auto_create_groups_max_per_login
    low_cap = 2
    config.SETTINGS.security.auto_create_groups_max_per_login = low_cap

    try:
        yield low_cap
    finally:
        config.SETTINGS.security.auto_create_groups_max_per_login = original_cap
