from abc import abstractmethod
from pathlib import Path
from typing import Callable, Optional

from rich.console import Console
from rich.progress import Progress

from tests.helpers.query_benchmark.db_query_profiler import (
    GraphProfileGenerator,
    InfrahubDatabaseProfiler,
)


class DataGenerator:
    """
    Abstract class responsible for loading data into a given database.
    """

    def __init__(self, db: InfrahubDatabaseProfiler) -> None:
        self.db = db

    async def init(self) -> None:
        """
        Any previous step before loading and profiling data should be implemented here.
        """

    @abstractmethod
    async def load_data(self, nb_elements: int) -> None:
        raise NotImplementedError("Abstract method")


async def load_data_and_profile(
    data_generator: DataGenerator,
    nb_elements: int,
    func_call: Callable,
    profile_frequency: int,
    graphs_output_location: Path,
    test_label: str,
    graph_generator: GraphProfileGenerator,
    memory_profiling_rate: Optional[int] = None,
) -> None:
    """
    Loads data using the provided data generator, profiles the execution at specified loading intervals,
    and generate profiling graphs.

    Args:
        data_generator (DataGenerator): Object responsible for loading data.
        nb_elements (int): The number of elements to generate by DataGenerator.
        func_call (FuncCall): Contains function to profile and its arguments.
        profile_frequency (int): The frequency, in terms of number of elements, at which function to profile will be executed and profiled.
        graphs_output_location (Path): Path to the directory where profiling graphs will be saved.
        test_label (str): A label or identifier for the test, used to name or organize the outputs.
        memory_profiling_rate (int): Indicates at which rate memory should be profiled. Frequency is related to number of function execution times,
                                     not to the number of elements as for 'profile_frequency'. For instance, memory_profiling_rate=25
                                     means memory is profiled every 25 times a function is executed/profiled.
    """

    await data_generator.init()

    q, r = divmod(nb_elements, profile_frequency)
    nb_elem_per_batch = [profile_frequency] * q + ([r] if r else [])

    db_profiling_queries = data_generator.db

    with Progress(console=Console(force_terminal=True)) as progress:  # Need force_terminal to display with pytest
        task = progress.add_task(
            f"Loading elements from {data_generator.__class__.__name__}", total=len(nb_elem_per_batch)
        )

        for i, nb_elem_to_load in enumerate(nb_elem_per_batch):
            await data_generator.load_data(nb_elements=nb_elem_to_load)
            db_profiling_queries.increase_nb_elements_loaded(nb_elem_to_load)
            profile_memory = i % memory_profiling_rate == 0 if memory_profiling_rate is not None else False
            with db_profiling_queries.profile(profile_memory):
                await func_call()
            progress.advance(task)

        # Remove first measurements as queries when there is no data seem always extreme
        measurements = [m for m in db_profiling_queries.measurements if m.nb_elements_loaded != 0]
        graph_generator.create_graphs(
            measurements=measurements, output_location=graphs_output_location, label=test_label
        )
