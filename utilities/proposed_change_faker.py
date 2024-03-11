"""
This script creates all required objects to fake a proposed change with all kind of validators, checks in all possible states.

It tries to be as idempotent as possible to avoid re-creating objects on re-run.
"""

import logging
import random
import string
import tempfile
from typing import Any

from infrahub_sdk.client import InfrahubClient
from infrahub_sdk.exceptions import BranchNotFoundError, NodeNotFoundError
from infrahub_sdk.node import InfrahubNode
from infrahub_sdk.timestamp import Timestamp

VALIDATOR_STATES = ["queued", "in_progress", "completed"]
CONCLUSIONS = ["unknown", "failure", "success"]
CONCLUSION_TO_SEVERITY = {"unknown": "warning", "failure": "error", "success": "success"}


def is_final_state(state: str) -> bool:
    return state in ("completed",)


class RandomStringFactory:
    def __init__(self, seed: Any = None) -> None:
        self.random = random.SystemRandom(x=seed)

    def get_one(self, length: int = 10) -> str:
        """Return a random string of length always starting with an upper case letter."""
        f = self.random.choice(string.ascii_uppercase)  # Some nodes needs an uppercased first letter
        r = "".join(self.random.choices(string.ascii_letters + string.digits, k=length - 1))
        return f + r


RSF = RandomStringFactory()


async def create_checks(
    client: InfrahubClient, log: logging.Logger, validator: InfrahubNode, check_kinds: list[str]
) -> None:
    created_at = Timestamp().to_string()

    for check_kind in check_kinds:
        for conclusion in CONCLUSIONS:
            check_data = {}
            if check_kind in ("CoreStandardCheck", "CoreFileCheck"):
                check_data = {
                    "name": f"{validator.display_label} - {RSF.get_one()}",
                    "validator": validator,
                    "kind": RSF.get_one(),
                    "origin": RSF.get_one(),
                    "created_at": created_at,
                }
            elif check_kind == "CoreSchemaCheck":
                check_data = {
                    "name": f"{validator.display_label} - {RSF.get_one()}",
                    "validator": validator,
                    "kind": RSF.get_one(),
                    "origin": RSF.get_one(),
                    "created_at": created_at,
                    "conflicts": [],
                }
            if check_data:
                check_data.update(
                    {
                        "conclusion": conclusion,
                        "severity": CONCLUSION_TO_SEVERITY[conclusion],
                        "message": RSF.get_one(length=2500),
                    }
                )

            if check_data:
                try:
                    c = await client.get(check_kind, validator__ids=validator.id, conclusion__value=conclusion)
                    log.info(f"- Found check: {c!r} with conclusion {conclusion}")
                except NodeNotFoundError:
                    c = await client.create(check_kind, data=check_data)
                    await c.save()
                    log.info(f"- Created check: {c!r} with conclusion {conclusion}")


async def create_validators(
    client: InfrahubClient, log: logging.Logger, proposed_change: InfrahubNode, repository: InfrahubNode
) -> None:
    started_at = Timestamp()
    validators: dict[str, dict[str, Any]] = {
        # "CoreArtifactValidator": {"checks": ["CoreArtifactCheck"], "data": {}},
        "CoreDataValidator": {"checks": ["CoreDataCheck"], "data": {}},
        "CoreRepositoryValidator": {
            "checks": ["CoreFileCheck", "CoreStandardCheck"],
            "data": {"repository": repository},
        },
        "CoreSchemaValidator": {"checks": ["CoreSchemaCheck"], "data": {}},
        # "CoreUserValidator": {"checks": [], "data": {"repository": repository}},
    }

    for validator_kind, details in validators.items():
        # Always include the proposed change ID in the validator creation
        create_data = details["data"]
        create_data.update({"proposed_change": proposed_change, "started_at": started_at.to_string()})

        for state in VALIDATOR_STATES:
            try:
                v = await client.get(validator_kind, proposed_change__ids=proposed_change.id, state__value=state)
                log.info(f"- Found validator: {v!r} with state {state}")
            except NodeNotFoundError:
                # State and name
                create_data.update(
                    {
                        "state": state,
                        "label": f"{validator_kind} - {RSF.get_one()}",
                    }
                )
                # Mark as complete if in final state
                if is_final_state(state):
                    create_data.update({"completed_at": started_at.add_delta(seconds=30).to_string()})

                v = await client.create(validator_kind, data=create_data)
                await v.save()
                log.info(f"- Created validator: {v!r} with state {state}")

            await create_checks(client, log, v, details["checks"])


async def create_repository(client: InfrahubClient, log: logging.Logger) -> InfrahubNode:
    temp_dir = tempfile.TemporaryDirectory()
    repo_name = "Dummy repository"

    try:
        new_repository = await client.get(kind="CoreRepository", name__value=repo_name)
        log.info(f"- Found repository: {new_repository!r}")
    except NodeNotFoundError:
        new_repository = await client.create(kind="CoreRepository", data={"name": repo_name, "location": temp_dir.name})
        await new_repository.save()
        log.info(f"- Created repository: {new_repository!r}")

    temp_dir.cleanup()

    return new_repository


async def create_proposed_change(client: InfrahubClient, log: logging.Logger) -> InfrahubNode:
    branch_name = "dummy-branch"

    try:
        new_branch = await client.branch.get(branch_name)
        log.info(f"- Found branch: {new_branch!r}")
    except BranchNotFoundError:
        new_branch = await client.branch.create(
            branch_name="dummy-branch", sync_with_git=False, description="Empty shell for testing validators and checks"
        )
        log.info(f"- Created branch: {new_branch!r}")

    try:
        new_proposed_change = await client.get(kind="CoreProposedChange", name__value="validators-checks-faker")
        log.info(f"- Found proposed change: {new_proposed_change!r}")
    except NodeNotFoundError:
        new_proposed_change = await client.create(
            "CoreProposedChange",
            data={"name": "validators-checks-faker", "source_branch": "dummy-branch", "destination_branch": "main"},
        )
        await new_proposed_change.save()
        log.info(f"- Created proposed change: {new_proposed_change!r}")

    return new_proposed_change


async def run(client: InfrahubClient, log: logging.Logger, branch: str):
    proposed_change = await create_proposed_change(client, log)
    repository = await create_repository(client, log)
    await create_validators(client, log, proposed_change, repository)
