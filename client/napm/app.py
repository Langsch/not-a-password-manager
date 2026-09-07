"""The application itself: what it holds, and what happens between screens.

The account password lives here, in an attribute, for as long as the process
does. That is the whole reason this client has a screen instead of being a
command — see the reveal below, which asks for it once and then stops asking.
"""

from __future__ import annotations

import contextlib

from textual.app import App

from napm import api, errors, preferences, session
from napm.screens.login import LoginScreen
from napm.screens.main import MainScreen
from napm.screens.modals import HELD_IN_MEMORY, AskPassword


class NapmApp(App[None]):
    CSS_PATH = "napm.tcss"
    TITLE = "napm"

    def __init__(self, base_url: str) -> None:
        super().__init__()

        self.base_url = base_url
        self.email = ""
        self.account_password: str | None = None
        self._client: api.Client | None = None

        # Read before mounting: the theme is applied on mount, and saving is
        # only armed afterwards so the default does not overwrite the choice
        # on the way in.
        self._preferences = preferences.load()
        self._remember_theme = False

    @property
    def client(self) -> api.Client:
        if self._client is None:
            raise errors.Unauthenticated()

        return self._client

    def on_mount(self) -> None:
        self.apply_theme()

        stored = session.load()

        if stored is None:
            self.push_screen(LoginScreen(self.base_url))
            return

        # A token is only good against the server that issued it, so a change
        # of address in the environment means signing in again rather than
        # replaying it somewhere it means nothing.
        if stored.base_url != self.base_url or stored.is_expired():
            session.clear()
            self.push_screen(LoginScreen(self.base_url, email=stored.email))
            return

        self._client = api.Client(stored.base_url, token=stored.token)
        self.email = stored.email
        self.sub_title = stored.email

        self.push_screen(MainScreen())

    def apply_theme(self) -> None:
        chosen = self._preferences.theme

        if chosen and chosen in self.available_themes:
            self.theme = chosen

        self._remember_theme = True

    def watch_theme(self, theme: str) -> None:
        """Textual forgets the theme between runs; this is what remembers it."""
        if not self._remember_theme:
            return

        preferences.save(preferences.Preferences(theme=theme))

    async def on_unmount(self) -> None:
        self.account_password = None

        if self._client is not None:
            await self._client.close()

    async def begin_session(self, client: api.Client, email: str, account_password: str) -> None:
        if self._client is not None:
            await self._client.close()

        self._client = client
        self.email = email
        self.sub_title = email
        self.account_password = account_password

        self.switch_screen(MainScreen())

    async def reveal(self, item: api.Item) -> api.Secrets | None:
        """The account password, asked once and then remembered until close."""
        password = self.account_password

        if password is None:
            password = await self.push_screen_wait(AskPassword(HELD_IN_MEMORY))

            if password is None:
                return None

        try:
            secrets = await self.client.reveal_item(item.id, password)
        except errors.InvalidCredentials:
            # Whatever was being held was wrong — drop it, or every later
            # reveal fails silently against a password nobody typed again.
            self.account_password = None

            self.notify("Wrong account password.", severity="error")
            return None
        except errors.ApiError as failure:
            await self.report(failure)
            return None

        self.account_password = password

        return secrets

    def forget_password(self) -> None:
        if self.account_password is None:
            self.notify("Nothing held.")
            return

        self.account_password = None

        self.notify("Account password forgotten. The next reveal will ask.")

    async def sign_out(self) -> None:
        if self._client is not None:
            # The session is being abandoned either way; a server that is
            # unreachable or a token already dead changes nothing here.
            with contextlib.suppress(errors.ApiError):
                await self._client.logout()

            await self._client.close()
            self._client = None

        self.back_to_login()

    async def password_changed(self) -> None:
        """The server dropped every session, including the one in hand."""
        if self._client is not None:
            await self._client.close()
            self._client = None

        self.back_to_login()

        self.notify("Password changed. Sign in again.")

    async def report(self, failure: errors.ApiError) -> None:
        """What a screen does with a failure it cannot handle itself."""
        if isinstance(failure, errors.Unauthenticated):
            await self.expire_session()
            return

        self.notify(failure.message, severity="error")

    async def expire_session(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None

        self.back_to_login()

        self.notify("Your session expired. Sign in again.", severity="warning")

    def back_to_login(self) -> None:
        email = self.email

        session.clear()

        self.account_password = None
        self.email = ""
        self.sub_title = ""

        self.switch_screen(LoginScreen(self.base_url, email=email))
