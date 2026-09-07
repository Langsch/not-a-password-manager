"""The small screens that ask one thing and go away."""

from __future__ import annotations

from dataclasses import dataclass

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import Button, Input, Static

from napm.api import Item, Secrets
from napm.clipboard import to_system_clipboard

HELD_IN_MEMORY = "Held in memory until you close the app. Never written to disk."

NO_TOOL = (
    "Sent to the terminal, which may have ignored it. "
    "For a local copy install wl-clipboard, xclip or xsel."
)


async def copy_password(widget: Widget, password: str) -> None:
    """Both routes at once, and an honest answer about which one worked.

    The escape sequence goes out regardless: over ssh it is the only one that
    can reach the terminal you are sitting at.
    """
    widget.app.copy_to_clipboard(password)

    tool = await to_system_clipboard(password)

    if tool is None:
        widget.notify(NO_TOOL, severity="warning")
        return

    widget.notify(f"Password copied with {tool}.")


class AskPassword(ModalScreen[str | None]):
    """Asks for the account password, which the app then keeps in memory.

    It is asked once per run of the app, not once per reveal: the app holds it
    until it closes. Reopening asks again, because it was never written down.
    """

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, prompt: str) -> None:
        super().__init__()

        self.prompt = prompt

    def compose(self) -> ComposeResult:
        with Vertical(id="ask", classes="card"):
            yield Static(self.prompt, classes="hint")
            yield Input(password=True, id="password")

            with Horizontal(classes="buttons"):
                yield Button("Cancel", id="cancel")
                yield Button("Unlock", variant="primary", id="unlock")

    def on_mount(self) -> None:
        self.query_one("#ask").border_title = "Unlock"
        self.query_one("#password", Input).border_title = "Account password"
        self.query_one("#password", Input).focus()

    @on(Input.Submitted, "#password")
    def submitted(self) -> None:
        self.action_unlock()

    @on(Button.Pressed, "#unlock")
    def unlock_pressed(self) -> None:
        self.action_unlock()

    @on(Button.Pressed, "#cancel")
    def cancel_pressed(self) -> None:
        self.action_cancel()

    def action_unlock(self) -> None:
        typed = self.query_one("#password", Input).value

        if not typed:
            return

        self.dismiss(typed)

    def action_cancel(self) -> None:
        self.dismiss(None)


class ShowSecrets(ModalScreen[None]):
    """What a reveal came back with."""

    BINDINGS = [
        ("escape", "close", "Close"),
        ("c", "copy", "Copy password"),
    ]

    def __init__(self, item: Item, secrets: Secrets) -> None:
        super().__init__()

        self.item = item
        self.secrets = secrets

    def compose(self) -> ComposeResult:
        with Vertical(id="secrets", classes="card"):
            yield Static(self.item.name, classes="card-heading")
            yield Static(self.where(), classes="hint")

            yield Static(self.secrets.password, id="password", classes="secret")

            if self.secrets.notes:
                with VerticalScroll(id="notes"):
                    yield Static(self.secrets.notes)

            with Horizontal(classes="buttons"):
                yield Button("Close", id="close")
                yield Button("Copy password", variant="primary", id="copy")

    def on_mount(self) -> None:
        self.query_one("#secrets").border_title = "Reveal"
        self.query_one("#password").border_title = "Password"

        if self.secrets.notes:
            self.query_one("#notes").border_title = "Notes"

        self.query_one("#copy", Button).focus()

    def where(self) -> str:
        parts = []

        if self.item.username:
            parts.append(self.item.username)

        if self.item.url:
            parts.append(self.item.url)

        if not parts:
            return "No username or address stored."

        return " · ".join(parts)

    @on(Button.Pressed, "#copy")
    def copy_pressed(self) -> None:
        self.action_copy()

    @on(Button.Pressed, "#close")
    def close_pressed(self) -> None:
        self.action_close()

    def action_copy(self) -> None:
        self.copy()

    @work(group="clipboard")
    async def copy(self) -> None:
        await copy_password(self, self.secrets.password)

    def action_close(self) -> None:
        self.dismiss(None)


@dataclass
class ItemDraft:
    """What the form collected. An empty password means something different on
    a create than on an edit, so the screen that opened the form decides."""

    name: str
    username: str
    url: str
    password: str
    notes: str


class ItemForm(ModalScreen[ItemDraft | None]):
    """Create or edit. Secrets are never prefilled — the form is not a reveal."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, item: Item | None = None) -> None:
        super().__init__()

        self.item = item

        if item is None:
            self.heading = "New item"
            self.password_hint = "Leave the password empty and the server generates one."
        else:
            self.heading = "Edit item"
            # Notes are encrypted, so the list never carries them and the form
            # cannot prefill them. Sending an empty string would erase what is
            # stored, so an empty box has to mean "unchanged".
            self.password_hint = "Password and notes: empty means unchanged."

    def compose(self) -> ComposeResult:
        name = ""
        username = ""
        url = ""

        if self.item is not None:
            name = self.item.name
            username = self.item.username or ""
            url = self.item.url or ""

        with Vertical(id="form", classes="card"):
            with VerticalScroll(id="form-fields"):
                yield Input(value=name, id="name")
                yield Input(value=username, id="username")
                yield Input(value=url, id="url")
                yield Input(password=True, id="password")
                yield Input(id="notes")

            yield Static(self.password_hint, classes="hint")

            with Horizontal(classes="buttons"):
                yield Button("Cancel", id="cancel")
                yield Button("Save", variant="primary", id="save")

    def on_mount(self) -> None:
        self.query_one("#form").border_title = self.heading

        self.query_one("#name", Input).border_title = "Name"
        self.query_one("#username", Input).border_title = "Username"
        self.query_one("#url", Input).border_title = "URL"
        self.query_one("#password", Input).border_title = "Password"
        self.query_one("#notes", Input).border_title = "Notes"

        self.query_one("#name", Input).focus()

    @on(Input.Submitted)
    def submitted(self) -> None:
        self.action_save()

    @on(Button.Pressed, "#save")
    def save_pressed(self) -> None:
        self.action_save()

    @on(Button.Pressed, "#cancel")
    def cancel_pressed(self) -> None:
        self.action_cancel()

    def action_save(self) -> None:
        name = self.query_one("#name", Input).value.strip()

        if not name:
            self.notify("A name is required.", severity="warning")
            self.query_one("#name", Input).focus()
            return

        draft = ItemDraft(
            name=name,
            username=self.query_one("#username", Input).value.strip(),
            url=self.query_one("#url", Input).value.strip(),
            password=self.query_one("#password", Input).value,
            notes=self.query_one("#notes", Input).value,
        )

        self.dismiss(draft)

    def action_cancel(self) -> None:
        self.dismiss(None)


class Confirm(ModalScreen[bool]):
    """A yes or no, for the things that do not come back."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, question: str, confirm_label: str = "Delete") -> None:
        super().__init__()

        self.question = question
        self.confirm_label = confirm_label

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-card", classes="card"):
            yield Static(self.question, classes="card-heading")

            with Horizontal(classes="buttons"):
                yield Button("Cancel", id="cancel")
                yield Button(self.confirm_label, variant="error", id="confirm")

    def on_mount(self) -> None:
        self.query_one("#confirm-card").border_title = "Are you sure?"
        self.query_one("#cancel", Button).focus()

    @on(Button.Pressed, "#confirm")
    def confirm_pressed(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#cancel")
    def cancel_pressed(self) -> None:
        self.action_cancel()

    def action_cancel(self) -> None:
        self.dismiss(False)
