from typing import Any, Dict, Optional, Set

from pydantic import BaseModel, ConfigDict

from infrahub.database import InfrahubDatabase


class ToGraphQLRequest(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    obj: Any
    db: InfrahubDatabase
    fields: Optional[Dict[str, Any]] = None
    related_node_ids: Optional[Set[str]] = None
    filter_sensitive: bool = False
