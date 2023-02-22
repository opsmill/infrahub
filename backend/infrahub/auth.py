from __future__ import annotations

from typing import TYPE_CHECKING, Awaitable, Callable, List, Optional

from starlette import authentication as auth
from starlette.authentication import AuthenticationError
from starlette.requests import HTTPConnection

import infrahub.config as config
from infrahub.core import get_account
from infrahub.core.account import validate_token

if TYPE_CHECKING:
    from neo4j import AsyncSession

# from ..datatypes import AuthResult
# from ..exceptions import InvalidCredentials

# Code copied from https://github.com/florimondmanca/starlette-auth-toolkit/


class InvalidCredentials(AuthenticationError):
    def __init__(
        self,
        message: str = "Could not authenticate with the provided credentials",
    ):
        super().__init__(message)


class AuthBackend(auth.AuthenticationBackend):
    async def authenticate(self, conn: HTTPConnection):  # -> AuthResult:
        raise NotImplementedError


class _BaseSchemeAuth(AuthBackend):
    scheme: str

    def get_credentials(self, conn: HTTPConnection) -> Optional[str]:
        if "Authorization" not in conn.headers:
            return None

        authorization = conn.headers.get("Authorization")
        scheme, _, credentials = authorization.partition(" ")
        if scheme.lower() != self.scheme.lower():
            return None

        return credentials

    def parse_credentials(self, credentials: str) -> List[str]:
        return [credentials]

    verify: Callable[..., Awaitable[Optional[auth.BaseUser]]]

    async def authenticate(self, conn: HTTPConnection):
        credentials = self.get_credentials(conn)
        if credentials is None:
            return None

        parts = self.parse_credentials(credentials)

        async with conn.app.state.db.session(database=config.SETTINGS.database.database) as session:
            user = await self.verify(session=session, token=parts[0])

        if user is None:
            raise InvalidCredentials

        return auth.AuthCredentials(["authenticated"]), user


# class BaseBasicAuth(_BaseSchemeAuth):
#     scheme = "Basic"

#     def parse_credentials(self, credentials: str) -> typing.List[str]:
#         try:
#             decoded_credentials = base64.b64decode(credentials).decode("ascii")
#         except (ValueError, UnicodeDecodeError, binascii.Error):
#             raise InvalidCredentials

#         try:
#             username, password = decoded_credentials.split(":")
#         except ValueError:
#             raise InvalidCredentials

#         return [username, password]

#     async def find_user(self, username: str) -> typing.Optional[auth.BaseUser]:
#         raise NotImplementedError

#     async def verify_password(self, user: auth.BaseUser, password: str) -> bool:
#         raise NotImplementedError

#     async def verify(
#         self, username: str, password: str
#     ) -> typing.Optional[auth.BaseUser]:
#         user = await self.find_user(username=username)

#         if user is None:
#             return None

#         valid = await self.verify_password(user, password)
#         if not valid:
#             return None

#         return user


class BaseTokenAuth(_BaseSchemeAuth):
    scheme = "Token"

    def parse_credentials(self, credentials: str) -> List[str]:
        token = credentials
        return [token]

    async def verify(self, session: AsyncSession, token: str) -> Optional[auth.BaseUser]:
        if account_name := await validate_token(session=session, token=token):
            account = await get_account(session=session, account=account_name)
            return account

        return False
