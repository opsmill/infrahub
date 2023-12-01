from typing import List

COLOR_SELECTION = [
    "#0b6581",
    "#0d3f54",
    "#0b1829",
    "#000000",
    "#ffffff",
    "#a7d9e6",
    "#23a1c1",
    "#3babc8",
    "#f7dc6f",
    "#6cc0d6",
    "#ffe040",
    "#21184f",
    "#405fff",
    "#ff405f",
    "#ff40bf",
    "#ffa500",
    "#0000ff",
    "#800080",
    "#468499",
    "#20b2aa",
]


def select_color(existing: List[str]) -> str:
    """Select a color from a predefined list without including anything from a list of existing colors."""
    for color in COLOR_SELECTION:
        if color not in existing:
            existing.append(color)
            return color

    return "#ff0000"
