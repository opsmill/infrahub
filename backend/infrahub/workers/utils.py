from __future__ import annotations

import importlib
import inspect
from typing import TYPE_CHECKING, Any

from prefect import Flow

from infrahub.context import InfrahubContext

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

    if service_parameter_name := get_parameter_name(func=func, types=[InfrahubServices.__name__, InfrahubServices]):
        if any(isinstance(param_value, InfrahubServices) for param_value in parameters):
            raise ValueError(f"{func.name} parameters contains an InfrahubServices object while it should be injected")
        parameters[service_parameter_name] = service
        return


def inject_context_parameter(func: Flow, parameters: dict[str, Any], context: InfrahubContext | None = None) -> None:
    service_parameter_name = get_parameter_name(func=func, types=[InfrahubContext.__name__, InfrahubContext])
    if service_parameter_name and context:
        parameters[service_parameter_name] = context
        return

    if service_parameter_name and not context:
        raise ValueError(
            f"{func.name} has a {service_parameter_name} parameter of type InfrahubContext, while context is not provided"
        )


def load_flow_function(module_path: str, flow_name: str) -> Flow:
    module = importlib.import_module(module_path)
    flow_func = getattr(module, flow_name)
    if not isinstance(flow_func, Flow):
        raise ValueError(
            f"Function loaded at {module_path=} with {flow_name=} has type {type(flow_func)}, expected {Flow}"
        )
    return flow_func


def get_parameter_name(func: Flow, types: list[Any]) -> str | None:
    sig = inspect.signature(func)
    for sig_param in sig.parameters.values():
        if sig_param.annotation in types:
            return sig_param.name
    return None


def has_parameter(func: Flow, types: list[Any]) -> bool:
    return get_parameter_name(func=func, types=types) is not None
