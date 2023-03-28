from infrahub.core import registry

import infrahub.types


async def test_type_registry():
    assert sorted(list(registry.data_type.keys())) == [
        "Any",
        "Bandwidth",
        "Boolean",
        "Checkbox",
        "Color",
        "DateTime",
        "Email",
        "File",
        "ID",
        "IPHost",
        "IPNetwork",
        "Integer",
        "List",
        "MacAddress",
        "Number",
        "Password",
        "String",
        "Text",
        "TextArea",
        "URL",
    ]
