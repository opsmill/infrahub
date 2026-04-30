from __future__ import annotations

from typing import Any, ClassVar

from infrahub.trigger.signature import TriggerSignatureBase, TriggerSignatureGetListQueryBase


class ComputedAttrJinja2SignatureGetListQuery(TriggerSignatureGetListQueryBase):
    def __init__(
        self,
        attribute_name: str | None = None,
        **kwargs: Any,
    ) -> None:
        self._attribute_name = attribute_name
        super().__init__(**kwargs)

    def _collect_conditions(self) -> list[str]:
        conditions = super()._collect_conditions()
        if self._attribute_name is not None:
            self._signature_filter_params["filter_attribute_name"] = self._attribute_name
            conditions.append("n.attribute_name = $filter_attribute_name")
        return conditions


class ComputedAttrJinja2Signature(TriggerSignatureBase):
    """Stores the hash of a self-targeting Jinja2 computed-attribute definition per
    (branch, target_kind, attribute_name), used to detect definition changes during
    schema-setup runs."""

    attribute_name: str

    list_query_cls: ClassVar[type[TriggerSignatureGetListQueryBase]] = ComputedAttrJinja2SignatureGetListQuery
