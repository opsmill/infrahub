from __future__ import annotations

from typing import TYPE_CHECKING, assert_never

from infrahub.core.registry import registry
from infrahub.core.template_fingerprint.models import SchemaFingerprints, TemplateFamily

if TYPE_CHECKING:
    from collections.abc import Mapping

    from infrahub.core.schema.schema_branch import SchemaBranch


def _branch_fingerprints(family: TemplateFamily, schema_branch: SchemaBranch) -> dict[str, str]:
    match family:
        case TemplateFamily.DISPLAY_LABEL_JINJA2:
            return {kind: label.get_hash() for kind, label in schema_branch.display_labels.get_template_nodes().items()}
        case TemplateFamily.HUMAN_FRIENDLY_ID:
            return {kind: hfid.get_hash() for kind, hfid in schema_branch.hfids.get_template_nodes().items()}
        case _:
            assert_never(family)


def fingerprints_from_schema_branches(
    family: TemplateFamily, schema_branches: Mapping[str, SchemaBranch]
) -> SchemaFingerprints:
    """Compute the fingerprint of every template of the family, for each of the given branches."""
    return SchemaFingerprints(
        family=family,
        by_branch={
            branch_name: _branch_fingerprints(family=family, schema_branch=schema_branch)
            for branch_name, schema_branch in schema_branches.items()
        },
    )


def collect_schema_fingerprints(family: TemplateFamily) -> SchemaFingerprints:
    """Compute the fingerprints of the family for the default branch and every branch that owns its schema."""
    branch_names = [registry.default_branch, *registry.get_altered_schema_branches()]
    return fingerprints_from_schema_branches(
        family=family,
        schema_branches={name: registry.schema.get_schema_branch(name=name) for name in branch_names},
    )
