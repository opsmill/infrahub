import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import pandas as pd
from infrahub_sdk import Timestamp
from neo4j import Record

# pylint: skip-file
from infrahub import config
from infrahub.database import InfrahubDatabase
from infrahub.log import get_logger

log = get_logger()


@dataclass
class QueryMeasurement:
    duration: float
    query_name: str
    start_time: float
    memory: Optional[float] = None
    index: Optional[int] = None
    profile: bool = False


class QueryAnalyzer:
    def __init__(self) -> None:
        self._start_time: Optional[Timestamp] = None
        self.name = "query_analyzer"
        self.index = 0
        self.measurements: List[QueryMeasurement] = []
        self.count_per_query: Dict[str, int] = defaultdict(int)
        self._df: Optional[pd.DataFrame] = None
        self.measure_memory_usage: bool = False
        self.sampling_memory_usage: int = 25
        self.output_location: Path = Path.cwd()

    @property
    def start_time(self) -> Timestamp:
        if self._start_time:
            return self._start_time
        raise ValueError("start_time hasnt't been initialized yet")

    def create_directory(self) -> Path:
        time_str = self.start_time.to_string()
        for char in [":", "-", "."]:
            time_str = time_str.replace(char, "_")
        directory_name = f"{time_str}_{self.name}"
        full_directory = self.output_location / directory_name
        if not full_directory.exists():
            full_directory.mkdir(parents=True)
        return full_directory

    def start_tracking(self, name: Optional[str] = None) -> None:
        self._start_time = Timestamp()
        self.index = 0
        if name:
            self.name = name

    def get_df(self) -> pd.DataFrame:
        data = {}
        for item in QueryMeasurement.__dataclass_fields__.keys():
            data[item] = [getattr(m, item) for m in self.measurements]

        return pd.DataFrame(data)

    def sample_memory(self, name: str) -> bool:
        if not self._start_time or not self.measure_memory_usage:
            return False

        if self.count_per_query[name] % self.sampling_memory_usage == 0:
            return True

        return False

    def add_measurement(self, measurement: QueryMeasurement) -> None:
        if not self._start_time:
            return

        self.index += 1
        measurement.index = self.index

        self.measurements.append(measurement)
        self.count_per_query[measurement.query_name] += 1

    def create_graphs(self, prefix: Optional[str] = None) -> None:
        df = self.get_df()
        query_names = set(df["query_name"].tolist())

        output_dir = self.create_directory()

        for query_name in query_names:
            self.create_duration_graph(
                query_name=query_name, metric="duration", prefix=self.name, output_dir=output_dir
            )
            self.create_memory_graph(query_name=query_name, metric="memory", prefix=self.name, output_dir=output_dir)

    def create_duration_graph(
        self, query_name: str, metric: str = "duration", prefix: Optional[str] = None, output_dir: Optional[Path] = None
    ) -> None:
        df = self.get_df()
        df_query = df[(df["query_name"] == query_name) & (df["profile"] == False)]  # noqa: E712

        name = f"{query_name}_{metric}"
        plt.figure(name)

        serie_name = f"{metric}"
        serie1 = df_query[metric].multiply(1000).round(2)
        plt.plot(df_query.index, serie1, label=serie_name)

        if len(df_query) < 50 * 20:
            serie_name = f"{metric}_mean_rolling50"
            serie2 = df_query[metric].rolling(50).mean().multiply(1000).round(2)
            plt.plot(df_query.index, serie2, label=serie_name)

        plt.ylabel("msec", fontsize=15)
        plt.title(f"Query - {query_name} | {metric}", fontsize=20)

        file_name = f"{name}.png"
        if prefix:
            file_name = f"{prefix}_{name}.png"

        if output_dir:
            plt.savefig(str(output_dir / file_name))
        else:
            plt.savefig(f"{self.start_time.to_string()}_{file_name}")

    def create_memory_graph(
        self, query_name: str, metric: str = "memory", prefix: Optional[str] = None, output_dir: Optional[Path] = None
    ) -> None:
        df = self.get_df()
        df_query = df[(df["query_name"] == query_name) & (df["profile"] == True)]  # noqa: E712

        plt.figure(query_name)

        serie_name = f"{metric}"
        serie1 = df_query[metric]
        plt.plot(df_query.index, serie1, label=serie_name)

        plt.ylabel("memory", fontsize=15)
        plt.title(f"Query - {query_name} | {metric}", fontsize=20)

        file_name = f"{query_name}_{metric}.png"
        if prefix:
            file_name = f"{prefix}_{query_name}_{metric}.png"

        if output_dir:
            plt.savefig(str(output_dir / file_name))
        else:
            plt.savefig(f"{self.start_time.to_string()}_{file_name}")


query_stats = QueryAnalyzer()


class InfrahubDatabaseAnalyzer(InfrahubDatabase):
    async def execute_query(
        self, query: str, params: config.Dict[str, Any] | None = None, name: str | None = "undefined"
    ) -> List[Record]:
        time_start = time.time()
        if name and query_stats.sample_memory(name=name):
            query = "PROFILE\n" + query
            response, metadata = await super().execute_query_with_metadata(query, params, name)
            duration_time = time.time() - time_start
            query_stats.add_measurement(
                QueryMeasurement(
                    duration=duration_time,
                    profile=True,
                    memory=metadata["profile"]["args"]["GlobalMemory"],
                    query_name=str(name),
                    start_time=time_start,
                )
            )
        else:
            response = await super().execute_query(query, params, name)
            duration_time = time.time() - time_start
            query_stats.add_measurement(
                QueryMeasurement(duration=duration_time, profile=False, query_name=str(name), start_time=time_start)
            )

        return response

    async def execute_query_with_metadata(
        self, query: str, params: config.Dict[str, Any] | None = None, name: str | None = "undefined"
    ) -> Tuple[List[Record], Dict[str, Any]]:
        time_start = time.time()
        if name and query_stats.sample_memory(name=name):
            query = "PROFILE\n" + query
            response, metadata = await super().execute_query_with_metadata(query, params, name)
            duration_time = time.time() - time_start
            query_stats.add_measurement(
                QueryMeasurement(
                    duration=duration_time,
                    profile=True,
                    memory=metadata["profile"]["args"]["GlobalMemory"],
                    query_name=str(name),
                    start_time=time_start,
                )
            )
        else:
            response, metadata = await super().execute_query_with_metadata(query, params, name)
            duration_time = time.time() - time_start
            query_stats.add_measurement(
                QueryMeasurement(duration=duration_time, profile=False, query_name=str(name), start_time=time_start)
            )

        return response, metadata
