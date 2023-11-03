from typing import Dict

from pydantic import BaseModel


class RepositoryData(BaseModel):
    id: str
    name: str
    location: str
    branches: Dict[str, str]
