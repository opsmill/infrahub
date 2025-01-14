from pydantic import BaseModel


class SchemaViolation(BaseModel):
    node_id: str
    node_kind: str
    display_label: str
    full_display_label: str
    message: str = ""
