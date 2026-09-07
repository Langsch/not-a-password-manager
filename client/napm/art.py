"""The drawing in the corner: a padlock asleep, and the wordmark under it.

Spelled out rather than generated. The figlet call that drew the wordmark and
the mirroring that drew the padlock both ran once, off to the side; keeping
them would mean a dependency and two helpers for eleven lines that never
change. The padlock's halves are still mirrors of each other, so an edit on
the left needs the same edit on the right with `/\\()[]<>` flipped.
"""

from __future__ import annotations

#: The padlock, dozing. Fourteen columns of drawing, four of margin.
MASCOT = [
    r"        .--.     z",
    r"      / |  | \  z",
    r"     .--'--'--.",
    r"     |  ^  ^  |",
    r"     '--------'",
]

#: The wordmark, twenty-two columns. Anything narrower than that clips it.
#: The trailing space on the second line is load-bearing: a raw string
#: cannot end in a backslash, and that line does.
WORDMARK = [
    r"  ___  ___ ____  __ _",
    r" / _ \/ _ `/ _ \/  ' \ ",
    r"/_//_/\_,_/ .__/_/_/_/",
    r"         /_/",
]

#: What the name is short for, said out loud.
LEGEND = [
    r"  definitely not a",
    r"  password manager",
]

WIDTH = 22


def banner(mascot: bool = True, legend: bool = True) -> str:
    """The corner as Textual markup.

    Markup and not a colour in the stylesheet: the legend is a different
    colour from the drawing above it, and the two are one widget. The colours
    are theme variables so the whole thing follows whatever palette is on.
    """
    drawing: list[str] = []

    if mascot:
        drawing += MASCOT
        drawing += [""]

    drawing += WORDMARK

    markup = "[$accent]" + "\n".join(drawing) + "[/]"

    if not legend:
        return markup

    words = "\n".join(LEGEND)

    return f"{markup}\n[$text-muted italic]{words}[/]"
