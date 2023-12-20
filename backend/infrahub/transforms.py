from warnings import warn

from infrahub_sdk.transforms import INFRAHUB_TRANSFORM_VARIABLE_TO_IMPORT, InfrahubTransform

warn(
    f"The module {__name__} is deprecated. Update to use infrahub_sdk.transforms instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["INFRAHUB_TRANSFORM_VARIABLE_TO_IMPORT", "InfrahubTransform"]
