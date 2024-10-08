import uuid

from pydantic import BaseModel, Field


class PasswordCredential(BaseModel):
    username: str = Field(..., description="Name of the user that is logging in.")
    password: str = Field(..., description="The password of the user.")


class UserToken(BaseModel):
    access_token: str = Field(..., description="JWT access_token")
    refresh_token: str = Field(..., description="JWT refresh_token")


class UserTokenWithUrl(UserToken):
    final_url: str = Field(..., description="The final url after logged in")


class AccessTokenResponse(BaseModel):
    access_token: str = Field(..., description="JWT access_token")


class RefreshTokenData(BaseModel):
    account_id: str
    session_id: uuid.UUID
