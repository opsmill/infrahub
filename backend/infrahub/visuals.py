COLOR_SELECTION = [
    "#ed6a5a",
    "#f4f1bb",
    "#9bc1bc",
    "#5ca4a9",
    "#e6ebe0",
    "#52489c",
    "#4062bb",
    "#59c3c3",
    "#56638a",
    "#5d737e",
    "#55505c",
    "#592941",
    "#498467",
    "#e5d0e3",
    "#748cab",
    "#018e42",
    "#50808e",
    "#7b2d26",
    "#9799ca",
    "#51bbfe",
]


def select_color(existing: list[str]) -> str:
    """Select a color from a predefined list without including anything from a list of existing colors."""
    for color in COLOR_SELECTION:
        if color not in existing:
            existing.append(color)
            return color

    return "#ff0000"
