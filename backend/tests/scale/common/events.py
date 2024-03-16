import logging
import os
from csv import DictWriter
from functools import wraps

import gevent
from locust import events
from locust.env import Environment
from locust.exception import StopUser
from locust.runners import Runner, WorkerRunner
from locust.user.task import DefaultTaskSet, TaskSet

from .config import config
from .utils import get_container_resource_usage, get_graphdb_stats

METRICS_FIELD_NAMES = [
    "metric_value",
    "timestamp",
    "operation_name",
    "stage",
    "node_amount",
    "attrs_amount",
    "rels_amount",
]


@events.test_start.add_listener
def setup_iteration_limit(environment: Environment, **kwargs):
    runner: Runner = environment.runner
    runner.iterations_started = 0
    runner.iteration_target_reached = False
    logging.debug(f"Iteration limit set to {config.test_task_iterations}")

    def iteration_limit_wrapper(method):
        @wraps(method)
        def wrapped(self, task):
            if runner.iterations_started == config.test_task_iterations:
                if not runner.iteration_target_reached:
                    runner.iteration_target_reached = True
                    logging.info(
                        f"Iteration limit reached ({config.test_task_iterations}), stopping Users at the start of their next task run"
                    )
                if runner.user_count == 1:
                    logging.info("Last user stopped, quitting runner")
                    if isinstance(runner, WorkerRunner):
                        runner._send_stats()  # send a final report
                    # need to trigger this in a separate greenlet, in case test_stop handlers do something async
                    gevent.spawn_later(0.1, runner.quit)
                raise StopUser()
            runner.iterations_started = runner.iterations_started + 1
            method(self, task)

        return wrapped

    # monkey patch TaskSets to add support for iterations limit. Not ugly at all :)
    TaskSet.execute_task = iteration_limit_wrapper(TaskSet.execute_task)
    DefaultTaskSet.execute_task = iteration_limit_wrapper(DefaultTaskSet.execute_task)


@events.request.add_listener
def request_event_handler(
    request_type, name, response_time, response_length, response, context, exception, start_time, **kwargs
):
    result = {
        "name": name,
        "start_time": f"{start_time:.2f}",
        "response_time": f"{response_time:.2f}ms",
        "failed": True if exception else False,
    }

    if os.getenv("CI") is None:
        server_container_stats = get_container_resource_usage(config.server_container)
        db_container_stats = get_container_resource_usage(config.db_container)
        graphdb_stats = get_graphdb_stats()

        result["server_cpu"] = f"{server_container_stats.cpu_usage:.2f}%"
        result["server_memory"] = f"{server_container_stats.memory_usage}B"
        result["db_cpu"] = f"{db_container_stats.cpu_usage:.2f}%"
        result["db_memory"] = f"{db_container_stats.memory_usage}B"

        result["db_size"] = f"{graphdb_stats.db_size}B"
        result["db_node_count"] = graphdb_stats.node_count
        result["db_rel_count"] = graphdb_stats.rel_count

    output = []
    output = [f"{k}={v}" for k, v in result.items()]
    print(", ".join(output))

    result_metric = {
        "metric_value": response_time,
        "timestamp": int(start_time * 1000),
        "operation_name": name,
        "stage": config.current_stage,
        "node_amount": config.node_amount,
        "attrs_amount": config.attrs_amount,
        "rels_amount": config.rels_amount,
    }

    with open("metrics.csv", "a", encoding="utf-8") as file:
        writer = DictWriter(file, fieldnames=METRICS_FIELD_NAMES)
        writer.writerow(result_metric)
