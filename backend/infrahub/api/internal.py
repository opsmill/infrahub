from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime  # noqa: TC003
from typing import TYPE_CHECKING, Self

import ujson
from fastapi import APIRouter, Depends, Request
from lunr.index import Index
from pydantic import BaseModel, Field

from infrahub import config
from infrahub.api.dependencies import get_current_user, get_permission_manager
from infrahub.config import (  # noqa: TC001
    AnalyticsSettings,
    ExperimentalFeaturesSettings,
    LoggingSettings,
    MainSettings,
)
from infrahub.core import registry
from infrahub.core.account import GlobalPermission
from infrahub.core.constants import GlobalPermissions, PermissionDecision
from infrahub.exceptions import NodeNotFoundError
from infrahub.license.models import (
    LicenseFailureReason,
    LicenseState,
    NoticeAudience,
    NoticeMode,
)
from infrahub.license.service import LicenseServiceUnavailable, read_license_status
from infrahub.license.status import notice_for, shown_to_all_users_when_enforced
from infrahub.log import get_logger
from infrahub.message_bus.messages import RefreshSettingsResponseDelay
from infrahub.workers.dependencies import get_installation_type, get_license_service

if TYPE_CHECKING:
    from infrahub.auth.session import AccountSession
    from infrahub.license.models import LicenseStatus
    from infrahub.license.service import LicenseService
    from infrahub.permissions import PermissionManager
    from infrahub.services import InfrahubServices

log = get_logger()
router = APIRouter()


class ConfigAPI(BaseModel):
    main: MainSettings
    logging: LoggingSettings
    analytics: AnalyticsSettings
    experimental_features: ExperimentalFeaturesSettings
    sso: config.SSOInfo
    ldap: config.LDAPInfo
    installation_type: str
    policy: config.PolicySettings


class BannerAPI(BaseModel):
    audience: NoticeAudience
    dismissible: bool
    shown_to_all_users_when_enforced: bool = Field(
        description="True when only super-admins see the banner now and every user sees it in the enforcing release"
    )


class LicenseInfoAPI(BaseModel):
    state: LicenseState
    reason: LicenseFailureReason | None = Field(
        description="Why the license could not be verified, set only when invalid"
    )
    license_id: str | None
    license_type: str | None
    customer_name: str | None
    product_tier: str | None
    support_tier: str | None
    starts_at: datetime | None
    ends_at: datetime | None = Field(description="First instant the license is no longer valid")
    days_remaining: int | None = Field(description="Whole days until the license ends, rounded up")
    days_since_expiry: int | None = Field(description="Whole days since the license ended, rounded down")
    notice_mode: NoticeMode
    enforcing_release: str | None = Field(
        description="Release in which every user starts seeing license problem notices, when known"
    )
    banner: BannerAPI

    @classmethod
    def from_status(cls, status: LicenseStatus, notice_mode: NoticeMode, enforcing_release: str | None) -> Self:
        notice = notice_for(status=status, mode=notice_mode)
        granted = status.license
        return cls(
            state=status.state,
            reason=status.reason,
            license_id=granted.license_id if granted else None,
            license_type=granted.license_type if granted else None,
            customer_name=granted.customer_name if granted else None,
            product_tier=granted.product_tier if granted else None,
            support_tier=granted.support_tier if granted else None,
            starts_at=granted.starts_at if granted else None,
            ends_at=granted.ends_at if granted else None,
            days_remaining=status.days_remaining,
            days_since_expiry=status.days_since_expiry,
            notice_mode=notice_mode,
            enforcing_release=enforcing_release,
            banner=BannerAPI(
                audience=notice.audience,
                dismissible=notice.dismissible,
                shown_to_all_users_when_enforced=shown_to_all_users_when_enforced(status=status, mode=notice_mode),
            ),
        )


class InfoAPI(BaseModel):
    deployment_id: str
    version: str
    license: LicenseInfoAPI | None = Field(
        description="License state and details, null unless the session is signed in"
    )


@dataclass
class _FailureLog:
    logged: bool = False


_license_object_failure = _FailureLog()


def _license_object(license_service: LicenseService) -> LicenseInfoAPI:
    status = read_license_status(service=license_service)
    try:
        return LicenseInfoAPI.from_status(
            status=status,
            notice_mode=license_service.notice_mode,
            enforcing_release=license_service.enforcing_release,
        )
    # Top-level boundary: a license object that cannot be built must not fail the whole response.
    except Exception:
        # A defect that fails every request logs its traceback once per process rather than once per request.
        if not _license_object_failure.logged:
            _license_object_failure.logged = True
            log.exception(
                "The license object could not be built; reporting the license as invalid with reason internal_error"
            )
        return LicenseInfoAPI.from_status(
            status=LicenseServiceUnavailable().status(), notice_mode=NoticeMode.QUIET, enforcing_release=None
        )


@router.get("/config")
async def get_config() -> ConfigAPI:
    return ConfigAPI(
        main=config.SETTINGS.main,
        logging=config.SETTINGS.logging,
        analytics=config.SETTINGS.analytics,
        experimental_features=config.SETTINGS.experimental_features,
        sso=config.SETTINGS.security.public_sso_config,
        ldap=config.LDAPInfo(
            enabled=config.SETTINGS.ldap.admin_enabled,
            display_label=config.SETTINGS.ldap.display_label,
            icon=config.SETTINGS.ldap.icon,
        ),
        installation_type=get_installation_type(),
        policy=config.SETTINGS.policy,
    )


@router.get("/info")
async def get_info(request: Request, account_session: AccountSession = Depends(get_current_user)) -> InfoAPI:
    # Anonymous access can be enabled, and whether and to whom the deployment is licensed is for signed-in users only.
    if not account_session.authenticated:
        return InfoAPI(deployment_id=str(registry.id), version=request.app.version, license=None)

    return InfoAPI(
        deployment_id=str(registry.id),
        version=request.app.version,
        license=_license_object(license_service=get_license_service()),
    )


class ResponseDelayAPI(BaseModel):
    response_delay: int = Field(ge=0, description="Delay in seconds added to each GraphQL request")


@router.post("/response-delay", include_in_schema=False)
async def set_response_delay(
    request: Request,
    delay: ResponseDelayAPI,
    permission_manager: PermissionManager = Depends(get_permission_manager),
) -> ResponseDelayAPI:
    """Update the API response delay at runtime (testing facility).

    The new value is broadcast over the message bus so every API worker process
    across all server replicas applies it without a restart.
    """
    permission_manager.raise_for_permission(
        permission=GlobalPermission(
            action=GlobalPermissions.SUPER_ADMIN.value, decision=PermissionDecision.ALLOW_ALL.value
        )
    )

    service: InfrahubServices = request.app.state.service
    await service.send(message=RefreshSettingsResponseDelay(response_delay=delay.response_delay))
    return delay


class SearchDocs:
    def __init__(self) -> None:
        self._title_documents: list[dict] = []
        self._heading_documents: list[dict] = []
        self._heading_index: Index | None = None

    def _load_json(self) -> None:
        """The structure of search-index.json is organized into an array of 3 arrays representing indexes for:

        [titleDocuments, headingDocuments, contentDocuments].

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

        Raises:
            NodeNotFoundError: When the documentation index file cannot be found on disk.

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
    if not query:
        return []
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
