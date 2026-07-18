from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PayloadBase(BaseModel):
    """Common configuration for all catalogue payload models."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class NodeNotFoundData(PayloadBase):
    node_kind: str
    identifier: str


class AuthenticationRequiredData(PayloadBase):
    pass


class TokenExpiredData(PayloadBase):
    expired_at: datetime | None = None


class PermissionDeniedData(PayloadBase):
    action: str | None = None
    resource_kind: str | None = None


class AttributeRequiredData(PayloadBase):
    node_kind: str
    field_name: str


class AttributeInvalidTypeData(PayloadBase):
    node_kind: str
    field_name: str
    expected_type: str
    received_type: str


class AttributeConstraintViolationData(PayloadBase):
    node_kind: str
    field_name: str
    constraint: str
    detail: str | None = None


class BranchNotFoundData(PayloadBase):
    branch_name: str


class SchemaNotFoundData(PayloadBase):
    kind: str


class UndefinedErrorData(PayloadBase):
    pass
