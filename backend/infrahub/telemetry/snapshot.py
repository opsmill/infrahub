from __future__ import annotations

from typing import Any

from pydantic import Field, field_validator

from infrahub.core.node.standard import StandardNode

from .constants import RemoteSendStatus


class TelemetrySnapshot(StandardNode):
    kind: str
    payload_format: str
    deployment_id: str
    infrahub_version: str
    data: dict[str, Any]
    checksum: str
    remote_send_status: RemoteSendStatus = Field(default=RemoteSendStatus.PENDING)

    @field_validator("kind")
    @classmethod
    def kind_must_be_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("kind must be a non-empty string")
        return v

    @field_validator("payload_format")
    @classmethod
    def payload_format_must_be_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("payload_format must be a non-empty string")
        return v

    @field_validator("checksum")
    @classmethod
    def checksum_must_be_valid_sha256(cls, v: str) -> str:
        if len(v) != 64 or not all(c in "0123456789abcdef" for c in v):
            raise ValueError("checksum must be a 64-character lowercase hex string (SHA-256)")
        return v

    @field_validator("data")
    @classmethod
    def data_must_be_non_empty(cls, v: dict[str, Any]) -> dict[str, Any]:
        if not v:
            raise ValueError("data must be a non-empty dict")
        return v
