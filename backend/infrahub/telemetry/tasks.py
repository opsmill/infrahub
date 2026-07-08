import hashlib
import json
import platform
import time
from collections.abc import Awaitable, Callable
from typing import Any

from prefect import flow, task
from prefect.cache_policies import NONE
from prefect.client.orchestration import get_client as get_prefect_client
from prefect.logging import get_run_logger

from infrahub import __version__, config
from infrahub.core import registry, utils
from infrahub.core.branch import Branch
from infrahub.core.constants import AccountStatus, InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.database import InfrahubDatabase
from infrahub.workers.dependencies import get_component, get_database, get_http

from .constants import (
    TELEMETRY_KIND,
    TELEMETRY_VERSION,
    RemoteSendStatus,
)
from .database import gather_database_information
from .models import (
    TelemetryAccountData,
    TelemetryActivity24hData,
    TelemetryBranchData,
    TelemetryData,
    TelemetrySchemaData,
    TelemetryWorkerData,
)
from .repository import TelemetrySnapshotRepository
from .snapshot import TelemetrySnapshot
from .task_manager import gather_activity_24h, gather_prefect_information
from .utils import determine_infrahub_type, safe_metric


@task(name="telemetry-schema-information", task_run_name="Gather Schema Information", cache_policy=NONE)
async def gather_schema_information(branch: Branch) -> TelemetrySchemaData:
    main_schema = registry.schema.get_schema_branch(name=branch.name)
    return TelemetrySchemaData(
        node_count=len(main_schema.node_names),
        generic_count=len(main_schema.generic_names),
        last_update=branch.schema_changed_at or "",
    )


@task(name="telemetry-feature-information", task_run_name="Gather Feature Information", cache_policy=NONE)
async def gather_feature_information() -> dict[str, int]:
    database = await get_database()
    async with database.start_session(read_only=True) as db:
        data = {}
        features_to_count = [
            InfrahubKind.ARTIFACT,
            InfrahubKind.RESOURCEPOOL,
            InfrahubKind.REPOSITORY,
            InfrahubKind.GENERICGROUP,
            InfrahubKind.PROFILE,
            InfrahubKind.PROPOSEDCHANGE,
            InfrahubKind.OBJECTTEMPLATE,
            InfrahubKind.TRANSFORM,
            InfrahubKind.WEBHOOK,
        ]
        for kind in features_to_count:
            data[kind] = await utils.count_nodes(db=db, label=kind)

        return data


@task(name="telemetry-account-information", task_run_name="Gather Account Information", cache_policy=NONE)
async def gather_account_information(db: InfrahubDatabase) -> TelemetryAccountData:
    """Gather account adoption counts on the default branch.

    Counted through the branch/temporal-correct path so they match the GraphQL resolvers; each
    field degrades to ``null`` independently on failure.
    """
    default_branch = registry.get_branch_from_registry()

    active = await safe_metric(
        NodeManager.count(
            db=db,
            schema=InfrahubKind.ACCOUNT,
            filters={"status__value": AccountStatus.ACTIVE.value},
            branch=default_branch,
        )
    )
    groups = await safe_metric(
        NodeManager.count(
            db=db,
            schema=InfrahubKind.ACCOUNTGROUP,
            branch=default_branch,
        )
    )

    return TelemetryAccountData(active=active, groups=groups)


async def count_active_branches() -> int:
    """Count open non-system branches.

    Registry members minus the default and global branches (closed branches are evicted from
    the registry). Async only so it composes with the degradation helper.
    """
    return len([branch for branch in registry.branch.values() if not branch.is_default and not branch.is_global])


async def _default_activity_24h_gatherer() -> TelemetryActivity24hData:
    """Open a Prefect client and assemble the windowed 24h activity metrics."""
    async with get_prefect_client(sync_client=False) as prefect_client:
        return await gather_activity_24h(client=prefect_client)


