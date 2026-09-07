"""Signing in, and creating the account the first time.

The two are one card with a mode, not two buttons side by side: they ask for
almost the same thing, and a screen offering both at once leaves you guessing
which one you are about to do.

There is no field for the server. It comes from the environment before the app
starts — see `napm.config`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Input, Static, Tab, Tabs

from napm import api, errors, session
from napm.art import WORDMARK

if TYPE_CHECKING:
    from napm.app import NapmApp

SIGN_IN = "sign-in"
REGISTER = "register"

TAGLINE = "A password notebook that belongs to you."

NO_RESET = "No password reset — forget this one and what is stored is gone."


class LoginScreen(Screen[None]):
    """One card, centred, in one of two modes."""

    BINDINGS = [("ctrl+q", "quit", "Quit")]

    def __init__(self, base_url: str, email: str = "") -> None:
        super().__init__()

        self.base_url = base_url
        self.email = email
        self.mode = SIGN_IN

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="login-frame"), Vertical(id="login-card"):
            yield Static(WORDMARK, id="login-art")
            yield Static(TAGLINE, classes="brand-tagline")

            yield Tabs(
                Tab("Sign in", id=SIGN_IN),
                Tab("Create account", id=REGISTER),
                id="mode",
            )

            yield Input(value=self.email, id="email")
            yield Input(password=True, id="password")
            yield Input(password=True, id="confirm")

            yield Static(NO_RESET, id="warning", classes="hint")

            with Horizontal(classes="buttons"):
                yield Button("Sign in", variant="primary", id="submit")

            yield Static("", id="status", classes="status-line")

        yield Footer()

    def on_mount(self) -> None:
        # Border titles rather than separate labels: same information, three
        # fewer rows, which is what lets the card fit a 24-row terminal.
        self.query_one("#email", Input).border_title = "Email"
        self.query_one("#password", Input).border_title = "Password"
        self.query_one("#confirm", Input).border_title = "Confirm password"

        self.apply_mode()

        if self.email:
            self.query_one("#password", Input).focus()
        else:
            self.query_one("#email", Input).focus()

    # --- mode ---------------------------------------------------------------

    def apply_mode(self) -> None:
        registering = self.mode == REGISTER

        self.query_one("#confirm", Input).display = registering
        self.query_one("#warning", Static).display = registering

        submit = self.query_one("#submit", Button)

        if registering:
            submit.label = "Create account"
        else:
            submit.label = "Sign in"

        self.say("")

    @on(Tabs.TabActivated, "#mode")
    def mode_changed(self, event: Tabs.TabActivated) -> None:
        if event.tab.id is None:
            return

        self.mode = event.tab.id

        self.apply_mode()

    # --- submitting ---------------------------------------------------------

    @on(Input.Submitted)
    def submitted(self) -> None:
        self.attempt()

    @on(Button.Pressed, "#submit")
    def submit_pressed(self) -> None:
        self.attempt()

    def attempt(self) -> None:
        email = self.query_one("#email", Input).value.strip()
        password = self.query_one("#password", Input).value

        if not email or not password:
            self.say("Fill in the email and the password.")
            return

        if self.mode == REGISTER:
            confirm = self.query_one("#confirm", Input).value

            if password != confirm:
                self.say("The two passwords do not match.")
                self.query_one("#confirm", Input).focus()
                return

        self.authenticate(email, password, self.mode == REGISTER)

    def say(self, message: str) -> None:
        self.query_one("#status", Static).update(message)

    def set_busy(self, busy: bool) -> None:
        self.query_one("#submit", Button).disabled = busy
        self.query_one("#mode", Tabs).disabled = busy

    @work(exclusive=True)
    async def authenticate(self, email: str, password: str, create_account: bool) -> None:
        app = cast("NapmApp", self.app)

        self.set_busy(True)
        self.say("Talking to the server…")

        client = api.Client(self.base_url)

        try:
            if create_account:
                await client.register(email, password)

            opened = await client.login(email, password)
        except errors.ApiError as failure:
            await client.close()

            self.set_busy(False)
            self.say(failure.message)
            self.query_one("#password", Input).focus()
            return

        stored = session.StoredSession(
            base_url=self.base_url,
            token=opened.token,
            expires_at=opened.expires_at,
            email=email,
        )

        session.save(stored)

        self.set_busy(False)
        self.say("")

        # The password goes to the app, which keeps it in memory for reveals
        # and never writes it anywhere.
        await app.begin_session(client, email, password)
