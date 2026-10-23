from datetime import datetime
from typing import Self

from pydantic import Field, model_validator

from infrahub.message_bus import InfrahubMessage


class RefreshSettingsTraceSampleRatio(InfrahubMessage):
    """Broadcast to set or clear the temporary trace sampling ratio on every API server process and task worker."""

    ratio: float | None = Field(
        default=None,
        ge=0,
        le=1,
        allow_inf_nan=False,
        description="Share of new root traces to record until expires_at; None clears the temporary ratio",
    )
    expires_at: datetime | None = Field(default=None, description="UTC time when the temporary ratio stops applying")

    @model_validator(mode="after")
    def validate_ratio_and_expires_at_set_together(self) -> Self:
        """Require `ratio` and `expires_at` to be both set or both empty.

        Raises:
            ValueError: If only one of them is set.

        """
        if (self.ratio is None) != (self.expires_at is None):
            raise ValueError("ratio and expires_at must be both set or both empty")
        return self
