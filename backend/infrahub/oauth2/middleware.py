from fastapi_oauth2.middleware import OAuth2Middleware
from starlette.types import ASGIApp

from infrahub import config
from infrahub.oauth2.config import create_config


class InfrahubOAuth2Middleware(OAuth2Middleware):
    def __init__(self, app: ASGIApp):
        config.SETTINGS.initialize_and_exit()
        super().__init__(app, config=create_config())
