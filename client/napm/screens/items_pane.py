"""The passwords pane: search, the list, and the item under the cursor."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Input, Static
from textual.widgets.data_table import ColumnKey

from napm import api, errors
from napm.screens.modals import Confirm, ItemDraft, ItemForm, ShowSecrets, copy_password

if TYPE_CHECKING:
    from napm.app import NapmApp
    from napm.screens.main import MainScreen

PER_PAGE = 50

# How the two columns share whatever width the terminal gives the pane.
COLUMN_SHARES = {"name": 0.55, "username": 0.45}

HIDDEN = "•" * 20
NOT_REVEALED = "Hidden until you reveal."


class ItemsPane(Vertical):
    BINDINGS = [
        Binding("r", "reveal", "Reveal"),
        Binding("n", "new", "New"),
        Binding("e", "edit", "Edit"),
        Binding("g", "rotate", "Rotate"),
        Binding("d", "delete", "Delete"),
        Binding("slash", "search", "Search", show=False),
        Binding("c", "copy", "Copy"),
        Binding("left", "previous_page", "Previous page", show=False),
        Binding("right", "next_page", "Next page", show=False),
        Binding("ctrl+r", "reload", "Refresh", show=False),
    ]

    def __init__(self, id: str) -> None:
        super().__init__(id=id)

        self.rows: list[api.Item] = []
        self.page = 1
        self.pages = 1
        self.total = 0
        self.search_text = ""
        self.revealed: api.Secrets | None = None

    def compose(self) -> ComposeResult:
        yield Input(placeholder="Search name or username…", id="search")
        yield DataTable(id="items", cursor_type="row", zebra_stripes=True)

        with Vertical(id="detail"):
            yield Static("", id="detail-name")

            with Horizontal(id="detail-cards"):
                with Vertical(id="password-card", classes="card"):
                    yield Static("", id="detail-password")

                with Vertical(id="notes-card", classes="card"):
                    yield Static("", id="detail-notes")

    def on_mount(self) -> None:
        self.query_one("#search", Input).border_title = "Search"
        self.query_one("#password-card").border_title = "Password"
        self.query_one("#notes-card").border_title = "Notes"

        table = self.query_one("#items", DataTable)

        table.add_column("NAME", key="name")
        table.add_column("USERNAME", key="username")

        self.draw_detail()
        self.reload()

        # The table, not the search box: the pane's bindings only reach the
        # footer while the focus is somewhere they apply, and an Input eats
        # every letter they are bound to.
        self.take_focus()

    def on_resize(self) -> None:
        self.fit_columns()

    def take_focus(self) -> None:
        self.query_one("#items", DataTable).focus()

    # --- events -------------------------------------------------------------

    @on(Input.Changed, "#search")
    def search_changed(self, event: Input.Changed) -> None:
        self.search_text = event.value.strip()
        self.page = 1

        self.reload()

    @on(Input.Submitted, "#search")
    def search_submitted(self) -> None:
        self.take_focus()

    @on(DataTable.RowHighlighted, "#items")
    def row_highlighted(self) -> None:
        # A revealed password belongs to the row it came from, and nothing
        # else. Moving the cursor puts it away.
        self.revealed = None

        self.draw_detail()

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

    def action_copy(self) -> None:
        if self.revealed is None:
            self.notify("Nothing revealed to copy.", severity="warning")
            return

        self.copy(self.revealed.password)

    @work(group="clipboard")
    async def copy(self, password: str) -> None:
        await copy_password(self, password)

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

        self.tell_the_screen()

        if secrets is None:
            return

        self.revealed = secrets

        self.draw_detail()

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
        await self.announce(created)

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

        try:
            rotated = await app.client.update_item(item.id, api.ItemChanges(generate_password=True))
        except errors.ApiError as failure:
            await app.report(failure)
            return

        self.reload()
        await self.announce(rotated)

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

    # --- helpers ------------------------------------------------------------

    async def announce(self, item: api.Item) -> None:
        """A password the server just drew.

        This one gets a modal rather than the detail panel: it is not a reveal
        of something stored, it is the only moment a brand new password is on
        screen, and the panel belongs to whichever row the cursor is on — which
        after a reload is not necessarily this one.
        """
        if item.password is None:
            self.notify(f"Saved {item.name}.")
            return

        secrets = api.Secrets(password=item.password, notes=None)

        await self.app.push_screen_wait(ShowSecrets(item, secrets))

    def tell_the_screen(self) -> None:
        screen = cast("MainScreen", self.screen)

        screen.refresh_meters()

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
            table.add_row(item.name, item.username or "—")

        if page.items:
            table.move_cursor(row=min(cursor, len(page.items) - 1))

        self.fit_columns()
        self.draw_detail()
        self.tell_the_screen()

    def fit_columns(self) -> None:
        """Share the pane's width between the columns.

        A `DataTable` sizes its columns to their content, so on a wide terminal
        the rows would end halfway across and leave the stripes hanging.
        """
        table = self.query_one("#items", DataTable)

        # Two cells of padding each, plus the row cursor's own column.
        available = max(table.size.width - 6, 30)

        for key, share in COLUMN_SHARES.items():
            column = table.columns.get(ColumnKey(key))

            if column is None:
                continue

            column.width = max(int(available * share), 12)
            column.auto_width = False

        table.refresh()

    def draw_detail(self) -> None:
        item = self.selected_item()

        name = self.query_one("#detail-name", Static)
        password = self.query_one("#detail-password", Static)
        notes = self.query_one("#detail-notes", Static)

        if item is None:
            name.update(self.nothing_to_show())
            password.update("")
            notes.update("")
            return

        name.update(self.heading(item))

        if self.revealed is None:
            password.update(f"[$text-muted]{HIDDEN}   press r[/]")
            notes.update(f"[$text-muted]{NOT_REVEALED}[/]")
            return

        password.update(f"[b $accent]{self.revealed.password}[/]")

        if self.revealed.notes:
            notes.update(self.revealed.notes)
        else:
            notes.update("[$text-muted]No notes stored.[/]")

    def heading(self, item: api.Item) -> str:
        parts = []

        if item.username:
            parts.append(item.username)

        if item.url:
            parts.append(item.url)

        if not parts:
            return f"[b $accent]{item.name}[/]"

        return f"[b $accent]{item.name}[/]  [$text-muted]{' · '.join(parts)}[/]"

    def nothing_to_show(self) -> str:
        if self.search_text:
            return f"[$text-muted]Nothing matches “{self.search_text}”.[/]"

        return "[$text-muted]No items yet. Press n to add one.[/]"
