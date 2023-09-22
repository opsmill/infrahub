from pydantic import BaseModel, Field


class ContentResponse(BaseModel):
    content: str = Field(..., description="The returned content")


class TemplateResponse(BaseModel):
    rendered_template: str = Field(..., description="The rendered template")


class TransformResponse(BaseModel):
    transformed_data: dict = Field(..., description="The data output of the transformation")


RESPONSE_MAP = {
    "content_response": ContentResponse,
    "template_response": TemplateResponse,
    "transform_response": TransformResponse,
}
