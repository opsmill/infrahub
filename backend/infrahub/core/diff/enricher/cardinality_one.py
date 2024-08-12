from ..model.path import CalculatedDiffs, EnrichedDiffRoot
from .interface import DiffEnricherInterface


class DiffCardinalityOneEnricher(DiffEnricherInterface):
    """Clean up diffs for cardinality=one relationships to make them cleaner and more intuitive

    Final result is that each EnrichedDiffRelationship for a relationship of cardinality one
     - MUST have a single EnrichedDiffSingleRelationship (we'll call it the element)
     - the peer_id property of the element will be the latest non-null peer ID for this element
     - the element MUST have an EnrichedDiffProperty of property_type=IS_RELATED that correctly records
        the previous and new values of the peer ID for this element

    changes to properties (IS_VISIBLE, etc) of a cardinality=one relationship with an updated peer ID will
    probably need to be cleaned up as well
    """

    async def enrich(self, enriched_diff_root: EnrichedDiffRoot, calculated_diffs: CalculatedDiffs) -> None: ...
