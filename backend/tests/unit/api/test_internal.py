from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from infrahub.api.internal import InstanceIdentityAPI, InstanceIdentityResolver, get_config
from infrahub.core.preferences.repository import PreferenceRepository
from infrahub.exceptions import DatabaseError
from infrahub.instance_identity import InstanceColor

if TYPE_CHECKING:
    from infrahub.core.preferences.models import Preference


class FailingPreferenceRepository(PreferenceRepository):
    def __init__(self, error: Exception) -> None:
        self.error = error

    async def get_for_owner(self, owner_id: str) -> Preference | None:
        raise self.error


@dataclass
class ReadFailureCase:
    name: str
    error: Exception


READ_FAILURE_CASES: list[ReadFailureCase] = [
    ReadFailureCase(name="database_error", error=DatabaseError(message="Unable to connect to the database")),
    ReadFailureCase(name="unexpected_error", error=RuntimeError("read() called while another coroutine is waiting")),
]


@pytest.mark.parametrize("case", READ_FAILURE_CASES, ids=lambda case: case.name)
async def test_a_failed_read_serves_no_identity_and_still_serves_the_deployment_defaults(case: ReadFailureCase) -> None:
    resolver = InstanceIdentityResolver(
        repository=FailingPreferenceRepository(error=case.error),
        defaults=InstanceIdentityAPI(label="staging", color=InstanceColor.AMBER),
    )

    response = await get_config(instance_resolver=resolver)

    assert (response.instance, response.instance_defaults) == (
        InstanceIdentityAPI(label=None, color=None),
        InstanceIdentityAPI(label="staging", color=InstanceColor.AMBER),
    )
