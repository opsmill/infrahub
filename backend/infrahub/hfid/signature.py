from __future__ import annotations

from typing import ClassVar

from infrahub.trigger.signature import TriggerSignatureBase, TriggerSignatureGetListQueryBase


class HFIDSignatureGetListQuery(TriggerSignatureGetListQueryBase):
    pass


class HFIDSignature(TriggerSignatureBase):
    """Stores the hash of a human-friendly-id definition per (branch, target_kind), used to
    detect definition changes during schema-setup runs."""

    list_query_cls: ClassVar[type[TriggerSignatureGetListQueryBase]] = HFIDSignatureGetListQuery
