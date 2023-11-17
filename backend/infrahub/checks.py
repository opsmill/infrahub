from warnings import warn

from infrahub_sdk.checks import INFRAHUB_CHECK_VARIABLE_TO_IMPORT, InfrahubCheck

warn(
    f"The module {__name__} is deprecated. Update to use infrahub_sdk.checks instead.", DeprecationWarning, stacklevel=2
)

__all__ = ["INFRAHUB_CHECK_VARIABLE_TO_IMPORT", "InfrahubCheck"]
