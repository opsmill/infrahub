from pydantic import BaseModel, Field

from .constants import InfrahubType


class TelemetryContainerData(BaseModel):
    """The CPU and memory of one container of a component, shared by the processes that run in it."""

    processor_available: int | None = None
    processor_assigned: int | None = None
    memory_total: int | None = None
    memory_available: int | None = None


class TelemetryWorkerData(BaseModel):
    total: int
    active: int


class TelemetryBranchData(BaseModel):
    total: int
    active: int | None = None


class TelemetryAccountData(BaseModel):
    active: int | None = Field(default=None)
    groups: int | None = Field(default=None)


class TelemetryActivity24hData(BaseModel):
    logins: int | None = Field(default=None)
    unique_logins: int | None = Field(default=None)
    checks_started: int | None = Field(default=None)
    checks_passed: int | None = Field(default=None)
    checks_failed: int | None = Field(default=None)
    artifacts_created: int | None = Field(default=None)
    artifacts_updated: int | None = Field(default=None)
    branches_created: int | None = Field(default=None)
    branches_merged: int | None = Field(default=None)
    branches_deleted: int | None = Field(default=None)
    webhooks_fired_success: int | None = Field(default=None)
    webhooks_fired_failure: int | None = Field(default=None)


class TelemetrySchemaData(BaseModel):
    node_count: int
    generic_count: int
    last_update: str


class TelemetryDatabaseServerData(BaseModel):
    name: str
    version: str


class TelemetryDatabaseSystemInfoData(BaseModel):
    memory_total: int
    memory_available: int
    processor_available: int
    processor_assigned: int | None = Field(default=None, ge=0)
    memory_assigned: int | None = Field(default=None, ge=0)


class TelemetryComponentData(BaseModel):
    """One component's processes, counted like the workers block, with the CPU and memory of one of its containers.

    The component's total is ``per_container`` times ``active`` divided by ``processes_per_container``.
    """

    total: int | None = None
    active: int | None = None
    processes_per_container: int | None = None
    per_container: TelemetryContainerData = Field(default_factory=TelemetryContainerData)


class TelemetryDatabaseData(BaseModel):
    database_type: str
    relationship_count: dict[str, int]
    node_count: dict[str, int | None]
    servers: list[TelemetryDatabaseServerData]
    system_info: TelemetryDatabaseSystemInfoData | None


class TelemetryWorkPoolData(BaseModel):
    name: str
    type: str
    total_workers: int
    active_workers: int


class TelemetryPrefectData(BaseModel):
    events: dict[str, int]
    automations: dict[str, int]
    work_pools: list[TelemetryWorkPoolData]


class TelemetryData(BaseModel):
    deployment_id: str | None
    execution_time: float | None
    infrahub_version: str
    infrahub_type: InfrahubType
    python_version: str
    platform: str
    workers: TelemetryWorkerData
    server: TelemetryComponentData = Field(default_factory=TelemetryComponentData)
    task_workers: TelemetryComponentData = Field(default_factory=TelemetryComponentData)
    branches: TelemetryBranchData
    accounts: TelemetryAccountData = Field(default_factory=TelemetryAccountData)
    activity_24h: TelemetryActivity24hData = Field(default_factory=TelemetryActivity24hData)
    features: dict[str, int]
    schema_info: TelemetrySchemaData
    database: TelemetryDatabaseData
    prefect: TelemetryPrefectData
