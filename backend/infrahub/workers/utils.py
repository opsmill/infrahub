from __future__ import annotations

import importlib
import inspect
from typing import TYPE_CHECKING, Any

from prefect import Flow

from infrahub.context import InfrahubContext
from infrahub.events.models import EventContext

if TYPE_CHECKING:
    from infrahub.services import InfrahubServices


def inject_service_parameter(func: Flow, parameters: dict[str, Any], service: InfrahubServices) -> None:
    """`service` object instantiates connections to various services (db, cache...) at worker startup,.

    so it is not meant to be sent by the server payload. We inject it here to avoid relying on a global variable.

    This mutates input `parameters`.

    Raises:
        ValueError: When ``parameters`` already contains an ``InfrahubServices`` instance.

    """
    # avoid circular imports
    from infrahub.services import InfrahubServices

    if service_parameter_name := get_parameter_name(func=func, types=[InfrahubServices.__name__, InfrahubServices]):
        if any(isinstance(param_value, InfrahubServices) for param_value in parameters):
            raise ValueError(f"{func.name} parameters contains an InfrahubServices object while it should be injected")
        parameters[service_parameter_name] = service
        return


def inject_context_parameter(
    func: Flow,
    parameters: dict[str, Any],
    context: InfrahubContext | EventContext | None = None,
) -> None:
    """Inject the workflow context into ``parameters`` if the flow declares one.

    Raises:
        ValueError: When the flow declares a context parameter but ``context`` is None.

    """
    infrahub_param = get_parameter_name(func=func, types=[InfrahubContext.__name__, InfrahubContext])
    event_param = get_parameter_name(func=func, types=[EventContext.__name__, EventContext])
    target_param = infrahub_param or event_param

    if target_param is None:
        return

    if context is None:
        raise ValueError(f"{func.name} has a {target_param} parameter, while context is not provided")

    if event_param and not infrahub_param and isinstance(context, InfrahubContext):
        parameters[event_param] = context.to_event_context()
        return

    parameters[target_param] = context


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
