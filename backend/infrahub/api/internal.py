import json
import os
import re
from typing import List

from fastapi import APIRouter
from lunr.index import Index
from pydantic import BaseModel

from infrahub import __version__, config
from infrahub.config import AnalyticsSettings, ExperimentalFeaturesSettings, LoggingSettings, MainSettings
from infrahub.core import registry

router = APIRouter()


class ConfigAPI(BaseModel):
    main: MainSettings
    logging: LoggingSettings
    analytics: AnalyticsSettings
    experimental_features: ExperimentalFeaturesSettings


class InfoAPI(BaseModel):
    deployment_id: str
    version: str


class SearchResultAPI(BaseModel):
    title: str
    url: str
    breadcrumb: List[str]


@router.get("/config")
async def get_config() -> ConfigAPI:
    return ConfigAPI(
        main=config.SETTINGS.main,
        logging=config.SETTINGS.logging,
        analytics=config.SETTINGS.analytics,
        experimental_features=config.SETTINGS.experimental_features,
    )


@router.get("/info")
async def get_info() -> InfoAPI:
    return InfoAPI(deployment_id=str(registry.id), version=__version__)


DOCS_DIRECTORY = os.environ.get("INFRAHUB_DOCS_DIRECTORY", os.path.abspath("docs"))
DOCS_SEARCH_INDEX_FILE = f"{DOCS_DIRECTORY}/build/search-index.json"

if os.path.exists(DOCS_SEARCH_INDEX_FILE):
    # The structure of search-index.json is organized into an array of 3 arrays representing indexes for:
    # [titleDocuments, headingDocuments, contentDocuments]
    #
    # For titleDocuments, it consists of an array of dictionaries with the following structure:
    # {
    #     i: title_id,
    #     t: page_title,
    #     u: url,
    #     b: breadcrumb,
    # }
    #
    # For headingDocuments, it is an array of dictionaries with the following structure:
    # {
    #     i: incremental_id,
    #     t: section.title,
    #     u: url,
    #     h: section.hash,
    #     p: title_id,
    # }
    #
    # For contentDocuments, it is an array of dictionaries with the following structure:
    # {
    #     i: incremental_id,
    #     t: section.content,
    #     s: section.title or page_title,
    #     u: url,
    #     h: section.hash,
    #     p: title_id,
    # }
    with open(DOCS_SEARCH_INDEX_FILE, "r", encoding="utf-8") as f:
        search_index = json.loads(f.read())
        page_search_index = search_index[0]
        heading_search_index = search_index[1]
        docs_heading_index = Index.load(heading_search_index["index"])


def tokenize(text: str):
    return re.findall(r"[^-\s]+", text.lower()) or []


def smart_queries(query: str):
    tokens = tokenize(query)
    if len(tokens) == 0:
        return []

    term_required_and_wildcard = [f"{term}*" for term in tokens]

    return " ".join(term_required_and_wildcard)


@router.get("/search/docs")
async def search_docs(query: str) -> List[SearchResultAPI]:
    smart_query = smart_queries(query)
    search_results = docs_heading_index.search(smart_query)
    heading_results = [
        next(doc for doc in heading_search_index["documents"] if doc["i"] == int(result["ref"]))
        for result in search_results
    ]

    response_list = [
        {
            "title": result["t"],
            "url": result["u"] + result["h"],
            "breadcrumb": next(doc["b"] for doc in page_search_index["documents"] if doc["i"] == int(result["p"])),
        }
        for result in heading_results
    ]

    return response_list
