"""Tabular lead explorer page."""

from typing import Any

import reflex as rx

from ui.state import AppState


def _status_color(status: rx.Var[str]) -> rx.Var[str]:
    """Map lead status to badge color scheme."""
    return rx.match(
        status,
        ("PENDING_LEAD_REVIEW", "yellow"),
        ("DRAFT_GENERATED", "purple"),
        ("EMAIL_SENT", "green"),
        ("REPLIED_INTERESTED", "cyan"),
        ("REPLIED_NOT_INTERESTED", "gray"),
        ("LEAD_REJECTED", "red"),
        ("DRAFT_REJECTED", "red"),
        "gray",
    )


def _lead_row(lead: dict[str, Any]) -> rx.Component:
    """Render a single table row for a lead record."""
    lead_id = lead["id"].to(str)
    return rx.table.row(
        rx.table.cell(
            rx.vstack(
                rx.text(lead["company_name"], weight="bold", color="white"),
                rx.link(
                    lead["website_url"],
                    href=lead["website_url"],
                    is_external=True,
                    size="1",
                    color="#60a5fa",
                ),
                spacing="0",
                align="start",
            ),
        ),
        rx.table.cell(
            rx.badge(
                f"{lead['fit_score']}/10",
                color_scheme="green",
                size="2",
            ),
        ),
        rx.table.cell(
            rx.vstack(
                rx.text(lead["decision_maker_name"], weight="medium", color="#cbd5e1"),
                rx.text(lead["decision_maker_email"], size="1", color="#94a3b8"),
                spacing="0",
                align="start",
            ),
        ),
        rx.table.cell(
            rx.badge(
                lead["status"],
                color_scheme=_status_color(lead["status"]),
                size="2",
            ),
        ),
        rx.table.cell(
            rx.text(
                lead["suggested_angle"],
                size="1",
                color="#cbd5e1",
                line_clamp=2,
            ),
        ),
        rx.table.cell(
            rx.hstack(
                rx.cond(
                    lead["status"] == "PENDING_LEAD_REVIEW",
                    rx.button(
                        rx.icon("check", size=14),
                        color_scheme="green",
                        size="1",
                        on_click=lambda: AppState.approve_lead(lead_id),
                    ),
                ),
                rx.cond(
                    lead["status"] == "DRAFT_GENERATED",
                    rx.hstack(
                        rx.button(
                            rx.icon("send", size=14),
                            color_scheme="blue",
                            size="1",
                            on_click=lambda: AppState.send_draft(lead_id),
                        ),
                        rx.button(
                            rx.icon("pencil", size=14),
                            color_scheme="purple",
                            variant="soft",
                            size="1",
                            on_click=lambda: AppState.open_edit_modal(lead),
                        ),
                        spacing="1",
                    ),
                ),
                rx.cond(
                    lead["status"] == "PENDING_LEAD_REVIEW",
                    rx.button(
                        rx.icon("x", size=14),
                        color_scheme="red",
                        variant="soft",
                        size="1",
                        on_click=lambda: AppState.discard_lead(lead_id),
                    ),
                ),
                spacing="2",
                align="center",
            ),
        ),
    )


def leads_page() -> rx.Component:
    """Render the full leads table view."""
    return rx.vstack(
        # Search & Filter Header
        rx.card(
            rx.hstack(
                rx.hstack(
                    rx.input(
                        placeholder="Search company, URL, email, or summary...",
                        value=AppState.search_query,
                        on_change=AppState.set_search_query,
                        width="350px",
                        size="2",
                    ),
                    rx.select(
                        [
                            "ALL",
                            "PENDING_LEAD_REVIEW",
                            "DRAFT_GENERATED",
                            "EMAIL_SENT",
                            "REPLIED_INTERESTED",
                            "LEAD_REJECTED",
                            "DRAFT_REJECTED",
                        ],
                        value=AppState.selected_status_filter,
                        on_change=AppState.set_selected_status_filter,
                        size="2",
                    ),
                    spacing="3",
                    align="center",
                ),
                rx.text(
                    f"Showing {AppState.filtered_leads.length()} records",
                    size="2",
                    color="#94a3b8",
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
            width="100%",
            margin_bottom="1.5rem",
        ),
        # Leads Table
        rx.box(
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("Company & Website"),
                        rx.table.column_header_cell("Fit Score"),
                        rx.table.column_header_cell("Contact"),
                        rx.table.column_header_cell("Status"),
                        rx.table.column_header_cell("Suggested Angle"),
                        rx.table.column_header_cell("Actions"),
                    ),
                ),
                rx.table.body(
                    rx.foreach(AppState.filtered_leads, _lead_row),
                ),
                variant="surface",
                size="2",
                width="100%",
            ),
            background="#0f172a",
            border="1px solid #1e293b",
            border_radius="0.75rem",
            overflow="hidden",
            width="100%",
        ),
        spacing="2",
        width="100%",
        align="start",
    )
