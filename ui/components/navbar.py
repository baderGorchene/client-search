"""Navigation header bar component."""

import reflex as rx

from ui.state import AppState


def navbar() -> rx.Component:
    """Render top navigation header."""
    return rx.box(
        rx.hstack(
            rx.hstack(
                rx.image(src="/logo.jpg", width="34px", height="34px", border_radius="0.5rem", border="1px solid #334155"),
                rx.vstack(
                    rx.heading("Client Search", size="4", weight="bold", color="white"),
                    rx.text("Autonomous B2B Scouting & HITL Outreach", size="1", color="#94a3b8"),
                    spacing="0",
                ),
                align="center",
                spacing="3",
            ),
            rx.hstack(
                rx.button(
                    rx.hstack(
                        rx.icon("kanban", size=16),
                        rx.text("Kanban Board"),
                        spacing="2",
                        align="center",
                    ),
                    variant=rx.cond(AppState.active_tab == "kanban", "solid", "ghost"),
                    color_scheme="blue",
                    on_click=lambda: AppState.set_active_tab("kanban"),
                    size="2",
                ),
                rx.button(
                    rx.hstack(
                        rx.icon("table", size=16),
                        rx.text("Leads Table"),
                        spacing="2",
                        align="center",
                    ),
                    variant=rx.cond(AppState.active_tab == "table", "solid", "ghost"),
                    color_scheme="blue",
                    on_click=lambda: AppState.set_active_tab("table"),
                    size="2",
                ),
                rx.button(
                    rx.hstack(
                        rx.icon("radar", size=16),
                        rx.text("Scout Engine"),
                        spacing="2",
                        align="center",
                    ),
                    variant=rx.cond(AppState.active_tab == "scout", "solid", "ghost"),
                    color_scheme="blue",
                    on_click=lambda: AppState.set_active_tab("scout"),
                    size="2",
                ),
                rx.button(
                    rx.hstack(
                        rx.icon("settings", size=16),
                        rx.text("Settings"),
                        spacing="2",
                        align="center",
                    ),
                    variant=rx.cond(AppState.active_tab == "settings", "solid", "ghost"),
                    color_scheme="blue",
                    on_click=lambda: AppState.set_active_tab("settings"),
                    size="2",
                ),
                rx.button(
                    rx.hstack(
                        rx.icon("refresh-cw", size=16),
                        rx.text("Refresh"),
                        spacing="2",
                        align="center",
                    ),
                    variant="outline",
                    color_scheme="gray",
                    on_click=AppState.fetch_leads,
                    loading=AppState.is_loading,
                    size="2",
                ),
                align="center",
                spacing="3",
            ),
            justify="between",
            align="center",
            width="100%",
            max_width="1400px",
            margin="0 auto",
        ),
        background="rgba(15, 23, 42, 0.95)",
        backdrop_filter="blur(8px)",
        border_bottom="1px solid #1e293b",
        padding="1rem 2rem",
        position="sticky",
        top="0",
        z_index="50",
        width="100%",
    )
