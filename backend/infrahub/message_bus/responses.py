from typing import List

from pydantic.v1 import BaseModel, Field


class ContentResponse(BaseModel):
    content: str = Field(..., description="The returned content")


class DiffNamesResponse(BaseModel):
    files_added: List[str] = Field(..., description="Files added")
    files_changed: List[str] = Field(..., description="Files changed")
    files_removed: List[str] = Field(..., description="Files removed")


class TemplateResponse(BaseModel):
    rendered_template: str = Field(..., description="The rendered template")


class TransformResponse(BaseModel):
    transformed_data: dict = Field(..., description="The data output of the transformation")


RESPONSE_MAP = {
    "content_response": ContentResponse,
    "diffnames_response": DiffNamesResponse,
    "template_response": TemplateResponse,
    "transform_response": TransformResponse,
}
