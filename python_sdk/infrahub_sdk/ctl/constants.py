PROTOCOLS_TEMPLATE = """#
# Generated by "infrahubctl protocols"
#

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable, Optional

if TYPE_CHECKING:
    from datetime import datetime

    {% if sync %}
    from infrahub_sdk.nodes import RelatedNodeSync, RelationshipManagerSync
    {% else %}
    from infrahub_sdk.nodes import RelatedNode, RelationshipManager
    {% endif %}


@runtime_checkable
class CoreNode(Protocol):
    id: str
    display_label: Optional[str]
    hfid: Optional[list[str]]
    hfid_str: Optional[str]

    def get_kind(self) -> str: ...


{% for generic in generics %}
class {{ generic.namespace + generic.name }}(CoreNode):
    {% if not generic.attributes|default([]) and not generic.relationships|default([]) %}
    pass
    {% endif %}
    {% for attribute in generic.attributes|default([]) %}
    {{ attribute | render_attribute }}
    {% endfor %}
    {% for relationship in generic.relationships|default([]) %}
    {{ relationship | render_relationship(sync) }}
    {% endfor %}
    {% if generic.hierarchical | default(false) %}
    {% if sync %}
    parent: RelatedNodeSync
    children: RelationshipManagerSync
    {% else %}
    parent: RelatedNode
    children: RelationshipManager
    {% endif %}
    {% endif %}
{% endfor %}


{% for node in nodes %}
class {{ node.namespace + node.name }}({{ node.inherit_from | join(", ") or "CoreNode" }}):
    {% if not node.attributes|default([]) and not node.relationships|default([]) %}
    pass
    {% endif %}
    {% for attribute in node.attributes|default([]) %}
    {{ attribute | render_attribute }}
    {% endfor %}
    {% for relationship in node.relationships|default([]) %}
    {{ relationship | render_relationship(sync) }}
    {% endfor %}
    {% if node.hierarchical | default(false) %}
    {% if sync %}
    parent: RelatedNodeSync
    children: RelationshipManagerSync
    {% else %}
    parent: RelatedNode
    children: RelationshipManager
    {% endif %}
    {% endif %}
{% endfor %}
"""
