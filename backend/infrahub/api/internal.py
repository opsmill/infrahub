from fastapi import APIRouter
from pydantic import BaseModel

import infrahub.config as config
from infrahub import __version__
from infrahub.config import AnalyticsSettings, LoggingSettings, MainSettings, FeaturesSettings
from infrahub.core import registry

router = APIRouter()


class ConfigAPI(BaseModel):
    main: MainSettings
    logging: LoggingSettings
    analytics: AnalyticsSettings
    features: FeaturesSettings


class InfoAPI(BaseModel):
    deployment_id: str
    version: str


@router.get("/config")
async def get_config() -> ConfigAPI:
    return ConfigAPI(main=config.SETTINGS.main, logging=config.SETTINGS.logging, analytics=config.SETTINGS.analytics, features=config.SETTINGS.features)


@router.get("/info")
async def get_info() -> InfoAPI:
    return InfoAPI(deployment_id=str(registry.id), version=__version__)
