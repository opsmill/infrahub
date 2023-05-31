from pydantic import BaseModel, Field


class PasswordCredential(BaseModel):
    username: str = Field(..., description="Name of the user that is logging in.")
    password: str = Field(..., description="The password of the user.")


class UserToken(BaseModel):
    access_token: str = Field(..., description="JWT access_token")
