# Changelog Enrichment

> Part of: `dev/knowledge/backend/` | Related: [events.md](events.md), [webhooks.md](webhooks.md), [display-labels-and-hfid.md](display-labels-and-hfid.md)

A node event carries a `NodeChangelog` (`backend/infrahub/core/changelog/models.py`), and webhook
receivers get it as-is in the payload's `data.changelog`. Besides the ids and kinds of the node and
its relationship peers, the changelog carries human-readable identifiers so a receiver does not need
to call back into Infrahub to resolve them:

| Field | On | Value |
|-------|----|-------|
| `display_label`, `hfid` | the node | the node's display label and human-friendly ID; `hfid` is `None` for a kind without one |
| `peer_display_label`, `peer_hfid` | each peer of a cardinality-many relationship, and the current peer of a cardinality-one relationship | the peer's display label and human-friendly ID; `peer_hfid` is `None` for a kind without one, and both are `None` when the peer could not be resolved |

The previous peer of a cardinality-one relationship carries only `peer_id_previous` and
`peer_kind_previous`.

## Two paths build the changelogs

| Path | Entry point | Where the labels come from |
|------|-------------|----------------------------|
| Node and relationship mutations | `build_relationship_changelog_getter()` (`core/changelog/builder.py`) | the mutated node's own labels come from the loaded node; the peers' labels are resolved in one batched load |
| Branch merge and rebase | `build_diff_changelog_collector()` (`core/changelog/builder.py`) | display labels come from the enriched diff; HFIDs are resolved by `ChangelogHfidResolver` |

Build both through `builder.py`: it is the only place that wires the label loader, so every consumer
reads labels the same way.

### Mutations

`RelationshipChangelogGetter` fills the mutated node's relationship peers with their labels, then
builds the *secondary* changelogs: a relationship change on the mutated node also changes the
reciprocal relationship on each peer whose schema declares one, so each such peer gets its own node
event. A one-way relationship (a tag never lists what points at it) produces no secondary. Three
components do the work, injected by `builder.py`:

- `PeerLabelResolver` (`peer_labels.py`) collects every peer id the changelog references and resolves
  them in one load
- `ReciprocalRelationshipBuilder` (`reciprocal.py`) builds the peer-side relationship changelog for
  either cardinality, including the parent it names
- `SecondaryChangelogMerger` (`secondary_merger.py`) folds the secondaries by peer, so a peer reached
  through several changed relationships gets one event carrying all of its reciprocal changes

A secondary whose peer could not be resolved (for example a peer deleted in the same cascade) still
names its node, with the placeholder display label `n/a` and no HFID.

After a `RelationshipAdd` or `RelationshipRemove`, the source node's labels are read again only when
the mutated relationship feeds its display label or HFID, or is the profiles relationship. Otherwise
the labels the loaded node holds are current.

### Merge and rebase

`DiffChangelogCollector` (`core/changelog/diff.py`) turns each changed node of the enriched diff into
a changelog. The diff already carries the display labels of nodes and peers; it carries HFIDs only as
attribute changes, so `ChangelogHfidResolver` (`hfid_resolver.py`) fills them afterwards:

- a node whose diff carries its current HFID (created, or HFID changed) takes it from the diff
- a removed node, gone by the time labels are read, takes the previous value the diff recorded, also
  where it appears as a peer
- every other node, and every peer outside the diff, is loaded in one batch
- a node or peer whose kind was dropped by a schema migration stays unresolved, even when the diff
  records its HFID, and never joins the batch, so it cannot fail the load for the others

## Reading labels

`NodeLabelLoader` (`core/changelog/enrichment.py`) is the single entry point for label reads. Its
`DbNodeLabelReader` reads the stored labels first, through `NodeManager.get_stored_labels()` (see
[Bulk Reads of Stored Labels](display-labels-and-hfid.md#bulk-reads-of-stored-labels)), and loads a node only when storage does
not give its labels. That load reads only the two label attributes, and falls back to the whole node
when a label is not materialized and must be computed from the node's fields.

Never let a label read fail the operation. The mutation, merge or rebase has already committed when
the changelog is enriched, so `NodeLabelLoader` logs the failure and returns no labels: the affected
fields stay `None` and the event is still emitted.

## Key Locations

| Component | Location |
|-----------|----------|
| Payload models | `core/changelog/models.py` |
| Assembly of loaders and components | `core/changelog/builder.py` |
| Label loader and reader | `core/changelog/enrichment.py` |
| Secondary changelog components | `core/changelog/relationship_getter.py`, `peer_labels.py`, `reciprocal.py`, `secondary_merger.py` |
| Merge and rebase collection | `core/changelog/diff.py`, `hfid_resolver.py` |
| Source node re-read after a relationship mutation | `graphql/mutations/relationship.py` |
