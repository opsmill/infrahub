from typing import Optional

from pydantic import BaseSettings, Field


class Config(BaseSettings):
    api_token: Optional[str] = Field(default=None, description="API token for authentication against Infrahub.")

    class Config:
        env_prefix = "INFRAHUB_SDK_"
        case_sensitive = False
