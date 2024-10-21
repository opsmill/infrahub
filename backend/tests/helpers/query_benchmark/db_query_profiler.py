import time
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Any, List, Optional, Self, Type

import matplotlib.pyplot as plt
import pandas as pd
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


class GraphProfileGenerator:
    def build_df_from_measuremenst(self, measurements: list[QueryMeasurement]) -> pd.DataFrame:
        data = {}
        for item in QueryMeasurement.__dataclass_fields__.keys():
            data[item] = [getattr(m, item) for m in measurements]

        return pd.DataFrame(data)

    def create_graphs(self, measurements: List[QueryMeasurement], output_location: Path, label: str) -> None:
        df = self.build_df_from_measuremenst(measurements)
        query_names = set(df["query_name"].tolist())

        if not output_location.exists():
            output_location.mkdir(parents=True)

        for query_name in query_names:
            self.create_duration_graph(df=df, query_name=query_name, label=label, output_dir=output_location)
            # self.create_memory_graph(query_name=query_name, label=label, output_dir=output_location)

    def create_duration_graph(self, df: pd.DataFrame, query_name: str, label: str, output_dir: Path) -> None:
        metric = "duration"

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


class InfrahubDatabaseProfiler(InfrahubDatabase):
    profiling_enabled: bool
    profile_memory: bool
    measurements: List[QueryMeasurement]
    nb_elements_loaded: int

    def __init__(
        self,
        profiling_enabled: bool = False,
        profile_memory: bool = False,
        measurements: Optional[List[QueryMeasurement]] = None,
        nb_elements_loaded: int = 0,
        **kwargs: Any,
    ) -> None:  # todo args in constructor only because of __class__ pattern
        super().__init__(**kwargs)
        self.profiling_enabled = profiling_enabled
        self.profile_memory = profile_memory
        self.measurements = measurements if measurements is not None else []
        self.nb_elements_loaded = nb_elements_loaded
        # Note that any attribute added here should be added to get_context method.

    def get_context(self) -> dict[str, Any]:
        ctx = super().get_context()
        ctx["profiling_enabled"] = self.profiling_enabled
        ctx["profile_memory"] = self.profile_memory
        ctx["measurements"] = self.measurements
        ctx["nb_elements_loaded"] = self.nb_elements_loaded
        return ctx

    async def execute_query_with_metadata(
        self,
        query: str,
        params: dict[str, Any] | None = None,
        name: str | None = "undefined",
        context: dict[str, str] | None = None,
    ) -> tuple[list[Record], dict[str, Any]]:
        if not self.profiling_enabled:
            # Profiling might be disabled to avoid capturing queries while loading data
            return await super().execute_query_with_metadata(query, params, name)

        # We don't want to memory profile all queries
        if self.profile_memory and name in self.queries_names_to_config:
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
            nb_elements_loaded=self.nb_elements_loaded,
        )
        self.measurements.append(measurement)

        return response, metadata

    def profile(self, profile_memory: bool) -> Self:
        """
        This method allows to enable profiling of a InfrahubDatabaseProfiler instance
        through a context manager with this syntax:

        `with db.profile(profile_memory=...):
            # run code to profile
        `
        """

        self.profile_memory = profile_memory
        return self

    def __enter__(self) -> None:
        self.profiling_enabled = True
        self.profile_memory = self.profile_memory

    def __exit__(
        self, exc_type: Optional[Type[BaseException]], exc_val: Optional[BaseException], exc_tb: Optional[TracebackType]
    ) -> None:
        self.profiling_enabled = False
        self.profile_memory = False

    def increase_nb_elements_loaded(self, nb_elements_loaded: int) -> None:
        self.nb_elements_loaded += nb_elements_loaded
