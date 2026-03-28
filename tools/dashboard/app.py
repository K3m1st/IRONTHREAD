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
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Footer, Header, Static
from textual import work

from data import BoxState, resolve_db_path, load_box_state


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

        # Flags
        content.append("  Flags:  ", style="white")
        if t.user_flag:
            content.append("U", style="bold yellow")
            content.append(" user  ", style="dim")
        else:
            content.append(".        ", style="dim")
        if t.root_flag:
            content.append("R", style="bold green")
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

        title = self.query_one("#findings-container .section-title", Static)
        title.update(f"FINDINGS ({len(state.findings)})")

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

        title = self.query_one("#creds-container .section-title", Static)
        title.update(f"CREDENTIALS ({len(state.credentials)})")

        for c in state.credentials:
            verified = Text("Yes", style="green") if c.verified else Text("No", style="dim")
            table.add_row(
                Text(c.cred_type, style="white"),
                Text(c.username or "—", style="bold white"),
                Text(c.source[:55], style="dim white"),
                verified,
                agent_text(c.found_by),
            )

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
