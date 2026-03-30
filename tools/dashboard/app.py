#!/usr/bin/env python3
# ruff: noqa: E501
"""IRONTHREAD Operator Dashboard — single-box TUI.

Usage:
    python tools/dashboard/app.py <BoxName>
    python tools/dashboard/app.py Snapped
"""

import sys
from pathlib import Path

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import DataTable, Footer, Header, Static
from textual import work

from data import BoxState, Credential, Finding, resolve_db_path, load_box_state


# ---------------------------------------------------------------------------
# Color helpers
# ---------------------------------------------------------------------------

AGENT_STYLES = {
    "ORACLE": "bold yellow",
    "ELLIOT": "bold cyan",
    "NOIRE":  "bold magenta",
}

SEVERITY_STYLES = {
    "critical": "bold red",
    "high":     "red",
    "medium":   "yellow",
    "low":      "dim green",
    "info":     "dim blue",
}

STATUS_STYLES = {
    "validated":   "green",
    "in_progress": "yellow",
    "open":        "white",
    "exhausted":   "dim strike",
}

ACCESS_STYLES = {
    "root":   "bold green",
    "system": "bold green",
    "user":   "bold yellow",
    "none":   "dim white",
}


def styled(value: str | None, style_map: dict, default: str = "white") -> Text:
    """Return a Rich Text with style looked up from a map."""
    val = value or ""
    return Text(val, style=style_map.get(val.lower(), default))


def agent_text(agent: str) -> Text:
    return Text(agent, style=AGENT_STYLES.get(agent, "white"))


def severity_text(sev: str | None) -> Text:
    if not sev:
        return Text("—", style="dim")
    return Text(sev.upper(), style=SEVERITY_STYLES.get(sev.lower(), "white"))


def flag_display(user_flag: str | None, root_flag: str | None) -> Text:
    parts = Text()
    if user_flag:
        parts.append("U", style="bold yellow")
    else:
        parts.append(".", style="dim")
    parts.append("  ")
    if root_flag:
        parts.append("R", style="bold green")
    else:
        parts.append(".", style="dim")
    return parts


# ---------------------------------------------------------------------------
# Widgets
# ---------------------------------------------------------------------------

class TargetPanel(Static):
    """Displays target info as styled text."""
    pass


class ServicesPanel(Static):
    """Displays services as styled text."""
    pass


# ---------------------------------------------------------------------------
# Detail modals
# ---------------------------------------------------------------------------

