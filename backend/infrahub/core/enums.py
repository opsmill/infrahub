import enum
import re
from typing import Any

ENUM_NAME_REGEX = re.compile(r"[_a-zA-Z0-9]+")


def generate_python_enum(name: str, options: list[Any]) -> type[enum.Enum]:
    main_attrs = {}
    for option in options:
        if isinstance(option, int):
            enum_name = str(option)
        else:
            enum_name = "_".join(re.findall(ENUM_NAME_REGEX, option)).upper()

        main_attrs[enum_name] = option
    return enum.Enum(name, main_attrs)  # type: ignore[return-value]
