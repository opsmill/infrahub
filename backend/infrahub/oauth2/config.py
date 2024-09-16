from fastapi_oauth2.claims import Claims
from fastapi_oauth2.client import OAuth2Client
from fastapi_oauth2.config import OAuth2Config
from social_core.backends.google import GoogleOAuth2

from infrahub import config


def create_config() -> OAuth2Config:
    clients: list[OAuth2Client] = []
    match config.SETTINGS.security.oauth2_provider:
        case config.Oauth2Provider.GOOGLE:
            provider_settings = config.SETTINGS.security.get_oauth_settings(provider=config.Oauth2Provider.GOOGLE)
            clients.append(
                OAuth2Client(
                    backend=GoogleOAuth2,
                    client_id=provider_settings.client_id,
                    client_secret=provider_settings.client_secret,
                    scope=["openid", "profile", "email"],
                    claims=Claims(
                        identity=lambda user: f"{user.provider}:{user.sub}",
                    ),
                )
            )

    return OAuth2Config(
        allow_http=True,
        jwt_secret=config.SETTINGS.security.secret_key,
        jwt_expires=config.SETTINGS.security.access_token_lifetime,
        jwt_algorithm="HS256",
        clients=clients,
    )
