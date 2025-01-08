from __future__ import annotations

import re
from typing import TYPE_CHECKING

import ujson
from fastapi import APIRouter, Depends, Request
from lunr.index import Index
from pydantic import BaseModel

from infrahub import config
from infrahub.api.dependencies import get_current_user
from infrahub.config import (  # noqa: TC001
    AnalyticsSettings,
    ExperimentalFeaturesSettings,
    LoggingSettings,
    MainSettings,
)
from infrahub.core import registry
from infrahub.exceptions import NodeNotFoundError

if TYPE_CHECKING:
    from infrahub.auth import AccountSession

router = APIRouter()


class ConfigAPI(BaseModel):
    main: MainSettings
    logging: LoggingSettings
    analytics: AnalyticsSettings
    experimental_features: ExperimentalFeaturesSettings
    sso: config.SSOInfo


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
        sso=config.SETTINGS.security.public_sso_config,
    )


@router.get("/info")
async def get_info(request: Request, _: AccountSession = Depends(get_current_user)) -> InfoAPI:
    return InfoAPI(deployment_id=str(registry.id), version=request.app.version)


class SearchDocs:
    def __init__(self) -> None:
        self._title_documents: list[dict] = []
        self._heading_documents: list[dict] = []
        self._heading_index: Index | None = None

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
            with config.SETTINGS.main.docs_index_path.open(encoding="utf-8") as f:
                search_index = ujson.loads(f.read())
                self._title_documents = search_index[0]["documents"]
                heading_json = search_index[1]
                self._heading_documents = heading_json["documents"]
                self._heading_index = Index.load(heading_json["index"])
        except FileNotFoundError as exc:
            raise NodeNotFoundError(
                identifier=str(config.SETTINGS.main.docs_index_path),
                message="documentation index not found",
                node_type="file",
            ) from exc

    @property
    def heading_index(self) -> Index:
        if not self._heading_index:
            self._load_json()

        return self._heading_index

    @property
    def title_documents(self) -> list[dict]:
        if not self._title_documents:
            self._load_json()

        return self._title_documents

    @property
    def heading_documents(self) -> list[dict]:
        if not self._heading_documents:
            self._load_json()

        return self._heading_documents


search_docs_loader = SearchDocs()


def tokenize(text: str) -> list[str]:
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
    breadcrumb: list[str]


@router.get("/search/docs", include_in_schema=False)
async def search_docs(
    query: str, limit: int | None = None, _: AccountSession = Depends(get_current_user)
) -> list[SearchResultAPI]:
    smart_query = smart_queries(query)
    search_results = search_docs_loader.heading_index.search(smart_query)
    heading_results = [
        next(doc for doc in search_docs_loader.heading_documents if doc["i"] == int(result["ref"]))
        for result in search_results
    ]

    if limit is not None:
        heading_results = heading_results[:limit]

    response_list: list[SearchResultAPI] = [
        SearchResultAPI(
            title=result["t"],
            url=result["u"] + result["h"],
            breadcrumb=next(
                doc["b"] + [doc["t"]] for doc in search_docs_loader.title_documents if doc["i"] == int(result["p"])
            ),
        )
        for result in heading_results
    ]

    return response_list
