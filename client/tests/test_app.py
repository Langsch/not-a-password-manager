"""What decision 12 is about: the account password, held and then asked for again."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from napm import api, preferences, session
from napm.app import NapmApp
from napm.screens.items_pane import ItemsPane
from napm.screens.login import LoginScreen
from napm.screens.main import MainScreen
from napm.screens.modals import AskPassword, ShowSecrets
from tests.conftest import EMAIL, PASSWORD
from textual.widgets import ContentSwitcher, DataTable, Input, ListView, Static

BASE = "http://localhost:8000"


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


async def seed(server, *items):
    client = api.Client(BASE)
    await client.login(EMAIL, PASSWORD)

    for name, username, password, notes in items:
        await client.create_item(name, username, password=password, notes=notes)

    await client.close()


def table(app) -> DataTable:
    return app.screen.query_one("#items", DataTable)


def shown_password(app) -> str:
    return str(app.screen.query_one("#detail-password", Static).content)


# --- signing in ---------------------------------------------------------------


async def test_signing_in_lands_on_the_main_screen(server, config_dir):
    app = NapmApp(base_url=BASE)

    async with app.run_test(size=(100, 40)) as pilot:
        await settle(pilot)

        assert isinstance(app.screen, LoginScreen)

        await sign_in(pilot, app)

        assert isinstance(app.screen, MainScreen)


async def test_the_login_screen_has_no_field_for_the_server(server, config_dir):
    """The address is settled in the environment, before the app starts."""
    app = NapmApp(base_url=BASE)

    async with app.run_test(size=(100, 40)) as pilot:
        await settle(pilot)

        assert not app.screen.query("#base-url")


async def test_a_wrong_password_stays_on_the_login_screen(server, config_dir):
    app = NapmApp(base_url=BASE)

    async with app.run_test(size=(100, 40)) as pilot:
        await settle(pilot)

        app.screen.query_one("#email", Input).value = EMAIL
        app.screen.query_one("#password", Input).value = "not the password"

        await pilot.click("#submit")
        await settle(pilot)

        assert isinstance(app.screen, LoginScreen)
        assert "Wrong email or password." in str(app.screen.query_one("#status", Static).content)
        assert session.load() is None


async def test_a_session_for_another_server_is_not_replayed(server, config_dir):
    """The address changed in the environment, so the token means nothing."""
    session.save(
        session.StoredSession(
            base_url="http://somewhere-else:8000",
            token="a token from another installation",
            expires_at=datetime.now(UTC) + timedelta(days=7),
            email=EMAIL,
        )
    )

    app = NapmApp(base_url=BASE)

    async with app.run_test(size=(100, 40)) as pilot:
        await settle(pilot)

        assert isinstance(app.screen, LoginScreen)
        assert session.load() is None


# --- the list -----------------------------------------------------------------


async def test_the_list_shows_what_the_server_has(server, config_dir):
    await seed(
        server,
        ("GitHub", "rafael", "K7#mQ2vX!pL9", None),
        ("Router", "admin", "hunter2", None),
    )

    app = NapmApp(base_url=BASE)

    async with app.run_test(size=(100, 40)) as pilot:
        await settle(pilot)
        await sign_in(pilot, app)

        assert table(app).row_count == 2

        app.screen.query_one("#search", Input).value = "rout"
        await settle(pilot)

        assert table(app).row_count == 1


async def test_the_list_never_carries_a_password(server, config_dir):
    await seed(server, ("GitHub", "rafael", "K7#mQ2vX!pL9", None))

    app = NapmApp(base_url=BASE)

    async with app.run_test(size=(100, 40)) as pilot:
        await settle(pilot)
        await sign_in(pilot, app)

        assert "K7#mQ2vX!pL9" not in shown_password(app)


# --- revealing ----------------------------------------------------------------


async def test_the_password_typed_at_sign_in_is_the_one_reveal_uses(server, config_dir):
    await seed(server, ("GitHub", "rafael", "K7#mQ2vX!pL9", "in the safe"))

    app = NapmApp(base_url=BASE)

    async with app.run_test(size=(100, 40)) as pilot:
        await settle(pilot)
        await sign_in(pilot, app)

        await pilot.press("r")
        await settle(pilot)

        assert "K7#mQ2vX!pL9" in shown_password(app)

        # The second reveal asks for nothing: this is the whole point of the
        # app having a screen instead of being a one-shot command.
        await pilot.press("r")
        await settle(pilot)

        assert server.reveal_calls == 2
        assert not app.screen.query(AskPassword)


async def test_moving_the_cursor_puts_the_password_away(server, config_dir):
    await seed(
        server,
        ("GitHub", "rafael", "K7#mQ2vX!pL9", None),
        ("Router", "admin", "hunter2", None),
    )

    app = NapmApp(base_url=BASE)

    async with app.run_test(size=(100, 40)) as pilot:
        await settle(pilot)
        await sign_in(pilot, app)

        await pilot.press("r")
        await settle(pilot)

        assert "K7#mQ2vX!pL9" in shown_password(app)

        await pilot.press("down")
        await settle(pilot)

        assert "K7#mQ2vX!pL9" not in shown_password(app)


async def test_forgetting_the_password_makes_the_next_reveal_ask(server, config_dir):
    await seed(server, ("GitHub", None, "K7#mQ2vX!pL9", None))

    app = NapmApp(base_url=BASE)

    async with app.run_test(size=(100, 40)) as pilot:
        await settle(pilot)
        await sign_in(pilot, app)

        await pilot.press("ctrl+l")
        await settle(pilot)

        assert app.account_password is None

        await pilot.press("r")
        await settle(pilot)

        assert isinstance(app.screen, AskPassword)

        app.screen.query_one("#password", Input).value = "not the password"

        await pilot.click("#unlock")
        await settle(pilot)

        # A wrong one is not kept, or every later reveal would fail against a
        # password nobody typed again.
        assert isinstance(app.screen, MainScreen)
        assert app.account_password is None

        await pilot.press("r")
        await settle(pilot)

        app.screen.query_one("#password", Input).value = PASSWORD

        await pilot.click("#unlock")
        await settle(pilot)

        assert isinstance(app.screen, MainScreen)
        assert "K7#mQ2vX!pL9" in shown_password(app)


async def test_reopening_keeps_the_session_and_forgets_the_password(server, config_dir):
    await seed(server, ("GitHub", None, "K7#mQ2vX!pL9", None))

    first = NapmApp(base_url=BASE)

    async with first.run_test(size=(100, 40)) as pilot:
        await settle(pilot)
        await sign_in(pilot, first)

    stored = session.load()

    assert stored is not None
    assert stored.email == EMAIL

    again = NapmApp(base_url=BASE)

    async with again.run_test(size=(100, 40)) as pilot:
        await settle(pilot)

        # The token was on disk, so no login screen...
        assert isinstance(again.screen, MainScreen)
        assert again.account_password is None

        await pilot.press("r")
        await settle(pilot)

        # ...but the password was not, so the first reveal asks.
        assert isinstance(again.screen, AskPassword)


# --- writing ------------------------------------------------------------------


async def test_creating_an_item_shows_the_password_the_server_drew(server, config_dir):
    app = NapmApp(base_url=BASE)

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
        assert len(str(app.screen.query_one("#password", Static).content)) == 20


async def test_deleting_asks_first(server, config_dir):
    await seed(server, ("GitHub", None, "K7#mQ2vX!pL9", None))

    app = NapmApp(base_url=BASE)

    async with app.run_test(size=(100, 40)) as pilot:
        await settle(pilot)
        await sign_in(pilot, app)

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


# --- the sidebar --------------------------------------------------------------


async def test_the_menu_switches_panes(server, config_dir):
    app = NapmApp(base_url=BASE)

    async with app.run_test(size=(100, 40)) as pilot:
        await settle(pilot)
        await sign_in(pilot, app)

        switcher = app.screen.query_one("#main", ContentSwitcher)

        assert switcher.current == "passwords"

        app.screen.query_one("#nav", ListView).focus()
        await pilot.press("down")
        await settle(pilot)

        assert switcher.current == "account"


async def test_the_meters_say_whether_a_reveal_will_ask(server, config_dir):
    app = NapmApp(base_url=BASE)

    async with app.run_test(size=(100, 40)) as pilot:
        await settle(pilot)
        await sign_in(pilot, app)

        meter = app.screen.query_one("#meter-reveal", Static)

        assert "no prompt" in str(meter.content)

        await pilot.press("ctrl+l")
        await settle(pilot)

        assert "asks first" in str(meter.content)


async def test_the_meters_count_what_the_list_holds(server, config_dir):
    await seed(
        server,
        ("GitHub", None, "one", None),
        ("Router", None, "two", None),
    )

    app = NapmApp(base_url=BASE)

    async with app.run_test(size=(100, 40)) as pilot:
        await settle(pilot)
        await sign_in(pilot, app)

        assert app.screen.query_one(ItemsPane).total == 2
        assert "2" in str(app.screen.query_one("#meter-items", Static).content)


# --- the account pane ---------------------------------------------------------


async def go_to_account(pilot, app):
    app.screen.query_one("#nav", ListView).focus()
    await pilot.press("down")
    await settle(pilot)


async def test_changing_the_account_password_sends_you_back_to_the_login_screen(
    server,
    config_dir,
):
    app = NapmApp(base_url=BASE)

    async with app.run_test(size=(100, 40)) as pilot:
        await settle(pilot)
        await sign_in(pilot, app)
        await go_to_account(pilot, app)

        app.screen.query_one("#current-password", Input).value = PASSWORD
        app.screen.query_one("#new-password", Input).value = "a longer better password"
        app.screen.query_one("#confirm-password", Input).value = "a longer better password"

        await pilot.click("#change")
        await settle(pilot)

        assert isinstance(app.screen, LoginScreen)
        assert session.load() is None
        assert app.account_password is None
        assert server.users[EMAIL] == "a longer better password"


async def test_two_different_new_passwords_never_reach_the_server(server, config_dir):
    app = NapmApp(base_url=BASE)

    async with app.run_test(size=(100, 40)) as pilot:
        await settle(pilot)
        await sign_in(pilot, app)
        await go_to_account(pilot, app)

        app.screen.query_one("#current-password", Input).value = PASSWORD
        app.screen.query_one("#new-password", Input).value = "one thing"
        app.screen.query_one("#confirm-password", Input).value = "another thing"

        await pilot.click("#change")
        await settle(pilot)

        assert isinstance(app.screen, MainScreen)
        assert "do not match" in str(app.screen.query_one("#account-status", Static).content)
        assert server.users[EMAIL] == PASSWORD


async def test_a_wrong_current_password_changes_nothing(server, config_dir):
    app = NapmApp(base_url=BASE)

    async with app.run_test(size=(100, 40)) as pilot:
        await settle(pilot)
        await sign_in(pilot, app)
        await go_to_account(pilot, app)

        app.screen.query_one("#current-password", Input).value = "not the password"
        app.screen.query_one("#new-password", Input).value = "a longer better password"
        app.screen.query_one("#confirm-password", Input).value = "a longer better password"

        await pilot.click("#change")
        await settle(pilot)

        assert isinstance(app.screen, MainScreen)
        assert server.users[EMAIL] == PASSWORD


# --- signing out --------------------------------------------------------------


async def test_signing_out_drops_the_stored_session(server, config_dir):
    app = NapmApp(base_url=BASE)

    async with app.run_test(size=(100, 40)) as pilot:
        await settle(pilot)
        await sign_in(pilot, app)

        await pilot.press("ctrl+o")
        await settle(pilot)

        assert isinstance(app.screen, LoginScreen)
        assert app.account_password is None
        assert session.load() is None


async def test_an_expired_token_sends_you_back_to_the_login_screen(server, config_dir):
    client = api.Client(BASE)
    opened = await client.login(EMAIL, PASSWORD)
    await client.close()

    session.save(
        session.StoredSession(
            base_url=BASE,
            token=opened.token,
            expires_at=opened.expires_at,
            email=EMAIL,
        )
    )

    # Killed on the server while the file on disk still looks fine.
    server.tokens.clear()

    app = NapmApp(base_url=BASE)

    async with app.run_test(size=(100, 40)) as pilot:
        await settle(pilot)

        assert isinstance(app.screen, LoginScreen)
        assert session.load() is None


# --- what the app remembers about itself --------------------------------------


async def test_the_theme_survives_closing_the_app(server, config_dir):
    """Textual resets `theme` to its default on every run; this is what does not."""
    app = NapmApp(base_url=BASE)

    async with app.run_test(size=(100, 40)) as pilot:
        await settle(pilot)

        app.theme = "gruvbox"

        await settle(pilot)

    assert preferences.load().theme == "gruvbox"

    again = NapmApp(base_url=BASE)

    async with again.run_test(size=(100, 40)) as pilot:
        await settle(pilot)

        assert again.theme == "gruvbox"


async def test_a_theme_that_no_longer_exists_is_ignored(server, config_dir):
    preferences.save(preferences.Preferences(theme="a-theme-from-another-version"))

    app = NapmApp(base_url=BASE)

    async with app.run_test(size=(100, 40)) as pilot:
        await settle(pilot)

        assert app.theme in app.available_themes


async def test_starting_up_does_not_overwrite_the_stored_theme(server, config_dir):
    """The default is applied before the file is read, so arming the save late
    is what keeps it from clobbering the choice on the way in."""
    preferences.save(preferences.Preferences(theme="nord"))

    app = NapmApp(base_url=BASE)

    async with app.run_test(size=(100, 40)) as pilot:
        await settle(pilot)

    assert preferences.load().theme == "nord"
