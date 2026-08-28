"""Throwaway prototype gate for webhook payload enrichment.

Read from a raw environment variable rather than an INFRAHUB_ config setting: a real
setting would drag in docker-compose / configuration.mdx regeneration and their CI gates,
which a measurement prototype does not need. The value is re-read per mutation on purpose so
the level can be switched between perf runs without rebuilding the image.

Levels form two axes. The primary node's HFID is added on every level except OFF, read either
from its materialized value (local) or recomputed by resolving a relationship peer (distant).
The peer levels additionally enrich related-node changelogs; their HFID is likewise read local
or recomputed distant, and loaded either one node at a time or in a single batch.
"""

from __future__ import annotations

import os
from enum import StrEnum

_ENV_VAR = "INFRAHUB_EXPERIMENTAL_WEBHOOK_ENRICHMENT"


class WebhookEnrichmentLevel(StrEnum):
    OFF = "off"
    LOCAL_HFID = "local_hfid"
    DISTANT_HFID = "distant_hfid"
    LOCAL_HFID_PEERS_LABEL = "local_hfid_peers_label"
    LOCAL_HFID_PEERS_LABEL_OPTIMIZED = "local_hfid_peers_label_optimized"
    DISTANT_HFID_PEERS = "distant_hfid_peers"
    DISTANT_HFID_PEERS_OPTIMIZED = "distant_hfid_peers_optimized"


_PEER_LEVELS = frozenset(
    {
        WebhookEnrichmentLevel.LOCAL_HFID_PEERS_LABEL,
        WebhookEnrichmentLevel.LOCAL_HFID_PEERS_LABEL_OPTIMIZED,
        WebhookEnrichmentLevel.DISTANT_HFID_PEERS,
        WebhookEnrichmentLevel.DISTANT_HFID_PEERS_OPTIMIZED,
    }
)
_PEER_OPTIMIZED_LEVELS = frozenset(
    {
        WebhookEnrichmentLevel.LOCAL_HFID_PEERS_LABEL_OPTIMIZED,
        WebhookEnrichmentLevel.DISTANT_HFID_PEERS_OPTIMIZED,
    }
)
_DISTANT_PEER_LEVELS = frozenset(
    {
        WebhookEnrichmentLevel.DISTANT_HFID_PEERS,
        WebhookEnrichmentLevel.DISTANT_HFID_PEERS_OPTIMIZED,
    }
)


def get_webhook_enrichment_level() -> WebhookEnrichmentLevel:
    """Resolve the active level. An unknown value falls back to OFF (current behaviour)."""
    raw = os.environ.get(_ENV_VAR, "off").strip().lower()
    try:
        return WebhookEnrichmentLevel(raw)
    except ValueError:
        return WebhookEnrichmentLevel.OFF


def enrichment_primary_enabled() -> bool:
    """Whether the primary node's HFID is added to its changelog."""
    return get_webhook_enrichment_level() != WebhookEnrichmentLevel.OFF


def enrichment_primary_recompute_enabled() -> bool:
    """Whether the primary HFID is recomputed from the database rather than read materialized."""
    return get_webhook_enrichment_level() == WebhookEnrichmentLevel.DISTANT_HFID


def enrichment_peers_enabled() -> bool:
    """Whether related-node (peer) changelogs are enriched with their labels."""
    return get_webhook_enrichment_level() in _PEER_LEVELS


def enrichment_peers_optimized_enabled() -> bool:
    """Whether peer labels are loaded in a single batch rather than one query per peer."""
    return get_webhook_enrichment_level() in _PEER_OPTIMIZED_LEVELS


def enrichment_peers_recompute_enabled() -> bool:
    """Whether each peer's HFID is recomputed from the database rather than read materialized."""
    return get_webhook_enrichment_level() in _DISTANT_PEER_LEVELS