class DetailModal(ModalScreen):
    """Base modal for displaying record details."""

    CSS = """
    DetailModal {
        align: center middle;
    }

    #detail-dialog {
        width: 80%;
        max-width: 100;
        height: auto;
        max-height: 80%;
        border: tall $accent;
        background: $surface;
        padding: 2 3;
    }

    #detail-title {
        text-style: bold;
        margin-bottom: 1;
    }

    #detail-meta {
        margin-bottom: 1;
    }

    #detail-body {
        margin-top: 1;
        margin-bottom: 1;
    }

    #detail-evidence-label {
        text-style: bold;
        color: $text-muted;
        margin-top: 1;
    }

    #detail-evidence {
        margin-bottom: 1;
        color: $text-muted;
    }

    #detail-hint {
        text-style: dim;
        margin-top: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("q", "dismiss", "Close"),
    ]


class FindingDetailModal(DetailModal):
    """Modal showing full finding details."""

    def __init__(self, finding: Finding) -> None:
        super().__init__()
        self.finding = finding

    def compose(self) -> ComposeResult:
        f = self.finding
        with VerticalScroll(id="detail-dialog"):
            # Title
            title_text = Text()
            title_text.append("FINDING", style="bold")
            yield Static(title_text, id="detail-title")

            # Metadata row
            meta = Text()
            meta.append("  Severity: ", style="white")
            meta.append(
                (f.severity or "—").upper(),
                style=SEVERITY_STYLES.get((f.severity or "").lower(), "white"),
            )
            meta.append("     Status: ", style="white")
            meta.append(
                f.status,
                style=STATUS_STYLES.get(f.status, "white"),
            )
            meta.append("\n")
            meta.append("  Category: ", style="white")
            meta.append(f.category, style="white")
            meta.append("     Agent:  ", style="white")
            meta.append(f.found_by, style=AGENT_STYLES.get(f.found_by, "white"))
            yield Static(meta, id="detail-meta")

            # Title line
            yield Static(Text(f"  {f.title}", style="bold white"))

            # Detail body
            if f.detail:
                detail_label = Text()
                detail_label.append("\n  DETAIL", style="bold dim")
                yield Static(detail_label)

                detail_body = Text()
                for line in f.detail.split("\n"):
                    detail_body.append(f"  {line}\n", style="white")
                yield Static(detail_body, id="detail-body")

            # Evidence
            if f.evidence:
                ev_label = Text()
                ev_label.append("  EVIDENCE", style="bold dim")
                yield Static(ev_label, id="detail-evidence-label")

                ev_body = Text()
                for line in f.evidence.split("\n"):
                    ev_body.append(f"  {line}\n", style="dim cyan")
                yield Static(ev_body, id="detail-evidence")

            yield Static(Text("  [Esc] Close", style="dim"), id="detail-hint")


class CredentialDetailModal(DetailModal):
    """Modal showing full credential details."""

    def __init__(self, cred: Credential) -> None:
        super().__init__()
        self.cred = cred

    def compose(self) -> ComposeResult:
        c = self.cred
        with VerticalScroll(id="detail-dialog"):
            title_text = Text()
            title_text.append("CREDENTIAL", style="bold")
            yield Static(title_text, id="detail-title")

            meta = Text()
            meta.append("  Type: ", style="white")
            meta.append(c.cred_type, style="bold white")
            meta.append("       Username: ", style="white")
            meta.append(c.username or "—", style="bold white")
            meta.append("\n")
            meta.append("  Verified: ", style="white")
            if c.verified:
                meta.append("Yes", style="bold green")
            else:
                meta.append("No", style="dim")
            meta.append("     Agent: ", style="white")
            meta.append(c.found_by, style=AGENT_STYLES.get(c.found_by, "white"))
            yield Static(meta, id="detail-meta")

            # Source
            src = Text()
            src.append("\n  SOURCE\n", style="bold dim")
            src.append(f"  {c.source}\n", style="white")
            yield Static(src)

            # Context
            if c.context:
                ctx = Text()
                ctx.append("\n  CONTEXT\n", style="bold dim")
                ctx.append(f"  {c.context}\n", style="white")
                yield Static(ctx)

            yield Static(Text("  [Esc] Close", style="dim"), id="detail-hint")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

class OperatorDashboard(App):
    """IRONTHREAD single-box operator dashboard."""

    TITLE = "IRONTHREAD"

    CSS = """
    Screen {
        background: $surface;
    }

    #top-row {
        height: auto;
        min-height: 10;
        margin: 1 2;
    }

    #target-panel {
        width: 1fr;
        min-width: 36;
        border: tall $accent;
        padding: 1 2;
        margin: 0 1 0 0;
    }

    #services-panel {
        width: 1fr;
        min-width: 36;
        border: tall $accent;
        padding: 1 2;
        margin: 0 0 0 1;
    }

    #findings-container {
        height: 1fr;
        min-height: 10;
        margin: 1 2;
        border: tall $accent;
        padding: 1 1;
    }

    #creds-container {
        height: 1fr;
        min-height: 8;
        margin: 1 2;
        border: tall $accent;
        padding: 1 1;
    }

    #actions-container {
        height: 1fr;
        min-height: 10;
        margin: 1 2;
        border: tall $accent;
        padding: 1 1;
    }

    .section-title {
        text-style: bold;
        color: $text;
        margin-bottom: 1;
    }

    DataTable {
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("p", "toggle_pause", "Pause"),
    ]

    def __init__(self, box_name: str, db_path: Path):
        super().__init__()
        self.box_name = box_name
        self.db_path = db_path
        self._paused = False
        self._state: BoxState | None = None
        self._findings_index: list[Finding] = []
        self._creds_index: list[Credential] = []

    def compose(self) -> ComposeResult:
        yield Header()

        with Horizontal(id="top-row"):
            yield TargetPanel(id="target-panel")
            yield ServicesPanel(id="services-panel")

        with Vertical(id="findings-container"):
            yield Static("FINDINGS", classes="section-title")
            yield DataTable(id="findings-table")

        with Vertical(id="creds-container"):
            yield Static("CREDENTIALS", classes="section-title")
            yield DataTable(id="creds-table")

        with Vertical(id="actions-container"):
            yield Static("RECENT ACTIONS", classes="section-title")
            yield DataTable(id="actions-table")

        yield Footer()

    def on_mount(self) -> None:
        self.sub_title = f"{self.box_name}"

        # Set up findings table
        ft = self.query_one("#findings-table", DataTable)
        ft.add_columns("Severity", "Category", "Title", "Status", "Agent")
        ft.cursor_type = "row"

        # Set up credentials table
        ct = self.query_one("#creds-table", DataTable)
        ct.add_columns("Type", "Username", "Source", "Verified", "Agent")
        ct.cursor_type = "row"

        # Set up actions table
        at = self.query_one("#actions-table", DataTable)
        at.add_columns("Time", "Agent", "Phase", "Action")
        at.cursor_type = "row"

        # Initial load + auto-refresh
        self._do_refresh()
        self.set_interval(10, self._auto_refresh)

    def _auto_refresh(self) -> None:
        if not self._paused:
            self._do_refresh()

    def _do_refresh(self) -> None:
        self._load_data()

    @work(thread=True, exclusive=True)
    def _load_data(self) -> None:
        try:
            state = load_box_state(self.db_path)
            self.call_from_thread(self._update_ui, state)
        except Exception as e:
            self.call_from_thread(
                self.notify, f"DB error: {e}", severity="error"
            )

    def _update_ui(self, state: BoxState) -> None:
        self._state = state
        self._update_target_panel(state)
        self._update_services_panel(state)
        self._update_findings(state)
        self._update_credentials(state)
        self._update_actions(state)

        # Update subtitle with phase
        phase = state.target.phase or "unknown"
        pause_indicator = "  [PAUSED]" if self._paused else ""
        self.sub_title = f"{self.box_name}  //  Phase: {phase}{pause_indicator}"

    def _update_target_panel(self, state: BoxState) -> None:
        t = state.target
        panel = self.query_one("#target-panel", TargetPanel)

        content = Text()
        content.append("TARGET\n\n", style="bold")

        # IP + hostname
        display_name = f"{t.ip}"
        if t.hostname:
            display_name += f"  ({t.hostname})"
        content.append(f"  {display_name}\n", style="bold white")

        # OS
        if t.os:
            content.append(f"  OS: {t.os}\n", style="white")

        content.append("\n")

        # Access level
        access_style = ACCESS_STYLES.get(t.access_level or "none", "dim white")
        content.append("  Access: ", style="white")
        content.append(t.access_level or "none", style=access_style)
        if t.access_user:
            content.append(f"  ({t.access_user})", style="white")
        content.append("\n")

        # Method
        if t.access_method:
            content.append(f"  Method: {t.access_method}\n", style="dim white")

        content.append("\n")

        # Flags — check state table first, fall back to access_level
        has_user = bool(t.user_flag) or t.access_level in ("user", "root", "system")
        has_root = bool(t.root_flag) or t.access_level in ("root", "system")

        content.append("  Flags:  ", style="white")
        if has_user:
            content.append("U", style="bold yellow")
            if t.user_flag:
                content.append(f" {t.user_flag[:8]}..  ", style="dim")
            else:
                content.append(" user  ", style="dim")
        else:
            content.append(".        ", style="dim")
        if has_root:
            content.append("R", style="bold green")
            if t.root_flag:
                content.append(f" {t.root_flag[:8]}..", style="dim")
            else:
                content.append(" root", style="dim")
        else:
            content.append(".", style="dim")

        panel.update(content)

    def _update_services_panel(self, state: BoxState) -> None:
        panel = self.query_one("#services-panel", ServicesPanel)

        content = Text()
        content.append(f"SERVICES ({len(state.services)})\n\n", style="bold")

        if not state.services:
            content.append("  No services discovered yet.", style="dim")
        else:
            for svc in state.services:
                # Port/proto
                content.append(f"  {svc.port}", style="bold cyan")
                content.append(f"/{svc.protocol}", style="dim")
                content.append("  ")

                # Service name
                content.append(f"{svc.service or '?'}", style="white")
                content.append("  ")

                # Version
                if svc.version:
                    content.append(f"{svc.version}", style="dim white")
                content.append("\n\n")

        panel.update(content)

    def _update_findings(self, state: BoxState) -> None:
        table = self.query_one("#findings-table", DataTable)
        table.clear()
        self._findings_index = list(state.findings)

        title = self.query_one("#findings-container .section-title", Static)
        title.update(f"FINDINGS ({len(state.findings)})  [Enter] detail")

        for f in state.findings:
            table.add_row(
                severity_text(f.severity),
                Text(f.category, style="white"),
                Text(f.title[:70], style="white"),
                styled(f.status, STATUS_STYLES),
                agent_text(f.found_by),
            )

    def _update_credentials(self, state: BoxState) -> None:
        table = self.query_one("#creds-table", DataTable)
        table.clear()
        self._creds_index = list(state.credentials)

        title = self.query_one("#creds-container .section-title", Static)
        title.update(f"CREDENTIALS ({len(state.credentials)})  [Enter] detail")

        for c in state.credentials:
            verified = Text("Yes", style="green") if c.verified else Text("No", style="dim")
            table.add_row(
                Text(c.cred_type, style="white"),
                Text(c.username or "—", style="bold white"),
                Text(c.source[:55], style="dim white"),
                verified,
                agent_text(c.found_by),
            )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Open detail modal when Enter is pressed on a findings or creds row."""
        table_id = event.data_table.id
        row_idx = event.cursor_row

        if table_id == "findings-table" and row_idx < len(self._findings_index):
            self.push_screen(FindingDetailModal(self._findings_index[row_idx]))
        elif table_id == "creds-table" and row_idx < len(self._creds_index):
            self.push_screen(CredentialDetailModal(self._creds_index[row_idx]))

    def _update_actions(self, state: BoxState) -> None:
        table = self.query_one("#actions-table", DataTable)
        table.clear()

        for a in state.actions:
            # Format timestamp: "03-26 04:23"
            ts = a.created_at
            if len(ts) >= 16:
                ts = ts[5:16].replace("T", " ")

            table.add_row(
                Text(ts, style="dim"),
                agent_text(a.agent),
                Text(a.phase or "—", style="dim"),
                Text(a.action[:80], style="white"),
            )

    # --- Actions ---

    def action_refresh(self) -> None:
        self._do_refresh()
        self.notify("Refreshed", severity="information")

    def action_toggle_pause(self) -> None:
        self._paused = not self._paused
        status = "PAUSED" if self._paused else "LIVE"
        self.notify(f"Auto-refresh: {status}", severity="information")
        # Update subtitle immediately
        if self._state:
            phase = self._state.target.phase or "unknown"
            pause_indicator = "  [PAUSED]" if self._paused else ""
            self.sub_title = f"{self.box_name}  //  Phase: {phase}{pause_indicator}"


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python app.py <BoxName>")
        print("Example: python app.py Snapped")
        sys.exit(1)

    box_name = sys.argv[1]
    db_path = resolve_db_path(box_name)

    if not db_path.exists():
        print(f"Error: No memoria.db found for '{box_name}'")
        print(f"Expected: {db_path}")
        sys.exit(1)

    app = OperatorDashboard(box_name, db_path)
    app.run()


if __name__ == "__main__":
    main()
