from pydantic import BaseModel

from .constants import InfrahubType


class TelemetryWorkerData(BaseModel):
    total: int
    active: int


class TelemetryBranchData(BaseModel):
    total: int


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


class TelemetryDatabaseData(BaseModel):
    database_type: str
    relationship_count: dict[str, int]
    node_count: dict[str, int]
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
    branches: TelemetryBranchData
    features: dict[str, int]
    schema_info: TelemetrySchemaData
    database: TelemetryDatabaseData
    prefect: TelemetryPrefectData
