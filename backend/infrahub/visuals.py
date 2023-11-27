from typing import List

COLOR_SELECTION = [
    "#0B6581",
    "#0D3F54",
    "#0B1829",
    "#000000",
    "#FFFFFF",
    "#a7d9e6",
    "#23a1c1",
    "#3babc8",
    "#54b6cf",
    "#6cc0d6",
]


def select_color(existing: List[str]) -> str:
    """Select a color from a predefined list without including anything from a list of existing colors."""
    for color in COLOR_SELECTION:
        if color not in existing:
            existing.append(color)
            return color

    return "#ff0000"
