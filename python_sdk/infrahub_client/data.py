from typing import Dict, Optional

from pydantic import BaseModel


class RepositoryData(BaseModel):
    id: str
    name: str
    location: str
    branches: Dict[str, str]
