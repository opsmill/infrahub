import enum
import re
from typing import Dict

ENUM_NAME_REGEX = re.compile("[_a-zA-Z0-9]+")


def generate_python_enum(name: str, options: Dict[str, str]) -> enum.Enum:
    main_attrs = {}
    for option in options:
        enum_name = "_".join(re.findall(ENUM_NAME_REGEX, option)).upper()
        main_attrs[enum_name] = option
    return enum.Enum(name, main_attrs)
