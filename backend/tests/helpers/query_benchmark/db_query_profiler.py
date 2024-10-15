import time
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Any, Optional, Type

import matplotlib.pyplot as plt
import pandas as pd
from infrahub_sdk import Timestamp
from neo4j import Record

from infrahub.config import SETTINGS

# pylint: skip-file
from infrahub.database import InfrahubDatabase
from infrahub.database.constants import Neo4jRuntime
from infrahub.log import get_logger
from tests.helpers.constants import NEO4J_ENTERPRISE_IMAGE

log = get_logger()


@dataclass
class BenchmarkConfig:
    neo4j_image: str = NEO4J_ENTERPRISE_IMAGE
    neo4j_runtime: Neo4jRuntime = Neo4jRuntime.DEFAULT
    load_db_indexes: bool = False

    def __str__(self) -> str:
        return f"{self.neo4j_image=} ; runtime: {self.neo4j_runtime} ; indexes: {self.load_db_indexes}"


@dataclass
class QueryMeasurement:
    duration: float
    query_name: str
    start_time: float
    nb_elements_loaded: Optional[int] = None
    memory: Optional[float] = None


class QueryAnalyzer:
    _start_time: Optional[Timestamp]
    name: Optional[str]
    count: int
    measurements: list[QueryMeasurement]
    count_per_query: dict[str, int]
    _df: Optional[pd.DataFrame]
    measure_memory_usage: bool
    sampling_memory_usage: int
    output_location: Path
    neo4j_runtime: Neo4jRuntime
    nb_elements_loaded: int
    query_to_nb_elts_loaded_to_measurements: dict[str, dict[int, QueryMeasurement]]
    profile_memory: bool
    profile_duration: bool

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._start_time = Timestamp()
        self.name = None
        self.count = 0
        self.measurements = []
        self.query_to_nb_elts_loaded_to_measurements = {}
        self._df = None
        self.output_location = Path.cwd()
        self.neo4j_runtime = Neo4jRuntime.DEFAULT
        self.nb_elements_loaded = 0
        self.profile_duration = False
        self.profile_memory = False

    def increase_nb_elements_loaded(self, increment: int) -> None:
        self.nb_elements_loaded += increment

    @property
    def start_time(self) -> Timestamp:
        if self._start_time:
            return self._start_time
        raise ValueError("start_time hasnt't been initialized yet")

    def create_directory(self, prefix: str, output_location: Path) -> Path:
        time_str = self.start_time.to_string()
        for char in [":", "-", "."]:
            time_str = time_str.replace(char, "_")
        directory_name = f"{time_str}_{prefix}"
        full_directory = output_location / directory_name
        if not full_directory.exists():
            full_directory.mkdir(parents=True)
        return full_directory

    def get_df(self) -> pd.DataFrame:
        data = {}
        for item in QueryMeasurement.__dataclass_fields__.keys():
            data[item] = [getattr(m, item) for m in self.measurements]

        return pd.DataFrame(data)

    def add_measurement(self, measurement: QueryMeasurement) -> None:
        measurement.nb_elements_loaded = self.nb_elements_loaded
        self.measurements.append(measurement)

    def create_graphs(self, output_location: Path, label: str) -> None:
        df = self.get_df()
        query_names = set(df["query_name"].tolist())

        if not output_location.exists():
            output_location.mkdir(parents=True)

        for query_name in query_names:
            self.create_duration_graph(query_name=query_name, label=label, output_dir=output_location)
            # self.create_memory_graph(query_name=query_name, label=label, output_dir=output_location)

    def create_duration_graph(self, query_name: str, label: str, output_dir: Path) -> None:
        metric = "duration"
        df = self.get_df()

        name = f"{query_name}_{metric}"
        plt.figure(name)

        df_query = df[(df["query_name"] == query_name) & (df["memory"].isna())].sort_values(
            by="start_time", ascending=True
        )
        x = df_query["nb_elements_loaded"].values
        y = df_query[metric].values * 1000
        plt.plot(x, y, label=label)

        plt.legend(bbox_to_anchor=(1.04, 1), borderaxespad=0)

        plt.ylabel("msec", fontsize=15)
        plt.title(f"Query - {query_name} | {metric}", fontsize=20)
        plt.grid()

        file_name = f"{name}.png"
        plt.savefig(str(output_dir / file_name), bbox_inches="tight")

    def create_memory_graph(self, query_name: str, label: str, output_dir: Path) -> None:
        metric = "memory"
        df = self.get_df()
        df_query = df[(df["query_name"] == query_name) & (~df["memory"].isna())]

        plt.figure(query_name)

        x = df_query["nb_elements_loaded"].values
        y = df_query[metric].values

        plt.plot(x, y, label=label)

        plt.legend()

        plt.ylabel("memory", fontsize=15)
        plt.title(f"Query - {query_name} | {metric}", fontsize=20)

        file_name = f"{query_name}_{metric}.png"

        plt.savefig(str(output_dir / file_name))


class ProfilerEnabler:
    profile_memory: bool

    def __init__(self, profile_memory: bool, query_analyzer: QueryAnalyzer) -> None:
        self.profile_memory = profile_memory
        self.query_analyzer = query_analyzer

    def __enter__(self) -> None:
        self.query_analyzer.profile_duration = True
        self.query_analyzer.profile_memory = self.profile_memory

    def __exit__(
        self, exc_type: Optional[Type[BaseException]], exc_val: Optional[BaseException], exc_tb: Optional[TracebackType]
    ) -> None:
        self.query_analyzer.profile_duration = False
        self.query_analyzer.profile_memory = False


# Tricky to have it as an attribute of InfrahubDatabaseProfiler as some copies of InfrahubDatabase are made
# during start_session calls.
# query_analyzer = QueryAnalyzer()


class InfrahubDatabaseProfiler(InfrahubDatabase):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.query_analyzer = QueryAnalyzer()
        # Note that any attribute added here should be added to get_context method.

    def get_context(self) -> dict[str, Any]:
        ctx = super().get_context()
        ctx["query_analyzer"] = self.query_analyzer
        return ctx

    async def execute_query_with_metadata(
        self, query: str, params: dict[str, Any] | None = None, name: str | None = "undefined"
    ) -> tuple[list[Record], dict[str, Any]]:
        if not self.query_analyzer.profile_duration:
            # Profiling might be disabled to avoid capturing queries while loading data
            return await super().execute_query_with_metadata(query, params, name)

        # We don't want to memory profile all queries
        if self.query_analyzer.profile_memory and name in self.queries_names_to_config:
            # Following call to super().execute_query_with_metadata() will use this value to set PROFILE option
            self.queries_names_to_config[name].profile_memory = True
            profile_memory = True
        else:
            profile_memory = False

        assert profile_memory is False, "Do not profile memory for now"

        # Do the query and measure duration
        time_start = time.time()
        response, metadata = await super().execute_query_with_metadata(query, params, name)
        duration_time = time.time() - time_start

        assert len(response) < SETTINGS.database.query_size_limit // 2, "make sure data return is small"

        measurement = QueryMeasurement(
            duration=duration_time,
            memory=metadata["profile"]["args"]["GlobalMemory"] if profile_memory else None,
            query_name=str(name),
            start_time=time_start,
        )
        self.query_analyzer.add_measurement(measurement)

        return response, metadata