@task(name="telemetry-gather-data", task_run_name="Gather Anonynous Data", cache_policy=NONE)
async def gather_anonymous_telemetry_data(
    account_gatherer: Callable[[InfrahubDatabase], Awaitable[TelemetryAccountData]] = gather_account_information,
    activity_gatherer: Callable[[], Awaitable[TelemetryActivity24hData]] = _default_activity_24h_gatherer,
    active_branch_counter: Callable[[], Awaitable[int]] = count_active_branches,
) -> TelemetryData:
    """Assemble the full telemetry payload, isolating every metric source.

    Each source is gathered through the degradation helper, so one failing source nulls only
    its own field(s) while the rest is still built. The ``*_gatherer`` / ``*_counter`` params
    are injection seams that let the per-source isolation be tested with a real failing
    collaborator instead of patching.
    """
    start_time = time.time()

    default_branch = registry.get_branch_from_registry()
    database = await get_database()
    component = await get_component()
    workers = await component.list_workers(branch=default_branch.name, schema_hash=False)

    accounts = await safe_metric(account_gatherer(database))
    activity_24h = await safe_metric(activity_gatherer())

    data = TelemetryData(
        deployment_id=registry.id,
        execution_time=None,
        infrahub_version=__version__,
        infrahub_type=determine_infrahub_type(),
        python_version=platform.python_version(),
        platform=platform.machine(),
        workers=TelemetryWorkerData(
            total=len(workers),
            active=len([w for w in workers if w.active]),
        ),
        branches=TelemetryBranchData(
            total=len(registry.branch),
            active=await safe_metric(active_branch_counter()),
        ),
        accounts=accounts if accounts is not None else TelemetryAccountData(),
        activity_24h=activity_24h if activity_24h is not None else TelemetryActivity24hData(),
        features=await gather_feature_information(),
        schema_info=await gather_schema_information(branch=default_branch),
        database=await gather_database_information(db=database),
        prefect=await gather_prefect_information(),
    )

    data.execution_time = time.time() - start_time

    return data


@task(name="telemetry-post-data", task_run_name="Upload data", retries=5, cache_policy=NONE)
async def post_telemetry_data(url: str, payload: dict[str, Any]) -> None:
    """Send the telemetry data to the specified URL, using HTTP POST."""
    response = await get_http().post(url=url, json=payload)
    response.raise_for_status()


@flow(name="anonymous_telemetry_send", flow_run_name="Send anonymous telemetry")
async def send_telemetry_push() -> None:
    log = get_run_logger()

    log.info("Gathering anonymous telemetry data...")
    data = await gather_anonymous_telemetry_data()
    data_dict = data.model_dump(mode="json")
    checksum = hashlib.sha256(json.dumps(data_dict).encode()).hexdigest()
    log.info(f"Anonymous usage telemetry gathered in {data.execution_time} seconds.")

    snapshot = TelemetrySnapshot(
        kind=TELEMETRY_KIND,
        payload_format=TELEMETRY_VERSION,
        deployment_id=str(registry.id) if registry.id else "",
        infrahub_version=__version__,
        data=data_dict,
        checksum=checksum,
        remote_send_status=RemoteSendStatus.PENDING,
    )

    database = await get_database()
    repository = TelemetrySnapshotRepository(db=database)

    # Always store locally. If this fails, we have nothing to update later — bail out.
    try:
        await repository.save(snapshot)
        log.info(f"Telemetry snapshot stored locally (uuid={snapshot.uuid}).")
    except Exception as exc:
        log.warning(f"Failed to store telemetry snapshot locally: {exc}")
        return

    if config.SETTINGS.main.telemetry_optout:
        log.info("User opted out of remote telemetry. Marking snapshot as skipped.")
        snapshot.remote_send_status = RemoteSendStatus.SKIPPED
        await repository.save(snapshot)
        return

    log.info(f"Pushing anonymous telemetry data to {config.SETTINGS.main.telemetry_endpoint}...")
    payload = {
        "kind": TELEMETRY_KIND,
        "payload_format": TELEMETRY_VERSION,
        "data": data_dict,
        "checksum": checksum,
    }

    try:
        await post_telemetry_data(url=config.SETTINGS.main.telemetry_endpoint, payload=payload)
        snapshot.remote_send_status = RemoteSendStatus.SENT
        log.info("Telemetry data sent to remote endpoint successfully.")
    except Exception as exc:
        snapshot.remote_send_status = RemoteSendStatus.FAILED
        log.warning(f"Failed to send telemetry data to remote endpoint: {exc}")

    try:
        await repository.save(snapshot)
    except Exception as exc:
        log.warning(f"Failed to update snapshot remote send status: {exc}")
