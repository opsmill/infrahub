from infrahub.core.diff.model.path import EnrichedDiffNode, EnrichedDiffRoot


def get_one_diff_node(
    diff_root: EnrichedDiffRoot, node_uuid: str, node_kind: str | None = None, node_labels: frozenset[str] | None = None
) -> EnrichedDiffNode:
    matching_nodes = [node for node in diff_root.nodes if node.uuid == node_uuid]
    if node_kind:
        matching_nodes = [node for node in matching_nodes if node.kind == node_kind]
    if node_labels:
        matching_nodes = [node for node in matching_nodes if node.identifier.labels == node_labels]
    if len(matching_nodes) > 1:
        raise ValueError(f"multiple nodes found for {node_uuid=},{node_kind=},{node_labels=}")
    if not matching_nodes:
        raise ValueError(f"No nodes found for {node_uuid=},{node_kind=},{node_labels=}")
    return matching_nodes[0]
