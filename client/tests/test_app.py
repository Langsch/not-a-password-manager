"""What decision 12 is about: the account password, held and then asked for again."""

from __future__ import annotations

import asyncio

from napm import api, session
from napm.app import NapmApp
from napm.screens.items import ItemsScreen
from napm.screens.login import LoginScreen
from napm.screens.modals import AskPassword, ShowSecrets
from tests.conftest import EMAIL, PASSWORD
from textual.widgets import DataTable, Input, Static


async def settle(pilot, rounds: int = 8):
    """Let the workers finish. They talk to the fake server, so this is quick."""
    for _ in range(rounds):
        await pilot.pause()
        await asyncio.sleep(0.01)


async def sign_in(pilot, app):
    app.screen.query_one("#email", Input).value = EMAIL
    app.screen.query_one("#password", Input).value = PASSWORD

    await pilot.click("#submit")
    await settle(pilot)


def shown_password(app) -> str:
    return str(app.screen.query_one("#password", Static).content)


async def test_signing_in_lands_on_the_list(server, config_dir):
    app = NapmApp(base_url="http://localhost:8000")

    async with app.run_test(size=(100, 40)) as pilot:
        await settle(pilot)

        assert isinstance(app.screen, LoginScreen)

        await sign_in(pilot, app)

        assert isinstance(app.screen, ItemsScreen)


async def test_a_wrong_password_stays_on_the_login_screen(server, config_dir):
    app = NapmApp(base_url="http://localhost:8000")

    async with app.run_test(size=(100, 40)) as pilot:
        await settle(pilot)

        app.screen.query_one("#email", Input).value = EMAIL
        app.screen.query_one("#password", Input).value = "not the password"

        await pilot.click("#submit")
        await settle(pilot)

        assert isinstance(app.screen, LoginScreen)
        assert "Wrong email or password." in str(app.screen.query_one("#status", Static).content)
        assert session.load() is None


async def test_the_list_shows_what_the_server_has(server, config_dir):
    client = api.Client("http://localhost:8000")
    await client.login(EMAIL, PASSWORD)
    await client.create_item("GitHub", "rafael", password="K7#mQ2vX!pL9")
    await client.create_item("Router", "admin", password="hunter2")
    await client.close()

    app = NapmApp(base_url="http://localhost:8000")

    async with app.run_test(size=(100, 40)) as pilot:
        await settle(pilot)
        await sign_in(pilot, app)

        table = app.screen.query_one("#items", DataTable)

        assert table.row_count == 2

        app.screen.query_one("#search", Input).value = "rout"
        await settle(pilot)

        assert table.row_count == 1


async def test_the_password_typed_at_sign_in_is_the_one_reveal_uses(server, config_dir):
    client = api.Client("http://localhost:8000")
    await client.login(EMAIL, PASSWORD)
    await client.create_item("GitHub", "rafael", password="K7#mQ2vX!pL9", notes="in the safe")
    await client.close()

    app = NapmApp(base_url="http://localhost:8000")

    async with app.run_test(size=(100, 40)) as pilot:
        await settle(pilot)
        await sign_in(pilot, app)

        app.screen.query_one("#items", DataTable).focus()

        await pilot.press("r")
        await settle(pilot)

        assert isinstance(app.screen, ShowSecrets)
        assert shown_password(app) == "K7#mQ2vX!pL9"

        await pilot.press("escape")
        await settle(pilot)

        # The second reveal asks for nothing: this is the whole point of the
        # app having a screen instead of being a one-shot command.
        await pilot.press("r")
        await settle(pilot)

        assert isinstance(app.screen, ShowSecrets)
        assert server.reveal_calls == 2


async def test_forgetting_the_password_makes_the_next_reveal_ask(server, config_dir):
    client = api.Client("http://localhost:8000")
    await client.login(EMAIL, PASSWORD)
    await client.create_item("GitHub", password="K7#mQ2vX!pL9")
    await client.close()

    app = NapmApp(base_url="http://localhost:8000")

    async with app.run_test(size=(100, 40)) as pilot:
        await settle(pilot)
        await sign_in(pilot, app)

        await pilot.press("ctrl+l")
        await settle(pilot)

        assert app.account_password is None

        app.screen.query_one("#items", DataTable).focus()

        await pilot.press("r")
        await settle(pilot)

        assert isinstance(app.screen, AskPassword)

        app.screen.query_one("#password", Input).value = "not the password"

        await pilot.click("#unlock")
        await settle(pilot)

        # A wrong one is not kept, or every later reveal would fail against a
        # password nobody typed again.
        assert isinstance(app.screen, ItemsScreen)
        assert app.account_password is None

        await pilot.press("r")
        await settle(pilot)

        app.screen.query_one("#password", Input).value = PASSWORD

        await pilot.click("#unlock")
        await settle(pilot)

        assert isinstance(app.screen, ShowSecrets)
        assert shown_password(app) == "K7#mQ2vX!pL9"


async def test_reopening_keeps_the_session_and_forgets_the_password(server, config_dir):
    client = api.Client("http://localhost:8000")
    await client.login(EMAIL, PASSWORD)
    await client.create_item("GitHub", password="K7#mQ2vX!pL9")
    await client.close()

    first = NapmApp(base_url="http://localhost:8000")

    async with first.run_test(size=(100, 40)) as pilot:
        await settle(pilot)
        await sign_in(pilot, first)

    assert session.load() is not None

    again = NapmApp(base_url="http://localhost:8000")

    async with again.run_test(size=(100, 40)) as pilot:
        await settle(pilot)

        # The token was on disk, so no login screen...
        assert isinstance(again.screen, ItemsScreen)
        assert again.account_password is None

        again.screen.query_one("#items", DataTable).focus()

        await pilot.press("r")
        await settle(pilot)

        # ...but the password was not, so the first reveal asks.
        assert isinstance(again.screen, AskPassword)


