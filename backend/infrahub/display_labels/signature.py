from __future__ import annotations

from typing import ClassVar

from infrahub.trigger.signature import TriggerSignatureBase, TriggerSignatureGetListQueryBase


class DisplayLabelSignatureGetListQuery(TriggerSignatureGetListQueryBase):
    pass


class DisplayLabelSignature(TriggerSignatureBase):
    """Stores the hash of a Jinja2 display-label definition per (branch, target_kind), used to
    detect definition changes during schema-setup runs."""

    list_query_cls: ClassVar[type[TriggerSignatureGetListQueryBase]] = DisplayLabelSignatureGetListQuery
