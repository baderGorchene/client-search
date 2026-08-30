"""Main Operations Dashboard page."""

import reflex as rx

from ui.components.kanban import kanban_board
from ui.components.modals import edit_draft_modal
from ui.components.stat_cards import stat_cards
from ui.state import AppState


def _scout_trigger_bar() -> rx.Component:
    """Render quick prospect discovery trigger bar."""
    return rx.card(
        rx.hstack(
            rx.hstack(
                rx.icon("sparkles", size=20, color="#3b82f6"),
                rx.vstack(
                    rx.text("Run Prospecting Cycle", size="2", weight="bold", color="white"),
                    rx.text("Trigger zero-cost DuckDuckGo & Overpass discovery", size="1", color="#94a3b8"),
                    spacing="0",
                ),
                align="center",
                spacing="2",
                min_width="260px",
            ),
            rx.hstack(
                rx.select(
                    ["logistics", "real_estate", "boutique_agencies", "ecommerce"],
                    value=AppState.scout_vertical,
                    on_change=AppState.set_scout_vertical,
                    size="2",
                ),
                rx.input(
                    value=AppState.scout_location,
                    on_change=AppState.set_scout_location,
                    placeholder="Location (e.g. Chicago, IL)",
                    size="2",
                    width="220px",
                ),
                rx.button(
                    rx.hstack(
                        rx.icon("search", size=14),
                        rx.text("Start Scouting"),
                        spacing="1",
                        align="center",
                    ),
                    color_scheme="blue",
                    size="2",
                    on_click=AppState.trigger_scouting,
                    loading=AppState.is_scouting,
                ),
                spacing="3",
                align="center",
                wrap="wrap",
            ),
            justify="between",
            align="center",
            width="100%",
            wrap="wrap",
            gap="1rem",
        ),
        background="#0f172a",
        border="1px solid #1e293b",
        border_radius="0.75rem",
        padding="1rem 1.25rem",
        margin_bottom="1.5rem",
        width="100%",
    )


def dashboard_page() -> rx.Component:
    """Render the dashboard overview view."""
    return rx.vstack(
        # Alert / Status Message Notification Banner
        rx.cond(
            AppState.status_message != "",
            rx.callout(
                AppState.status_message,
                icon="info",
                color_scheme="blue",
                size="2",
                margin_bottom="1rem",
                width="100%",
            ),
        ),
        # Quick Scout Runner Bar
        _scout_trigger_bar(),
        # Key Performance Metrics
        stat_cards(),
        # Dual-Gate Mobile HITL Kanban
        kanban_board(),
        # Edit Modal Dialog
        edit_draft_modal(),
        spacing="2",
        width="100%",
        align="start",
    )
