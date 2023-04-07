from fastapi import APIRouter
from pydantic import BaseModel

import infrahub.config as config
from infrahub import __version__
from infrahub.config import AnalyticsSettings, LoggingSettings, MainSettings
from infrahub.core import registry

router = APIRouter()


class ConfigAPI(BaseModel):
    main: MainSettings
    logging: LoggingSettings
    analytics: AnalyticsSettings


class InfoAPI(BaseModel):
    deployment_id: str
    version: str


@router.get("/config")
async def get_config() -> ConfigAPI:
    return ConfigAPI(main=config.SETTINGS.main, logging=config.SETTINGS.logging, analytics=config.SETTINGS.analytics)


@router.get("/info")
async def get_info() -> InfoAPI:
    return InfoAPI(deployment_id=str(registry.id), version=__version__)
