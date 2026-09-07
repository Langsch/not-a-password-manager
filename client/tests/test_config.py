from __future__ import annotations

from napm import config


def test_the_default_is_localhost(monkeypatch):
    monkeypatch.delenv(config.API_URL_VARIABLE, raising=False)

    assert config.api_url() == config.DEFAULT_API_URL


def test_the_environment_decides(monkeypatch):
    monkeypatch.setenv(config.API_URL_VARIABLE, "http://home-server:9000")

    assert config.api_url() == "http://home-server:9000"


def test_an_empty_variable_is_not_an_address(monkeypatch):
    monkeypatch.setenv(config.API_URL_VARIABLE, "   ")

    assert config.api_url() == config.DEFAULT_API_URL
