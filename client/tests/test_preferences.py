"""The theme survives closing the app; Textual on its own does not remember it."""

from __future__ import annotations

import json

from napm import preferences


def test_nothing_stored_gives_the_empty_defaults(config_dir):
    assert preferences.load() == preferences.Preferences(theme="")


def test_a_saved_theme_comes_back(config_dir):
    preferences.save(preferences.Preferences(theme="nord"))

    assert preferences.load().theme == "nord"


def test_a_damaged_file_reads_as_nothing_chosen(config_dir):
    config_dir.mkdir(parents=True)
    preferences.path().write_text("{ this is not json")

    assert preferences.load() == preferences.Preferences()


def test_a_file_of_the_wrong_shape_reads_as_nothing_chosen(config_dir):
    config_dir.mkdir(parents=True)
    preferences.path().write_text(json.dumps({"theme": 12}))

    assert preferences.load() == preferences.Preferences()


def test_no_secret_is_written(config_dir):
    preferences.save(preferences.Preferences(theme="gruvbox"))

    body = json.loads(preferences.path().read_text())

    assert set(body) == {"theme"}
