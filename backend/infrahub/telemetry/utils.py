import importlib.metadata

from .constants import InfrahubType


def determine_infrahub_type() -> InfrahubType:
    try:
        importlib.metadata.version("infrahub-enterprise")
        return InfrahubType.ENTERPRISE
    except importlib.metadata.PackageNotFoundError:
        return InfrahubType.COMMUNITY