async def test_signing_out_drops_the_stored_session(server, config_dir):
    app = NapmApp(base_url="http://localhost:8000")

    async with app.run_test(size=(100, 40)) as pilot:
        await settle(pilot)
        await sign_in(pilot, app)

        await pilot.press("ctrl+o")
        await settle(pilot)

        assert isinstance(app.screen, LoginScreen)
        assert app.account_password is None
        assert session.load() is None


async def test_an_expired_token_sends_you_back_to_the_login_screen(server, config_dir):
    client = api.Client("http://localhost:8000")
    opened = await client.login(EMAIL, PASSWORD)
    await client.close()

    session.save(
        session.StoredSession(
            base_url="http://localhost:8000",
            token=opened.token,
            expires_at=opened.expires_at,
        )
    )

    # Killed on the server while the file on disk still looks fine.
    server.tokens.clear()

    app = NapmApp(base_url="http://localhost:8000")

    async with app.run_test(size=(100, 40)) as pilot:
        await settle(pilot)

        assert isinstance(app.screen, LoginScreen)
        assert session.load() is None


async def test_creating_an_item_shows_the_password_the_server_drew(server, config_dir):
    app = NapmApp(base_url="http://localhost:8000")

    async with app.run_test(size=(100, 40)) as pilot:
        await settle(pilot)
        await sign_in(pilot, app)

        await pilot.press("n")
        await settle(pilot)

        app.screen.query_one("#name", Input).value = "Router"
        app.screen.query_one("#username", Input).value = "admin"

        await pilot.click("#save")
        await settle(pilot)

        assert isinstance(app.screen, ShowSecrets)
        assert len(shown_password(app)) == 20


async def test_deleting_asks_first(server, config_dir):
    client = api.Client("http://localhost:8000")
    await client.login(EMAIL, PASSWORD)
    await client.create_item("GitHub", password="K7#mQ2vX!pL9")
    await client.close()

    app = NapmApp(base_url="http://localhost:8000")

    async with app.run_test(size=(100, 40)) as pilot:
        await settle(pilot)
        await sign_in(pilot, app)

        app.screen.query_one("#items", DataTable).focus()

        await pilot.press("d")
        await settle(pilot)

        await pilot.press("escape")
        await settle(pilot)

        assert len(server.items) == 1

        await pilot.press("d")
        await settle(pilot)

        await pilot.click("#confirm")
        await settle(pilot)

        assert server.items == {}


async def test_the_confirm_field_belongs_to_registering_only(server, config_dir):
    app = NapmApp(base_url="http://localhost:8000")

    async with app.run_test(size=(100, 40)) as pilot:
        await settle(pilot)

        assert not app.screen.query_one("#confirm", Input).display

        await pilot.click("Tab#register")
        await settle(pilot)

        assert app.screen.query_one("#confirm", Input).display


async def test_creating_an_account_signs_you_straight_in(server, config_dir):
    app = NapmApp(base_url="http://localhost:8000")

    async with app.run_test(size=(100, 40)) as pilot:
        await settle(pilot)

        await pilot.click("Tab#register")
        await settle(pilot)

        app.screen.query_one("#email", Input).value = "someone@example.com"
        app.screen.query_one("#password", Input).value = "a brand new password"
        app.screen.query_one("#confirm", Input).value = "a brand new password"

        await pilot.click("#submit")
        await settle(pilot)

        assert isinstance(app.screen, ItemsScreen)
        assert server.users["someone@example.com"] == "a brand new password"


async def test_two_different_passwords_never_reach_the_server(server, config_dir):
    app = NapmApp(base_url="http://localhost:8000")

    async with app.run_test(size=(100, 40)) as pilot:
        await settle(pilot)

        await pilot.click("Tab#register")
        await settle(pilot)

        app.screen.query_one("#email", Input).value = "someone@example.com"
        app.screen.query_one("#password", Input).value = "one thing"
        app.screen.query_one("#confirm", Input).value = "another thing"

        await pilot.click("#submit")
        await settle(pilot)

        assert isinstance(app.screen, LoginScreen)
        assert "do not match" in str(app.screen.query_one("#status", Static).content)
        assert "someone@example.com" not in server.users


async def test_registering_a_taken_email_says_so_on_the_screen(server, config_dir):
    app = NapmApp(base_url="http://localhost:8000")

    async with app.run_test(size=(100, 40)) as pilot:
        await settle(pilot)

        await pilot.click("Tab#register")
        await settle(pilot)

        app.screen.query_one("#email", Input).value = EMAIL
        app.screen.query_one("#password", Input).value = PASSWORD
        app.screen.query_one("#confirm", Input).value = PASSWORD

        await pilot.click("#submit")
        await settle(pilot)

        assert isinstance(app.screen, LoginScreen)
        assert "already has an account" in str(app.screen.query_one("#status", Static).content)


async def test_the_header_says_which_account_on_which_server(server, config_dir):
    app = NapmApp(base_url="http://localhost:8000")

    async with app.run_test(size=(100, 40)) as pilot:
        await settle(pilot)
        await sign_in(pilot, app)

        assert app.sub_title == f"{EMAIL} · localhost:8000"


async def test_the_meters_say_whether_a_reveal_will_ask(server, config_dir):
    app = NapmApp(base_url="http://localhost:8000")

    async with app.run_test(size=(100, 40)) as pilot:
        await settle(pilot)
        await sign_in(pilot, app)

        reveal_meter = app.screen.query_one("#meter-reveal", Static)

        assert "no prompt" in str(reveal_meter.content)

        await pilot.press("ctrl+l")
        await settle(pilot)

        assert "asks first" in str(reveal_meter.content)
