from __future__ import annotations

import importlib
import inspect
from types import NoneType, UnionType
from typing import Any, Union, get_args, get_origin

from prefect import Flow

from infrahub.context import InfrahubContext
from infrahub.events.models import EventContext


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
    """Return the name of the first parameter annotated with one of ``types``, optional or not."""
    sig = inspect.signature(func)
    for sig_param in sig.parameters.values():
        if _without_none(sig_param.annotation) in types:
            return sig_param.name
    return None


def _without_none(annotation: Any) -> Any:
    if isinstance(annotation, str):
        return annotation.removesuffix(" | None")
    if get_origin(annotation) in {Union, UnionType}:
        members = [member for member in get_args(annotation) if member is not NoneType]
        if len(members) == 1:
            return members[0]
    return annotation


def has_parameter(func: Flow, types: list[Any]) -> bool:
    return get_parameter_name(func=func, types=types) is not None
