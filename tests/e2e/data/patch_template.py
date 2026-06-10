"""Patch panel object-template slice.

Faithful transcription of ``prepare_patch_template()`` in
``models/infrastructure_edge.py`` (line ~2487) and its ``TEMPLATES`` table
(lines ~340-391): the ``TEMPLATES`` dicts below are exactly what the script's
``TemplateInfraPatchPanel`` / ``TemplateInfraFrontPatchPanelInterface``
pydantic models ``model_dump()`` to. The Regular_Patch_Panel template is
saved with ``allow_upsert``; its six front-interface templates are saved in
one batch (plain ``save``), as in the script.
"""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Any

import pytest

from data.handles import PatchTemplateHandle

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClientSync

    from data.handles import OrgRegistryHandle

TEMPLATES: list[dict[str, Any]] = [
    {
        "template_name": "Regular_Patch_Panel",
        "module_capacity": 3,
        "description": "Patch Panel used to connect racks",
        "tags": ["green"],
        "interfaces": [
            {
                "template_name": "Regular_Patch_Panel__C1.P01",
                "name": "C1.P01",
                "connector_type": "LC",
                "description": "Position 1 on Module C1",
                "patch_panel": {},
            },
            {
                "template_name": "Regular_Patch_Panel__C1.P02",
                "name": "C1.P02",
                "connector_type": "LC",
                "description": "Position 2 on Module C1",
                "patch_panel": {},
            },
            {
                "template_name": "Regular_Patch_Panel__C1.P03",
                "name": "C1.P03",
                "connector_type": "LC",
                "description": "Position 3 on Module C1",
                "patch_panel": {},
            },
            {
                "template_name": "Regular_Patch_Panel__C1.P04",
                "name": "C1.P04",
                "connector_type": "LC",
                "description": "Position 4 on Module C1",
                "patch_panel": {},
            },
            {
                "template_name": "Regular_Patch_Panel__C1.P05",
                "name": "C1.P05",
                "connector_type": "LC",
                "description": "Position 5 on Module C1",
                "patch_panel": {},
            },
            {
                "template_name": "Regular_Patch_Panel__C1.P06",
                "name": "C1.P06",
                "connector_type": "LC",
                "description": "Position 6 on Module C1",
                "patch_panel": {},
            },
        ],
    },
]


@pytest.fixture(scope="session")
def data_patch_template(
    data_client: InfrahubClientSync,
    schema_base: None,
    data_org_registry: OrgRegistryHandle,
    infrahub_provisioned_externally: bool,
) -> PatchTemplateHandle:
    """Create the patch panel template and its front-interface templates.

    Depends on ``data_org_registry`` for the ``green`` tag the template
    references (the script passed the tag name and let the server resolve it
    via the default filter; passing the id targets the same node).
    """
    if infrahub_provisioned_externally:
        return PatchTemplateHandle.external()

    branch = "main"
    templates: dict[str, str] = {}

    batch = data_client.create_batch()

    # Create Patch Panel Template
    for template in TEMPLATES:
        data = deepcopy(template)
        data["tags"] = [data_org_registry.tags[tag] for tag in template["tags"]]
        patch_template = data_client.create(branch=branch, kind="TemplateInfraPatchPanel", data=data)
        patch_template.save(allow_upsert=True)
        templates[data["template_name"]] = patch_template.id

        # and corresponding interfaces
        for interface in data["interfaces"]:
            interface["patch_panel"] = {"id": patch_template.id}
            obj = data_client.create(branch=branch, kind="TemplateInfraFrontPatchPanelInterface", data=interface)
            batch.add(task=obj.save, node=obj)

    for node, _response in batch.execute():
        templates[node.template_name.value] = node.id

    return PatchTemplateHandle(templates=templates)
