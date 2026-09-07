"""The screen you spend the session in: a sidebar, and a pane beside it."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import ContentSwitcher, Footer, Header, Label, ListItem, ListView, Static

from napm import session
from napm.art import WORDMARK
from napm.screens.account_pane import AccountPane
from napm.screens.items_pane import ItemsPane

if TYPE_CHECKING:
    from napm.app import NapmApp

PASSWORDS = "passwords"
ACCOUNT = "account"


class MainScreen(Screen[None]):
    BINDINGS = [
        Binding("ctrl+o", "sign_out", "Sign out"),
        Binding("ctrl+n", "navigate", "Menu", show=False),
        Binding("ctrl+l", "lock", "Forget the account password", show=False),
        Binding("ctrl+q", "quit", "Quit", show=False),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)

        with Horizontal(id="body"):
            with Vertical(id="sidebar"):
                yield Static(WORDMARK, id="art")
                yield Label("NAVIGATION", classes="side-label")

                yield ListView(
                    ListItem(Label("Passwords"), id=f"nav-{PASSWORDS}"),
                    ListItem(Label("Account"), id=f"nav-{ACCOUNT}"),
                    id="nav",
                )

                with Vertical(id="meters"):
                    yield Static(id="meter-items", classes="meter")
                    yield Static(id="meter-session", classes="meter")
                    yield Static(id="meter-reveal", classes="meter")

            with ContentSwitcher(initial=PASSWORDS, id="main"):
                yield ItemsPane(id=PASSWORDS)
                yield AccountPane(id=ACCOUNT)

        yield Footer()

    def on_mount(self) -> None:
        self.refresh_meters()

    @on(ListView.Highlighted, "#nav")
    def navigated(self, event: ListView.Highlighted) -> None:
        if event.item is None or event.item.id is None:
            return

        chosen = event.item.id.removeprefix("nav-")

        self.query_one("#main", ContentSwitcher).current = chosen

    @on(ListView.Selected, "#nav")
    def chosen(self) -> None:
        # Enter on the menu hands the keyboard to the pane, where the bindings
        # in the footer actually apply.
        self.active_pane().take_focus()

    # --- actions ------------------------------------------------------------

    def action_navigate(self) -> None:
        self.query_one("#nav", ListView).focus()

    def action_lock(self) -> None:
        app = cast("NapmApp", self.app)

        app.forget_password()

        self.refresh_meters()

    def action_sign_out(self) -> None:
        self.sign_out()

    @work(group="action")
    async def sign_out(self) -> None:
        app = cast("NapmApp", self.app)

        await app.sign_out()

    # --- the sidebar's readouts ---------------------------------------------

    def active_pane(self) -> ItemsPane | AccountPane:
        current = self.query_one("#main", ContentSwitcher).current

        if current == ACCOUNT:
            return self.query_one(AccountPane)

        return self.query_one(ItemsPane)

    def refresh_meters(self) -> None:
        app = cast("NapmApp", self.app)

        total = self.query_one(ItemsPane).total

        self.meter("#meter-items", "ITEMS", str(total))
        self.meter("#meter-session", "SESSION", self.session_left())

        if app.account_password is None:
            self.meter("#meter-reveal", "REVEAL", "[$warning]asks first[/]")
        else:
            self.meter("#meter-reveal", "REVEAL", "[$success]no prompt[/]")

    def meter(self, selector: str, label: str, value: str) -> None:
        self.query_one(selector, Static).update(f"[$text-muted]{label}[/]  [b]{value}[/]")

    def session_left(self) -> str:
        stored = session.load()

        if stored is None:
            return "—"

        left = stored.expires_at - datetime.now(UTC)
        hours = int(left.total_seconds() // 3600)

        if hours < 1:
            return "under an hour"

        if hours < 48:
            return f"{hours} h"

        return f"{hours // 24} days"
