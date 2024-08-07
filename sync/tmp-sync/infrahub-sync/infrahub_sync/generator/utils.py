from typing import List


def list_to_set(items: List[str]) -> str:
    """Convert a list in a string representation of a Set."""
    if not items:
        return "None"

    response = '"' + '", "'.join(items) + '"'
    if len(items) == 1:
        response += ","

    return "(" + response + ")"


def list_to_str(items: List[str]) -> str:
    """Convert a list into a string separated with comma"""
    return ", ".join(items)
