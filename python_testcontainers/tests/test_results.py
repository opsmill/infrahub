import time

import pytest
from infrahub_testcontainers.measurements import (
    BRANCH_MERGE_TIME,
    SCRIPT_EXECUTION_TIME,
)
from infrahub_testcontainers.models import ContextUnit
from infrahub_testcontainers.performance_test import InfrahubPerformanceTest


def test_initialize_performance_test(perf_test: InfrahubPerformanceTest) -> None:
    perf_test.add_context("test2", 200, ContextUnit.COUNT)

    perf_test.initialize("test_results")

    with perf_test.start_measurement(SCRIPT_EXECUTION_TIME, name="test3"):
        time.sleep(1)


@pytest.mark.performance_load_backup
def test_load_from_backup(perf_test: InfrahubPerformanceTest) -> None:
    perf_test.add_measurement(BRANCH_MERGE_TIME, value=100)


@pytest.mark.performance_load_data
def test_load_initial_dataset(perf_test: InfrahubPerformanceTest) -> None:
    perf_test.add_measurement(BRANCH_MERGE_TIME, value=100)


@pytest.mark.performance_create_backup
def test_create_database_backup(perf_test: InfrahubPerformanceTest) -> None:
    perf_test.add_measurement(BRANCH_MERGE_TIME, value=100)
