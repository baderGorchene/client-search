"""Statistical metric cards and KPI badges component."""

import reflex as rx

from ui.state import AppState


def _metric_card(
    title: str,
    value: rx.Var[int | str],
    icon_name: str,
    accent_color: str,
    badge_text: str = "",
) -> rx.Component:
    """Render an individual KPI statistic card."""
    return rx.card(
        rx.hstack(
            rx.vstack(
                rx.text(title, size="2", color="#94a3b8", weight="medium"),
                rx.heading(value, size="6", weight="bold", color="white"),
                rx.cond(
                    badge_text != "",
                    rx.badge(badge_text, color_scheme="blue", variant="surface", size="1"),
                ),
                align="start",
                spacing="1",
            ),
            rx.box(
                rx.icon(icon_name, size=24, color=accent_color),
                background=f"{accent_color}1a",
                padding="0.75rem",
                border_radius="0.5rem",
            ),
            justify="between",
            align="center",
            width="100%",
        ),
        background="#0f172a",
        border="1px solid #1e293b",
        border_radius="0.75rem",
        padding="1.25rem",
        flex="1",
        min_width="220px",
    )


def stat_cards() -> rx.Component:
    """Render the dashboard summary metric row."""
    return rx.box(
        rx.hstack(
            _metric_card(
                title="Total Prospects",
                value=AppState.total_leads_count,
                icon_name="database",
                accent_color="#3b82f6",
            ),
            _metric_card(
                title="Gate 1 (Lead Review)",
                value=AppState.status_counts["pending_gate1"],
                icon_name="user-check",
                accent_color="#eab308",
                badge_text="Needs Qualification",
            ),
            _metric_card(
                title="Gate 2 (Draft Review)",
                value=AppState.status_counts["pending_gate2"],
                icon_name="file-text",
                accent_color="#a855f7",
                badge_text="Ready for Approval",
            ),
            _metric_card(
                title="Emails Sent",
                value=AppState.status_counts["sent"],
                icon_name="send",
                accent_color="#22c55e",
            ),
            _metric_card(
                title="Interested Replies",
                value=AppState.status_counts["interested"],
                icon_name="message-square",
                accent_color="#06b6d4",
            ),
            wrap="wrap",
            spacing="4",
            width="100%",
        ),
        width="100%",
        margin_bottom="1.5rem",
    )
