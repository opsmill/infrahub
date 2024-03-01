import json
import re
from typing import List, Optional

from fastapi import APIRouter
from lunr.index import Index
from pydantic import BaseModel

from infrahub import __version__, config
from infrahub.config import AnalyticsSettings, ExperimentalFeaturesSettings, LoggingSettings, MainSettings
from infrahub.core import registry
from infrahub.exceptions import NodeNotFound

router = APIRouter()


class ConfigAPI(BaseModel):
    main: MainSettings
    logging: LoggingSettings
    analytics: AnalyticsSettings
    experimental_features: ExperimentalFeaturesSettings


class InfoAPI(BaseModel):
    deployment_id: str
    version: str


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


class SearchDocs:
    def __init__(self) -> None:
        self._title_documents: List[dict] = []
        self._heading_documents: List[dict] = []
        self._heading_index: Optional[Index] = None

    def _load_json(self) -> None:
        """
        The structure of search-index.json is organized into an array of 3 arrays representing indexes for:
        [titleDocuments, headingDocuments, contentDocuments]

        For titleDocuments, it consists of an array of dictionaries with the following structure:
        {
            i: title_id,
            t: page_title,
            u: url,
            b: breadcrumb,
        }

        For headingDocuments, it is an array of dictionaries with the following structure:
        {
            i: incremental_id,
            t: section.title,
            u: url,
            h: section.hash,
            p: title_id,
        }

        For contentDocuments, it is an array of dictionaries with the following structure:
        {
            i: incremental_id,
            t: section.content,
            s: section.title or page_title,
            u: url,
            h: section.hash,
            p: title_id,
        }
        """

        try:
            with open(config.SETTINGS.main.docs_index_path, "r", encoding="utf-8") as f:
                search_index = json.loads(f.read())
                self._title_documents = search_index[0]["documents"]
                heading_json = search_index[1]
                self._heading_documents = heading_json["documents"]
                self._heading_index = Index.load(heading_json["index"])
        except FileNotFoundError as exc:
            raise NodeNotFound(
                identifier=config.SETTINGS.main.docs_index_path,
                message="documentation index not found",
                node_type="file",
            ) from exc

    @property
    def heading_index(self) -> Index:
        if not self._heading_index:
            self._load_json()

        return self._heading_index

    @property
    def title_documents(self) -> List[dict]:
        if not self._title_documents:
            self._load_json()

        return self._title_documents

    @property
    def heading_documents(self) -> List[dict]:
        if not self._heading_documents:
            self._load_json()

        return self._heading_documents


search_docs_loader = SearchDocs()


def tokenize(text: str) -> List[str]:
    return re.findall(r"[^-\s]+", text.lower()) or []


def smart_queries(query: str) -> str:
    tokens = tokenize(query)
    if len(tokens) == 0:
        return ""

    term_required_and_wildcard = [f"{term}*" for term in tokens]

    return " ".join(term_required_and_wildcard)


class SearchResultAPI(BaseModel):
    title: str
    url: str
    breadcrumb: List[str]


@router.get("/search/docs", include_in_schema=False)
async def search_docs(query: str, limit: Optional[int] = None) -> List[SearchResultAPI]:
    smart_query = smart_queries(query)
    search_results = search_docs_loader.heading_index.search(smart_query)
    heading_results = [
        next(doc for doc in search_docs_loader.heading_documents if doc["i"] == int(result["ref"]))
        for result in search_results
    ]

    if limit is not None:
        heading_results = heading_results[:limit]

    response_list: List[SearchResultAPI] = [
        SearchResultAPI(
            title=result["t"],
            url=result["u"] + result["h"],
            breadcrumb=next(doc["b"] for doc in search_docs_loader.title_documents if doc["i"] == int(result["p"])),
        )
        for result in heading_results
    ]

    return response_list
