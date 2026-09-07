"""The account pane: who you are signed in as, and the password that guards it."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Input, Static

from napm import errors

if TYPE_CHECKING:
    from napm.app import NapmApp
    from napm.screens.main import MainScreen

DROPS_EVERY_DEVICE = "Ends every session, this one included. There is no password reset."


class AccountPane(VerticalScroll):
    def __init__(self, id: str) -> None:
        super().__init__(id=id)

    def compose(self) -> ComposeResult:
        with Vertical(id="account-card", classes="card"):
            yield Static("", id="signed-in-as")
            yield Static(DROPS_EVERY_DEVICE, classes="hint")

            yield Input(password=True, id="current-password")
            yield Input(password=True, id="new-password")
            yield Input(password=True, id="confirm-password")

            with Horizontal(classes="buttons"):
                yield Button("Change password", variant="primary", id="change")

            yield Static("", id="account-status", classes="status-line")

        with Vertical(id="session-card", classes="card"):
            yield Static(
                "The account password is held in memory while this app is open. "
                "Forgetting it makes the next reveal ask again.",
                classes="hint",
            )

            with Horizontal(classes="buttons"):
                yield Button("Forget the password", id="forget")
                yield Button("Sign out", variant="error", id="sign-out")

    def on_mount(self) -> None:
        self.query_one("#account-card").border_title = "Account password"
        self.query_one("#session-card").border_title = "This session"

        self.query_one("#current-password", Input).border_title = "Current password"
        self.query_one("#new-password", Input).border_title = "New password"
        self.query_one("#confirm-password", Input).border_title = "Confirm new password"

        self.show_who()

    def take_focus(self) -> None:
        self.query_one("#current-password", Input).focus()

    def show_who(self) -> None:
        app = cast("NapmApp", self.app)

        if app.email:
            self.query_one("#signed-in-as", Static).update(f"Signed in as [b]{app.email}[/]")
        else:
            self.query_one("#signed-in-as", Static).update("Signed in.")

    def say(self, message: str) -> None:
        self.query_one("#account-status", Static).update(message)

    # --- events -------------------------------------------------------------

    @on(Button.Pressed, "#change")
    def change_pressed(self) -> None:
        self.attempt()

    @on(Input.Submitted)
    def submitted(self) -> None:
        self.attempt()

    @on(Button.Pressed, "#forget")
    def forget_pressed(self) -> None:
        app = cast("NapmApp", self.app)
        screen = cast("MainScreen", self.screen)

        app.forget_password()
        screen.refresh_meters()

    @on(Button.Pressed, "#sign-out")
    def sign_out_pressed(self) -> None:
        self.sign_out()

    # --- work ---------------------------------------------------------------

    def attempt(self) -> None:
        current = self.query_one("#current-password", Input).value
        fresh = self.query_one("#new-password", Input).value
        confirm = self.query_one("#confirm-password", Input).value

        if not current or not fresh:
            self.say("Fill in the current password and the new one.")
            return

        if fresh != confirm:
            self.say("The two new passwords do not match.")
            self.query_one("#confirm-password", Input).focus()
            return

        self.change(current, fresh)

    @work(exclusive=True, group="account")
    async def change(self, current: str, fresh: str) -> None:
        app = cast("NapmApp", self.app)

        self.query_one("#change", Button).disabled = True
        self.say("Talking to the server…")

        try:
            await app.client.change_password(current, fresh)
        except errors.ApiError as failure:
            self.query_one("#change", Button).disabled = False
            self.say(failure.message)
            return

        # Every session died with the change, this one included.
        await app.password_changed()

    @work(group="action")
    async def sign_out(self) -> None:
        app = cast("NapmApp", self.app)

        await app.sign_out()
