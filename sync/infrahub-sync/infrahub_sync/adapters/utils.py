from typing import Any, Optional


def get_value(obj, name: str):
    """Query a value in dot notation recursively"""
    if "." not in name:
        # Check if the object is a dictionary and use appropriate method to access the attribute.
        if isinstance(obj, dict):
            return obj.get(name)
        return getattr(obj, name, None)

    first_name, remaining_part = name.split(".", maxsplit=1)

    # Check if the object is a dictionary and use appropriate method to access the attribute.
    if isinstance(obj, dict):
        sub_obj = obj.get(first_name)
    else:
        sub_obj = getattr(obj, first_name, None)

    if not sub_obj:
        return None
    return get_value(obj=sub_obj, name=remaining_part)


def derive_identifier_key(obj: dict[str, Any]) -> Optional[str]:
    """Try to get obj.id, and if it doesn't exist, try to get a key ending with _id"""
    obj_id = obj.get("id", None)
    if obj_id is None:
        for key, value in obj.items():
            if key.endswith("_id"):
                if value:
                    obj_id = value
                    break

    # If we still didn't find any id, raise ValueError
    if obj_id is None:
        raise ValueError("No suitable identifier key found in object")
    return obj_id
