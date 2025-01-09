from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

from prefect import Flow

if TYPE_CHECKING:
    from infrahub.services import InfrahubServices

# TODO solve this circular issue. we should have no ref to WorkflowLocalExec within InfrahubServices


def inject_service_parameter(service: InfrahubServices, parameters: dict[str, Any]) -> None:
    """
    `service` object instantiates connections to various services (db, cache...) at worker startup,
    # so it is not meant to be sent by the server payload. We inject it here to avoid relying on a global variable.
    This mutates input `parameters`.
    """

    assert "service" not in parameters
    parameters["service"] = service


def load_flow_function(module_path: str, flow_name: str) -> Flow:
    module = importlib.import_module(module_path)
    flow_func = getattr(module, flow_name)
    assert isinstance(flow_func, Flow)
    return flow_func
