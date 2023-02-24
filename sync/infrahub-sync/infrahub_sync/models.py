from typing import Optional

from diffsync import DiffSyncModel


class Region(DiffSyncModel):
    """Example model of a geographic region."""

    _modelname = "region"
    _identifiers = ("slug",)
    _attributes = ("description",)

    slug: str
    name: Optional[str]
    description: Optional[str]


class Site(DiffSyncModel):
    _modelname = "site"
    _identifiers = ("slug",)
    _attributes = ("description", "address")

    slug: str
    name: Optional[str]
    region: Optional[str]
    description: Optional[str]
    address: Optional[str]
