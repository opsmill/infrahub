from typing import Dict

try:
    from pydantic import v1 as pydantic  # type: ignore[attr-defined]
except ImportError:
    import pydantic  # type: ignore[no-redef]


class RepositoryData(pydantic.BaseModel):
    id: str
    name: str
    location: str
    branches: Dict[str, str]
