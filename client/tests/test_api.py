from __future__ import annotations

import httpx
import pytest
from napm import api, errors
from tests.conftest import EMAIL, PASSWORD


async def signed_in(server) -> api.Client:
    client = api.Client("http://localhost:8000")

    await client.login(EMAIL, PASSWORD)

    return client


async def test_login_returns_a_token_and_keeps_it(server):
    client = api.Client("http://localhost:8000")

    session = await client.login(EMAIL, PASSWORD)

    assert session.token
    assert client.token == session.token

    await client.close()


async def test_a_wrong_password_is_invalid_credentials(server):
    client = api.Client("http://localhost:8000")

    with pytest.raises(errors.InvalidCredentials):
        await client.login(EMAIL, "not the password")

    await client.close()


async def test_registering_a_taken_email_says_so(server):
    client = api.Client("http://localhost:8000")

    with pytest.raises(errors.EmailAlreadyRegistered):
        await client.register(EMAIL, PASSWORD)

    await client.close()


async def test_a_call_without_a_token_never_leaves(server):
    client = api.Client("http://localhost:8000")

    with pytest.raises(errors.Unauthenticated):
        await client.list_items()

    await client.close()


async def test_a_dead_token_is_unauthenticated(server):
    client = await signed_in(server)

    await client.logout()

    client.token = "a token that no longer exists"

    with pytest.raises(errors.Unauthenticated):
        await client.list_items()

    await client.close()


async def test_creating_without_a_password_gets_one_from_the_server(server):
    client = await signed_in(server)

    item = await client.create_item("GitHub", "rafael")

    assert item.password is not None
    assert len(item.password) == 20

    await client.close()


async def test_creating_with_a_password_echoes_nothing_back(server):
    client = await signed_in(server)

    item = await client.create_item("GitHub", "rafael", password="K7#mQ2vX!pL9")

    assert item.password is None

    await client.close()


async def test_the_listing_carries_no_secrets(server):
    client = await signed_in(server)

    await client.create_item("GitHub", "rafael", notes="a note")

    page = await client.list_items()

    assert [item.name for item in page.items] == ["GitHub"]
    assert page.items[0].password is None
    assert page.total == 1

    await client.close()


async def test_search_narrows_the_listing(server):
    client = await signed_in(server)

    await client.create_item("GitHub", "rafael")
    await client.create_item("Router", "admin")

    page = await client.list_items(query="rout")

    assert [item.name for item in page.items] == ["Router"]

    await client.close()


async def test_paging_reports_where_it_is(server):
    client = await signed_in(server)

    for number in range(5):
        await client.create_item(f"Item {number}")

    page = await client.list_items(page=2, per_page=2)

    assert page.page == 2
    assert page.pages == 3
    assert page.total == 5
    assert len(page.items) == 2

    await client.close()


async def test_reveal_returns_the_stored_secrets(server):
    client = await signed_in(server)

    item = await client.create_item("GitHub", password="K7#mQ2vX!pL9", notes="in the safe")

    secrets = await client.reveal_item(item.id, PASSWORD)

    assert secrets.password == "K7#mQ2vX!pL9"
    assert secrets.notes == "in the safe"

    await client.close()


async def test_reveal_with_a_wrong_account_password_reveals_nothing(server):
    client = await signed_in(server)

    item = await client.create_item("GitHub", password="K7#mQ2vX!pL9")

    with pytest.raises(errors.InvalidCredentials):
        await client.reveal_item(item.id, "not the password")

    await client.close()


async def test_an_unknown_item_is_not_found(server):
    client = await signed_in(server)

    with pytest.raises(errors.ItemNotFound):
        await client.reveal_item("00000000-0000-0000-0000-000000000000", PASSWORD)

    await client.close()


async def test_an_update_sends_only_the_fields_it_was_given(server):
    client = await signed_in(server)

    item = await client.create_item("GitHub", "rafael", password="K7#mQ2vX!pL9", notes="a note")

    changes = api.ItemChanges(name="GitHub Enterprise")

    await client.update_item(item.id, changes)

    secrets = await client.reveal_item(item.id, PASSWORD)
    page = await client.list_items()

    assert page.items[0].name == "GitHub Enterprise"
    assert page.items[0].username == "rafael"
    assert secrets.password == "K7#mQ2vX!pL9"
    assert secrets.notes == "a note"

    await client.close()


async def test_a_field_set_to_none_is_cleared(server):
    client = await signed_in(server)

    item = await client.create_item("GitHub", "rafael")

    await client.update_item(item.id, api.ItemChanges(username=None))

    page = await client.list_items()

    assert page.items[0].username is None

    await client.close()


async def test_rotating_returns_the_new_password(server):
    client = await signed_in(server)

    item = await client.create_item("GitHub", password="K7#mQ2vX!pL9")

    rotated = await client.update_item(item.id, api.ItemChanges(generate_password=True))

    assert rotated.password is not None
    assert rotated.password != "K7#mQ2vX!pL9"

    secrets = await client.reveal_item(item.id, PASSWORD)

    assert secrets.password == rotated.password

    await client.close()


async def test_deleting_is_final(server):
    client = await signed_in(server)

    item = await client.create_item("GitHub")

    await client.delete_item(item.id)

    with pytest.raises(errors.ItemNotFound):
        await client.delete_item(item.id)

    await client.close()


async def test_a_server_that_answers_nothing_is_unreachable(monkeypatch):
    def build_http(root: str) -> httpx.AsyncClient:
        def refuse(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("nothing listening", request=request)

        return httpx.AsyncClient(base_url=root, transport=httpx.MockTransport(refuse))

    monkeypatch.setattr(api, "build_http", build_http)

    client = api.Client("http://localhost:9")

    with pytest.raises(errors.Unreachable):
        await client.health()

    await client.close()


def test_an_untouched_change_set_sends_an_empty_body():
    assert api.ItemChanges().to_body() == {}


def test_a_change_set_distinguishes_clearing_from_leaving_alone():
    body = api.ItemChanges(username=None).to_body()

    assert body == {"username": None}
