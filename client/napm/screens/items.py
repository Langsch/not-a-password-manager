"""The list: search it, and act on the row under the cursor."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Input, Static
from textual.widgets.data_table import ColumnKey

from napm import api, errors, session
from napm.screens.modals import Confirm, ItemDraft, ItemForm, ShowSecrets

if TYPE_CHECKING:
    from napm.app import NapmApp

PER_PAGE = 50

# How the three columns share whatever width the terminal gives us.
COLUMN_SHARES = {"name": 0.38, "username": 0.24, "url": 0.38}


class ItemsScreen(Screen[None]):
    # Only the seven that fit a narrow footer are shown; the rest are still
    # bound, and the command palette lists them.
    BINDINGS = [
        Binding("r", "reveal", "Reveal"),
        Binding("n", "new", "New"),
        Binding("e", "edit", "Edit"),
        Binding("g", "rotate", "Rotate"),
        Binding("d", "delete", "Delete"),
        Binding("slash", "search", "Search"),
        Binding("ctrl+o", "sign_out", "Sign out"),
        Binding("left", "previous_page", "Previous page", show=False),
        Binding("right", "next_page", "Next page", show=False),
        Binding("ctrl+r", "reload", "Refresh", show=False),
        Binding("ctrl+l", "lock", "Forget the account password", show=False),
        Binding("ctrl+q", "quit", "Quit", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()

        self.rows: list[api.Item] = []
        self.page = 1
        self.pages = 1
        self.total = 0
        self.search_text = ""

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)

        with Vertical(id="body"):
            with Horizontal(id="meters"):
                yield Static(id="meter-items", classes="meter")
                yield Static(id="meter-page", classes="meter")
                yield Static(id="meter-session", classes="meter")
                yield Static(id="meter-reveal", classes="meter")

            yield Input(placeholder="Type to search name or username…", id="search")
            yield DataTable(id="items", cursor_type="row", zebra_stripes=True)
            yield Static("", id="status", classes="status-line")

        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#search", Input).border_title = "Search"

        table = self.query_one("#items", DataTable)

        table.add_column("NAME", key="name")
        table.add_column("USERNAME", key="username")
        table.add_column("URL", key="url")

        table.focus()

        self.update_meters()
        self.reload()

    def on_resize(self) -> None:
        self.fit_columns()

    # --- events -------------------------------------------------------------

    @on(Input.Changed, "#search")
    def search_changed(self, event: Input.Changed) -> None:
        self.search_text = event.value.strip()
        self.page = 1

        self.reload()

    @on(Input.Submitted, "#search")
    def search_submitted(self) -> None:
        self.query_one("#items", DataTable).focus()

    @on(DataTable.RowSelected, "#items")
    def row_selected(self) -> None:
        self.action_reveal()

    # --- actions ------------------------------------------------------------

    def action_search(self) -> None:
        self.query_one("#search", Input).focus()

    def action_previous_page(self) -> None:
        if self.page <= 1:
            return

        self.page -= 1
        self.reload()

    def action_next_page(self) -> None:
        if self.page >= self.pages:
            return

        self.page += 1
        self.reload()

    def action_lock(self) -> None:
        app = cast("NapmApp", self.app)

        app.forget_password()

        self.update_meters()

    def action_sign_out(self) -> None:
        self.sign_out()

    def action_reveal(self) -> None:
        item = self.selected_item()

        if item is None:
            return

        self.reveal(item)

    def action_new(self) -> None:
        self.create()

    def action_edit(self) -> None:
        item = self.selected_item()

        if item is None:
            return

        self.edit(item)

    def action_rotate(self) -> None:
        item = self.selected_item()

        if item is None:
            return

        self.rotate(item)

    def action_delete(self) -> None:
        item = self.selected_item()

        if item is None:
            return

        self.delete(item)

    # --- work ---------------------------------------------------------------

    @work(exclusive=True, group="list")
    async def reload(self) -> None:
        app = cast("NapmApp", self.app)

        try:
            page = await app.client.list_items(
                page=self.page,
                per_page=PER_PAGE,
                query=self.search_text,
            )
        except errors.ApiError as failure:
            await app.report(failure)
            return

        self.rows = page.items
        self.pages = max(page.pages, 1)
        self.page = page.page
        self.total = page.total

        self.draw(page)

    @work(group="action")
    async def reveal(self, item: api.Item) -> None:
        app = cast("NapmApp", self.app)

        secrets = await app.reveal(item)

        self.update_meters()

        if secrets is None:
            return

        await self.app.push_screen_wait(ShowSecrets(item, secrets))

    @work(group="action")
    async def create(self) -> None:
        app = cast("NapmApp", self.app)

        draft = await self.app.push_screen_wait(ItemForm())

        if draft is None:
            return

        password = None

        if draft.password:
            password = draft.password

        try:
            created = await app.client.create_item(
                name=draft.name,
                username=draft.username or None,
                url=draft.url or None,
                password=password,
                notes=draft.notes or None,
            )
        except errors.ApiError as failure:
            await app.report(failure)
            return

        self.reload()

        if created.password is None:
            self.notify(f"Created {created.name}.")
            return

        # It came back only because the server drew it, and this is the one
        # moment it is on screen without a reveal.
        secrets = api.Secrets(password=created.password, notes=None)

        await self.app.push_screen_wait(ShowSecrets(created, secrets))

    @work(group="action")
    async def edit(self, item: api.Item) -> None:
        app = cast("NapmApp", self.app)

        draft = await self.app.push_screen_wait(ItemForm(item))

        if draft is None:
            return

        changes = self.changes_from(draft)

        try:
            await app.client.update_item(item.id, changes)
        except errors.ApiError as failure:
            await app.report(failure)
            return

        self.notify(f"Saved {draft.name}.")
        self.reload()

    @work(group="action")
    async def rotate(self, item: api.Item) -> None:
        app = cast("NapmApp", self.app)

        question = f"Replace the stored password for {item.name} with a new one?"

        agreed = await self.app.push_screen_wait(Confirm(question, confirm_label="Rotate"))

        if not agreed:
            return

        changes = api.ItemChanges(generate_password=True)

        try:
            rotated = await app.client.update_item(item.id, changes)
        except errors.ApiError as failure:
            await app.report(failure)
            return

        self.reload()

        if rotated.password is None:
            self.notify("Rotated.")
            return

        secrets = api.Secrets(password=rotated.password, notes=None)

        await self.app.push_screen_wait(ShowSecrets(rotated, secrets))

    @work(group="action")
    async def delete(self, item: api.Item) -> None:
        app = cast("NapmApp", self.app)

        question = f"{item.name} is deleted for real. There is no trash."

        agreed = await self.app.push_screen_wait(Confirm(question))

        if not agreed:
            return

        try:
            await app.client.delete_item(item.id)
        except errors.ApiError as failure:
            await app.report(failure)
            return

        self.notify(f"Deleted {item.name}.")
        self.reload()

    @work(group="action")
    async def sign_out(self) -> None:
        app = cast("NapmApp", self.app)

        await app.sign_out()

    # --- helpers ------------------------------------------------------------

    def selected_item(self) -> api.Item | None:
        table = self.query_one("#items", DataTable)

        if not self.rows:
            return None

        cursor = table.cursor_row

        if cursor < 0 or cursor >= len(self.rows):
            return None

        return self.rows[cursor]

    def changes_from(self, draft: ItemDraft) -> api.ItemChanges:
        changes = api.ItemChanges()

        changes.name = draft.name
        changes.username = draft.username or None
        changes.url = draft.url or None

        # Empty means unchanged for both secrets: neither is in the listing, so
        # the form could not have shown what is stored.
        if draft.password:
            changes.password = draft.password

        if draft.notes:
            changes.notes = draft.notes

        return changes

    def draw(self, page: api.Page) -> None:
        table = self.query_one("#items", DataTable)

        cursor = table.cursor_row

        table.clear()

        for item in page.items:
            table.add_row(item.name, item.username or "—", item.url or "—")

        if page.items:
            table.move_cursor(row=min(cursor, len(page.items) - 1))

        self.fit_columns()
        self.update_meters()
        self.query_one("#status", Static).update(self.summary())

    def fit_columns(self) -> None:
        """Share the terminal's width between the columns.

        A `DataTable` sizes its columns to their content, so on a wide terminal
        the rows would end halfway across and leave the stripes hanging.
        """
        table = self.query_one("#items", DataTable)

        # Two cells of padding each, plus the row cursor's own column.
        available = max(table.size.width - 8, 30)

        for key, share in COLUMN_SHARES.items():
            column = table.columns.get(ColumnKey(key))

            if column is None:
                continue

            column.width = max(int(available * share), 10)
            column.auto_width = False

        table.refresh()

    def update_meters(self) -> None:
        app = cast("NapmApp", self.app)

        self.meter("#meter-items", "ITEMS", str(self.total))
        self.meter("#meter-page", "PAGE", f"{self.page} of {self.pages}")
        self.meter("#meter-session", "SESSION", self.session_left())

        if app.account_password is None:
            self.meter("#meter-reveal", "REVEAL", "[$warning]asks first[/]")
        else:
            self.meter("#meter-reveal", "REVEAL", "[$success]no prompt[/]")

    def meter(self, selector: str, label: str, value: str) -> None:
        self.query_one(selector, Static).update(f"[$text-muted]{label}[/]\n[b]{value}[/]")

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

    def summary(self) -> str:
        if self.total > 0:
            return ""

        if self.search_text:
            return f"Nothing matches “{self.search_text}”."

        return "No items yet. Press n to add one."
