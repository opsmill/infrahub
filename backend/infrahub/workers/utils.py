from __future__ import annotations

import importlib

from prefect import Flow


def load_flow_function(module_path: str, flow_name: str) -> Flow:
    module = importlib.import_module(module_path)
    flow_func = getattr(module, flow_name)
    assert isinstance(flow_func, Flow)
    return flow_func
