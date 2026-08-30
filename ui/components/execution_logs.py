"""Live execution logs and terminal console component."""

import reflex as rx

from ui.state import AppState


def _log_line_item(line: rx.Var[str]) -> rx.Component:
    """Render an individual execution step log line."""
    return rx.hstack(
        rx.text(
            line,
            size="2",
            color=rx.match(
                line.contains("❌"),
                (True, "#f87171"),
                rx.match(
                    line.contains("✅"),
                    (True, "#4ade80"),
                    rx.match(
                        line.contains("Step"),
                        (True, "#60a5fa"),
                        "#cbd5e1",
                    ),
                ),
            ),
            font_family="ui-monospace, monospace",
        ),
        spacing="1",
        align="center",
        width="100%",
    )


def execution_logs_console() -> rx.Component:
    """Render the real-time execution steps terminal console."""
    return rx.cond(
        (AppState.execution_logs.length() > 0) | AppState.is_scouting,
        rx.card(
            rx.vstack(
                # Console Header
                rx.hstack(
                    rx.hstack(
                        rx.icon("terminal", size=18, color="#38bdf8"),
                        rx.heading("Real-Time Execution Console", size="3", weight="bold", color="white"),
                        rx.cond(
                            AppState.is_scouting,
                            rx.hstack(
                                rx.spinner(size="1"),
                                rx.badge("EXECUTING CYCLE", color_scheme="blue", variant="solid", size="2"),
                                spacing="2",
                                align="center",
                            ),
                            rx.badge("CYCLE COMPLETED", color_scheme="green", variant="soft", size="2"),
                        ),
                        spacing="2",
                        align="center",
                    ),
                    rx.button(
                        rx.hstack(
                            rx.icon("trash-2", size=13),
                            rx.text("Clear"),
                            spacing="1",
                            align="center",
                        ),
                        variant="ghost",
                        color_scheme="gray",
                        size="1",
                        on_click=AppState.clear_execution_logs,
                    ),
                    justify="between",
                    align="center",
                    width="100%",
                ),
                # Current Step Description Banner (if executing)
                rx.cond(
                    AppState.is_scouting & (AppState.current_step_description != ""),
                    rx.box(
                        rx.hstack(
                            rx.spinner(size="1"),
                            rx.text(
                                AppState.current_step_description,
                                size="2",
                                color="#93c5fd",
                                weight="medium",
                            ),
                            spacing="2",
                            align="center",
                        ),
                        background="#1e3a8a33",
                        border="1px solid #1e40af",
                        border_radius="0.375rem",
                        padding="0.5rem 0.75rem",
                        width="100%",
                    ),
                ),
                # Log Stream Terminal Box
                rx.box(
                    rx.vstack(
                        rx.foreach(AppState.execution_logs, _log_line_item),
                        spacing="1",
                        align="start",
                        width="100%",
                    ),
                    background="#020617",
                    border="1px solid #1e293b",
                    border_radius="0.5rem",
                    padding="0.875rem",
                    max_height="220px",
                    overflow_y="auto",
                    width="100%",
                ),
                spacing="3",
                align="start",
                width="100%",
            ),
            background="#0f172a",
            border="1px solid #1e293b",
            border_radius="0.75rem",
            padding="1.25rem",
            margin_bottom="1.5rem",
            width="100%",
        ),
    )
