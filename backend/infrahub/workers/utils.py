from __future__ import annotations

import importlib
import inspect
from typing import TYPE_CHECKING, Any

from prefect import Flow

if TYPE_CHECKING:
    from infrahub.services import InfrahubServices


def inject_service_parameter(func: Flow, parameters: dict[str, Any], service: InfrahubServices) -> None:
    """
    `service` object instantiates connections to various services (db, cache...) at worker startup,
    so it is not meant to be sent by the server payload. We inject it here to avoid relying on a global variable.
    This mutates input `parameters`.
    """

    # avoid circular imports
    from infrahub.services import InfrahubServices  # pylint: disable=C0415

    sig = inspect.signature(func)
    for sig_param in sig.parameters.values():
        if sig_param.annotation in [InfrahubServices.__name__, InfrahubServices]:  # why it can be both?
            if any(isinstance(param_value, InfrahubServices) for param_value in parameters):
                raise ValueError(f"{func} parameters contains an InfrahubServices object while it should be injected")
            parameters[sig_param.name] = service
            return


def load_flow_function(module_path: str, flow_name: str) -> Flow:
    module = importlib.import_module(module_path)
    flow_func = getattr(module, flow_name)
    if not isinstance(flow_func, Flow):
        raise ValueError(
            f"Function loaded at {module_path=} with {flow_name=} has type {type(flow_func)}, expected {Flow}"
        )
    return flow_func
