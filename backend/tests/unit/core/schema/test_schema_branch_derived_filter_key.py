"""Resolving a cross-node derived value must not corrupt the cached own-id filter.

Display labels and HFIDs cache one template per kind. The self getter and the related (cross-node)
getter share that cached instance, so the related getter must return a copy rather than overwrite the
cached ``filter_key`` - otherwise a later own-id recompute queries with the relationship filter and
silently matches nothing.
"""

from __future__ import annotations

from copy import deepcopy

from infrahub.core.schema.schema_branch import SchemaBranch
from tests.helpers.merge_recompute.dataset import PROFILE_NODE_KIND, PROFILE_PEER_KIND, build_profile_schema


def _profile_schema_branch(*, hfid_reads_peer: bool = False) -> SchemaBranch:
    schema = deepcopy(build_profile_schema())
    if hfid_reads_peer:
        node = next(node for node in schema.nodes if node.kind == PROFILE_NODE_KIND)
        node.human_friendly_id = ["name__value", "peer__name__value"]
    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(schema=schema)
    schema_branch.process()
    return schema_branch


def test_get_related_template_does_not_mutate_cached_filter_key() -> None:
    display_labels = _profile_schema_branch().display_labels

    related = display_labels.get_related_template(related_kind=PROFILE_PEER_KIND, target_kind=PROFILE_NODE_KIND)

    assert related.filter_key == "peer__ids"
    assert display_labels.get_template_node(kind=PROFILE_NODE_KIND).filter_key == "ids"


def test_get_related_definition_does_not_mutate_cached_filter_key() -> None:
    hfids = _profile_schema_branch(hfid_reads_peer=True).hfids

    related = hfids.get_related_definition(related_kind=PROFILE_PEER_KIND, target_kind=PROFILE_NODE_KIND)

    assert related.filter_key == "peer__ids"
    assert hfids.get_node_definition(kind=PROFILE_NODE_KIND).filter_key == "ids"
