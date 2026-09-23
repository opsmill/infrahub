from __future__ import annotations

from pydantic import BaseModel, Field


class ServiceRequestRun(BaseModel):
    """Fulfils a service request placed through the Service Portal."""

    request_id: str = Field(..., description="The ID of the CoreServiceRequest to fulfil")
