"""The drawing is a grid, and the sidebar it lives in is 24 columns wide."""

from __future__ import annotations

from napm import art

SIDEBAR = 24


def test_every_line_fits_the_sidebar():
    for line in art.MASCOT + art.WORDMARK + art.LEGEND:
        assert len(line) <= SIDEBAR


def test_the_padlock_can_be_left_out():
    assert art.MASCOT[0] not in art.banner(mascot=False)
    assert art.WORDMARK[0] in art.banner(mascot=False)


def test_the_legend_can_be_left_out():
    assert art.LEGEND[0] not in art.banner(legend=False)


def test_the_colours_are_theme_variables():
    """Hard-coded hex would ignore the palette the account picked."""
    markup = art.banner()

    assert "[$accent]" in markup
    assert "[$text-muted italic]" in markup
