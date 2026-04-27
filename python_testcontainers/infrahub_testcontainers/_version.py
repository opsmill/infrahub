import importlib.metadata

try:
    __version__ = importlib.metadata.version("infrahub-testcontainers")
except importlib.metadata.PackageNotFoundError:
    __version__ = importlib.metadata.version("infrahub-server")
