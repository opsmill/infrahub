from typing import Optional

from diffsync import DiffSyncModel


class Region(DiffSyncModel):
    """Example model of a geographic region."""

    _modelname = "region"
    _identifiers = ("slug",)
    _attributes = ("name", "description")

    slug: str
    name: str
    description: Optional[str]


class Site(DiffSyncModel):
    _modelname = "site"
    _identifiers = ("slug",)
    _attributes = ("name", "description", "address")

    slug: str
    name: str
    region: Optional[str]
    description: Optional[str]
    address: Optional[str]
