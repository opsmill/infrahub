from typing import Any, Dict, Optional

from pydantic import BaseSettings, Field, root_validator


class Config(BaseSettings):
    api_token: Optional[str] = Field(default=None, description="API token for authentication against Infrahub.")
    username: Optional[str] = Field(default=None, description="Username for accessing Infrahub", min_length=1)
    password: Optional[str] = Field(default=None, description="Password for accessing Infrahub", min_length=1)

    class Config:
        env_prefix = "INFRAHUB_SDK_"
        case_sensitive = False

    @root_validator(pre=True)
    @classmethod
    def validate_credentials_input(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        has_username = "username" in values
        has_password = "password" in values
        if has_username != has_password:
            raise ValueError("Both 'username' and 'password' needs to be set")
        return values

    @root_validator(pre=True)
    @classmethod
    def validate_mix_authentication_schemes(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        if values.get("password") and values.get("api_token"):
            raise ValueError("Unable to combine password with token based authentication")
        return values

    @property
    def password_authentication(self) -> bool:
        if self.username:
            return True
        return False
