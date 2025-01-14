from __future__ import annotations

import importlib

from prefect import Flow


def load_flow_function(module_path: str, flow_name: str) -> Flow:
    module = importlib.import_module(module_path)
    flow_func = getattr(module, flow_name)
    if not isinstance(flow_func, Flow):
        raise ValueError(
            f"Function loaded at {module_path=} with {flow_name=} has type {type(flow_func)}, expected {Flow}"
        )
    return flow_func
