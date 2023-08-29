from pydantic import BaseModel, Field


class TemplateResponse(BaseModel):
    rendered_template: str = Field(..., description="The unique ID of the Artifact Definition")


RESPONSE_MAP = {"template_response": TemplateResponse}
