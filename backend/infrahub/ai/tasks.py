from __future__ import annotations

import logging

from prefect import flow
from prefect.logging import get_run_logger

from infrahub import config
from infrahub.context import InfrahubContext  # noqa: TC001  needed for prefect flow
from infrahub.workers.dependencies import get_client
from infrahub.workflows.utils import add_tags

from .claude import ClaudeExtractionClient
from .extraction import (
    build_extraction_prompt,
    get_extractable_attributes,
    get_extractable_relationships,
    parse_extraction_response,
)

log = logging.getLogger(__name__)

# Maximum number of peer choices to include in the extraction prompt.
# If a peer type has more nodes than this, we skip enumeration and let
# Claude return a free-form name (which may be less accurate).
_MAX_PEER_CHOICES = 100


def _get_node_display_name(node: object) -> str:
    """Return a human-readable display name for a node, for use in extraction prompts."""
    name_attr = getattr(node, "name", None)
    if name_attr is not None and hasattr(name_attr, "value") and name_attr.value:
        return str(name_attr.value)
    return str(getattr(node, "id", node))


@flow(
    name="file-object-ai-extraction",
    flow_run_name="AI extraction for {node_kind}/{node_id}",
    persist_result=False,
)
async def file_object_ai_extraction(
    branch_name: str,
    node_id: str,
    node_kind: str,
    context: InfrahubContext,  # noqa: ARG001
) -> None:
    """Extract structured data from a CoreFileObject's file content using the Claude API.

    Reads the extractable attributes from the node's schema, sends the file content to
    Claude with a structured extraction prompt, and updates the node attributes with the
    returned values.
    """
    logger = get_run_logger()
    await add_tags(branches=[branch_name], nodes=[node_id], db_change=True)

    ai_config = config.SETTINGS.ai
    if not ai_config.anthropic_api_key:
        logger.warning("Skipping AI extraction: INFRAHUB_AI_ANTHROPIC_API_KEY is not configured")
        return

    client = get_client()

    # Fetch the node (includes all attributes populated)
    node = await client.get(kind=node_kind, id=node_id, branch=branch_name)
    if node is None:
        logger.error("Node %s/%s not found; skipping AI extraction", node_kind, node_id)
        return

    # Fetch the schema to discover which attributes and relationships are extractable
    schema = await client.schema.get(kind=node_kind, branch=branch_name)
    extractable = get_extractable_attributes(schema=schema)
    extractable_rels = get_extractable_relationships(schema=schema)

    if not extractable and not extractable_rels:
        logger.info("No extractable attributes or relationships found for %s; skipping AI extraction", node_kind)
        return

    logger.info(
        "Extractable attributes for %s: %s",
        node_kind,
        {a.name: a.description for a in extractable},
    )
    if extractable_rels:
        logger.info(
            "Extractable relationships for %s: %s",
            node_kind,
            {r.name: r.peer for r in extractable_rels},
        )

    # Prefetch peer nodes for each relationship so Claude gets an exact choices list
    # and we can resolve the result without a second API call.
    peer_lookup: dict[str, dict[str, object]] = {}  # rel_name -> {display_name -> node}
    for rel in extractable_rels:
        try:
            peer_nodes = await client.filters(kind=rel.peer, branch=branch_name, limit=_MAX_PEER_CHOICES + 1)
        except Exception as exc:
            logger.warning("Failed to prefetch %s nodes for relationship '%s': %s", rel.peer, rel.name, exc)
            peer_nodes = []
        if len(peer_nodes) > _MAX_PEER_CHOICES:
            logger.warning(
                "Peer type %s has >%d nodes; skipping choice enumeration for relationship '%s'",
                rel.peer,
                _MAX_PEER_CHOICES,
                rel.name,
            )
            peer_lookup[rel.name] = {}
        else:
            lookup = {_get_node_display_name(n): n for n in peer_nodes}
            peer_lookup[rel.name] = lookup
            rel.peer_choices = sorted(lookup.keys()) if lookup else None

    # Download the file content
    try:
        file_content: bytes = await node.download_file()  # type: ignore[assignment]
    except Exception as exc:
        logger.error("Failed to download file for node %s/%s: %s", node_kind, node_id, exc)
        return

    file_name: str = node.file_name.value or ""  # type: ignore[attr-defined]
    file_type: str = node.file_type.value or "application/octet-stream"  # type: ignore[attr-defined]

    logger.info(
        "Running AI extraction on %s/%s (%s, %d bytes, %d extractable attributes)",
        node_kind,
        node_id,
        file_type,
        len(file_content),
        len(extractable),
    )

    # Build the extraction prompt
    system_prompt = build_extraction_prompt(
        attributes=extractable,
        file_name=file_name,
        file_type=file_type,
        relationships=extractable_rels or None,
    )

    # Call the Claude API
    claude = ClaudeExtractionClient(
        api_key=ai_config.anthropic_api_key,
        model=ai_config.extraction_model,
    )
    try:
        response_text = await claude.extract(
            content=file_content,
            mime_type=file_type,
            system_prompt=system_prompt,
        )
    except Exception as exc:
        logger.error("Claude API call failed for node %s/%s: %s", node_kind, node_id, exc)
        return

    logger.info(
        "Claude raw response for %s/%s (first 1000 chars): %s",
        node_kind,
        node_id,
        response_text[:1000],
    )

    # Parse the response and update the node
    extracted = parse_extraction_response(
        response_text=response_text, attributes=extractable, relationships=extractable_rels or None
    )
    logger.info("Parsed extraction result for %s/%s: %s", node_kind, node_id, extracted)
    if not extracted:
        logger.warning("No attributes extracted for %s/%s (check Claude response above)", node_kind, node_id)
        return

    logger.info("Extracted fields for %s/%s: %s", node_kind, node_id, list(extracted.keys()))

    # Split extracted values into attribute updates and relationship updates
    rel_names = {r.name for r in extractable_rels}
    rel_by_name = {r.name: r for r in extractable_rels}

    for attr_name, value in extracted.items():
        if attr_name in rel_names:
            continue
        attr = getattr(node, attr_name, None)
        if attr is None:
            logger.warning("Attribute '%s' not found on node %s; skipping", attr_name, node_kind)
            continue
        try:
            attr.value = value
        except Exception as exc:
            logger.warning("Failed to set attribute '%s' on node %s: %s", attr_name, node_kind, exc)

    for rel_name, peer_name in extracted.items():
        if rel_name not in rel_names:
            continue
        rel = rel_by_name[rel_name]

        # Resolve from prefetched lookup first (no extra API call)
        peer_node = peer_lookup.get(rel_name, {}).get(peer_name)

        if peer_node is None:
            # Fallback: direct name search (covers the >_MAX_PEER_CHOICES case)
            try:
                peer_node = await client.get(
                    kind=rel.peer, name__value=peer_name, branch=branch_name, raise_when_missing=False
                )
            except Exception as exc:
                logger.warning(
                    "Failed to look up %s '%s' for relationship '%s': %s", rel.peer, peer_name, rel_name, exc
                )
                continue

        if peer_node is None:
            logger.warning(
                "No %s found with name '%s' for relationship '%s'; skipping", rel.peer, peer_name, rel_name
            )
            continue

        try:
            setattr(node, rel_name, peer_node)
        except Exception as exc:
            logger.warning("Failed to set relationship '%s' on node %s: %s", rel_name, node_kind, exc)

    try:
        await node.update()  # type: ignore[union-attr]
        logger.info("Successfully updated %d fields on %s/%s", len(extracted), node_kind, node_id)
    except Exception as exc:
        logger.error("Failed to save extracted fields to %s/%s: %s", node_kind, node_id, exc)
