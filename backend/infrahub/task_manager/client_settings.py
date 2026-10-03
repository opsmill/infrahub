from __future__ import annotations

from typing import TYPE_CHECKING

from prefect.settings import PREFECT_CLIENT_CSRF_SUPPORT_ENABLED, temporary_settings

if TYPE_CHECKING:
    from contextlib import AbstractContextManager

    from prefect.settings import Settings


def prefect_client_defaults() -> AbstractContextManager[Settings]:
    """Apply Infrahub's defaults to the Prefect clients created within this context.

    A value configured explicitly takes precedence, such as `PREFECT_CLIENT_CSRF_SUPPORT_ENABLED=true` for a task
    manager that has CSRF protection enabled.
    """
    # The task manager runs without CSRF protection, so fetching a token costs every new client one refused request.
    return temporary_settings(set_defaults={PREFECT_CLIENT_CSRF_SUPPORT_ENABLED: False})
