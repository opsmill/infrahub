from __future__ import annotations

from infrahub.utils import InfrahubStringEnum


class ServiceCatalogEntryMode(InfrahubStringEnum):
    REVIEW = "review"
    DIRECT = "direct"


class ServiceRequestStatus(InfrahubStringEnum):
    SUBMITTED = "submitted"
    GENERATING = "generating"
    FAILED = "failed"
    IN_REVIEW = "in_review"
    MERGED = "merged"
    REJECTED = "rejected"
