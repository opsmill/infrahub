core_object_template = {
    "name": "ObjectTemplate",
    "namespace": "Core",
    "include_in_menu": False,
    "icon": "mdi:pencil-ruler",
    "description": "Template to create pre-shaped objects.",
    "label": "Object Templates",
    "display_labels": ["template_name__value"],
    "default_filter": "template_name__value",
    "uniqueness_constraints": [["template_name__value"]],
    "attributes": [{"name": "template_name", "kind": "Text", "optional": False, "unique": True, "order_weight": 1000}],
}
