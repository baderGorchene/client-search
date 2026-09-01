"""Main Operations Dashboard page."""

import reflex as rx

from ui.components.execution_logs import execution_logs_console
from ui.components.kanban import kanban_board
from ui.components.map_view import leads_geo_map
from ui.components.modals import edit_draft_modal, scout_campaign_modal
from ui.components.stat_cards import stat_cards
from ui.state import AppState


def _scout_trigger_bar() -> rx.Component:
    """Render campaign discovery launcher bar with active parameter indicators."""
    return rx.card(
        rx.hstack(
            # Left Info
            rx.hstack(
                rx.icon("sparkles", size=22, color="#38bdf8"),
                rx.vstack(
                    rx.text("Autonomous Discovery Engine", size="2", weight="bold", color="white"),
                    rx.text("Multi-business keyword search, localized AI reasoning, & dynamic filtering", size="1", color="#94a3b8"),
                    spacing="0",
                ),
                align="center",
                spacing="2",
                min_width="280px",
            ),
            # Middle Configuration Badges
            rx.hstack(
                rx.badge(
                    rx.hstack(
                        rx.icon("map-pin", size=12),
                        rx.text(AppState.scout_location),
                        spacing="1",
                        align="center",
                    ),
                    color_scheme="blue",
                    variant="surface",
                    size="1",
                ),
                rx.badge(
                    rx.hstack(
                        rx.icon("languages", size=12),
                        rx.text(AppState.scout_language_label),
                        spacing="1",
                        align="center",
                    ),
                    color_scheme="purple",
                    variant="surface",
                    size="1",
                ),
                rx.badge(
                    rx.hstack(
                        rx.icon("target", size=12),
                        rx.text(f"Min Score: {AppState.scout_min_score}/10"),
                        spacing="1",
                        align="center",
                    ),
                    color_scheme="cyan",
                    variant="surface",
                    size="1",
                ),
                rx.badge(
                    rx.hstack(
                        rx.icon("tag", size=12),
                        rx.text(f"{AppState.scout_keywords_count} Niches"),
                        spacing="1",
                        align="center",
                    ),
                    color_scheme="green",
                    variant="surface",
                    size="1",
                ),
                spacing="2",
                align="center",
                wrap="wrap",
            ),
            # Right Action Buttons
            rx.hstack(
                rx.button(
                    rx.hstack(
                        rx.icon("sliders-horizontal", size=14),
                        rx.text("New Campaign"),
                        spacing="1",
                        align="center",
                    ),
                    color_scheme="blue",
                    size="2",
                    on_click=AppState.open_search_modal,
                ),
                rx.button(
                    rx.hstack(
                        rx.icon("play", size=14),
                        rx.text("Run Quick Cycle"),
                        spacing="1",
                        align="center",
                    ),
                    variant="soft",
                    color_scheme="cyan",
                    size="2",
                    on_click=AppState.trigger_scouting,
                    loading=AppState.is_scouting,
                ),
                spacing="2",
                align="center",
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


def _view_mode_switcher() -> rx.Component:
    """Render view mode selector buttons (HITL Kanban Pipeline vs. Interactive Geo Map)."""
    return rx.hstack(
        rx.hstack(
            rx.icon("layout-grid", size=16, color="#94a3b8"),
            rx.text("Pipeline View Mode:", size="2", color="#94a3b8", weight="medium"),
            spacing="1",
            align="center",
        ),
        rx.segmented_control.root(
            rx.segmented_control.item(
                rx.hstack(
                    rx.icon("kanban", size=14),
                    rx.text("HITL Kanban"),
                    spacing="1",
                    align="center",
                ),
                value="kanban",
            ),
            rx.segmented_control.item(
                rx.hstack(
                    rx.icon("map-pin", size=14),
                    rx.text("Leads Geo Map"),
                    spacing="1",
                    align="center",
                ),
                value="map",
            ),
            value=AppState.view_mode,
            on_change=lambda val: AppState.set_view_mode(val),
            size="2",
            color_scheme="blue",
        ),
        justify="between",
        align="center",
        width="100%",
        margin_top="1rem",
        margin_bottom="0.5rem",
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
        # Campaign Discovery Trigger Bar
        _scout_trigger_bar(),
        # Live Tabbed Execution Log Feeds & Stage Notifications
        execution_logs_console(),
        # Key Performance Metrics
        stat_cards(),
        # View Mode Switcher
        _view_mode_switcher(),
        # Conditional Display: Kanban Board vs. Interactive Geo Map
        rx.cond(
            AppState.view_mode == "map",
            leads_geo_map(),
            kanban_board(),
        ),
        # Edit Draft Modal Dialog
        edit_draft_modal(),
        # Custom Prospecting Campaign Modal Dialog
        scout_campaign_modal(),
        spacing="2",
        width="100%",
        align="start",
    )
