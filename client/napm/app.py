"""The application itself: what it holds, and what happens between screens.

The account password lives here, in an attribute, for as long as the process
does. That is the whole reason this client has a screen instead of being a
command — see the reveal below, which asks for it once and then stops asking.
"""

from __future__ import annotations

import contextlib

from textual.app import App

from napm import api, errors, session
from napm.screens.items import ItemsScreen
from napm.screens.login import LoginScreen
from napm.screens.modals import HELD_IN_MEMORY, AskPassword


class NapmApp(App[None]):
    CSS_PATH = "napm.tcss"
    TITLE = "not-a-password-manager"

    def __init__(self, base_url: str | None = None) -> None:
        super().__init__()

        self.requested_base_url = base_url
        self.account_password: str | None = None
        self._client: api.Client | None = None

    @property
    def client(self) -> api.Client:
        if self._client is None:
            raise errors.Unauthenticated()

        return self._client

    def on_mount(self) -> None:
        stored = session.load()

        if stored is None:
            self.push_screen(LoginScreen(self.requested_base_url or session.DEFAULT_BASE_URL))
            return

        # A token is only good against the server that issued it, so asking for
        # a different address means signing in again rather than replaying it.
        if self.requested_base_url is not None and self.requested_base_url != stored.base_url:
            self.push_screen(LoginScreen(self.requested_base_url))
            return

        if stored.is_expired():
            session.clear()
            self.push_screen(LoginScreen(stored.base_url))
            return

        self._client = api.Client(stored.base_url, token=stored.token)

        self.show_where(stored.base_url)
        self.push_screen(ItemsScreen())

    async def on_unmount(self) -> None:
        self.account_password = None

        if self._client is not None:
            await self._client.close()

    async def begin_session(self, client: api.Client, email: str, account_password: str) -> None:
        if self._client is not None:
            await self._client.close()

        self._client = client
        self.account_password = account_password

        self.show_where(client.base_url, email)
        self.switch_screen(ItemsScreen())

    def show_where(self, base_url: str, email: str = "") -> None:
        """The header says which account on which server, so two open windows
        against two servers are never confused for one another."""
        address = base_url.removeprefix("https://").removeprefix("http://")

        if email:
            self.sub_title = f"{email} · {address}"
        else:
            self.sub_title = address

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

        base_url = session.DEFAULT_BASE_URL
        stored = session.load()

        if stored is not None:
            base_url = stored.base_url

        session.clear()
        self.account_password = None
        self.sub_title = ""

        self.switch_screen(LoginScreen(base_url))

    async def report(self, failure: errors.ApiError) -> None:
        """What a screen does with a failure it cannot handle itself."""
        if isinstance(failure, errors.Unauthenticated):
            await self.expire_session()
            return

        self.notify(failure.message, severity="error")

    async def expire_session(self) -> None:
        base_url = session.DEFAULT_BASE_URL
        stored = session.load()

        if stored is not None:
            base_url = stored.base_url

        session.clear()
        self.account_password = None

        if self._client is not None:
            await self._client.close()
            self._client = None

        self.switch_screen(LoginScreen(base_url))
        self.notify("Your session expired. Sign in again.", severity="warning")
