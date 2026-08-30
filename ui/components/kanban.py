"""Kanban boards for Gate 1 (Lead Review) and Gate 2 (Draft Review)."""

from typing import Any

import reflex as rx

from ui.state import AppState


def _gate1_card(lead: dict[str, Any]) -> rx.Component:
    """Render a Gate 1 Lead Qualification Card."""
    lead_id = lead["id"].to(str)
    return rx.card(
        rx.vstack(
            # Header: Company Name & Score Badge
            rx.hstack(
                rx.vstack(
                    rx.heading(lead["company_name"], size="3", weight="bold", color="white"),
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
                rx.badge(
                    f"Score: {lead['fit_score']}/10",
                    color_scheme="green",
                    variant="solid",
                    size="2",
                ),
                justify="between",
                align="center",
                width="100%",
            ),
            rx.divider(border_color="#334155"),
            # Decision Maker Info
            rx.hstack(
                rx.icon("user", size=14, color="#94a3b8"),
                rx.text(
                    rx.cond(
                        lead["decision_maker_name"] != "",
                        lead["decision_maker_name"],
                        "Operations Lead",
                    ),
                    size="2",
                    weight="medium",
                    color="#cbd5e1",
                ),
                rx.cond(
                    lead["decision_maker_email"] != "",
                    rx.badge(lead["decision_maker_email"], color_scheme="blue", size="1"),
                ),
                spacing="2",
                align="center",
            ),
            # Operations Summary
            rx.text(
                lead["summary"],
                size="2",
                color="#94a3b8",
                line_clamp=3,
            ),
            # Angle Hook
            rx.box(
                rx.hstack(
                    rx.icon("zap", size=14, color="#f59e0b"),
                    rx.text(
                        lead["suggested_angle"],
                        size="1",
                        color="#f59e0b",
                        weight="medium",
                    ),
                    spacing="2",
                    align="center",
                ),
                background="#78350f26",
                padding="0.5rem 0.75rem",
                border_radius="0.375rem",
                width="100%",
            ),
            # Actions
            rx.hstack(
                rx.button(
                    rx.hstack(
                        rx.icon("check", size=14),
                        rx.text("Approve & Draft"),
                        spacing="1",
                        align="center",
                    ),
                    color_scheme="green",
                    size="2",
                    on_click=lambda: AppState.approve_lead(lead_id),
                    loading=AppState.active_lead_action_id == lead_id,
                    flex="1",
                ),
                rx.button(
                    rx.hstack(
                        rx.icon("x", size=14),
                        rx.text("Discard"),
                        spacing="1",
                        align="center",
                    ),
                    color_scheme="red",
                    variant="soft",
                    size="2",
                    on_click=lambda: AppState.discard_lead(lead_id),
                    loading=AppState.active_lead_action_id == lead_id,
                    flex="1",
                ),
                width="100%",
                spacing="2",
                margin_top="0.5rem",
            ),
            spacing="3",
            align="start",
            width="100%",
        ),
        background="#1e293b",
        border="1px solid #334155",
        border_radius="0.75rem",
        padding="1rem",
        width="100%",
        margin_bottom="1rem",
    )


def _gate2_card(lead: dict[str, Any]) -> rx.Component:
    """Render a Gate 2 Draft Review Card."""
    lead_id = lead["id"].to(str)
    return rx.card(
        rx.vstack(
            # Header
            rx.hstack(
                rx.vstack(
                    rx.heading(lead["company_name"], size="3", weight="bold", color="white"),
                    rx.text(lead["decision_maker_email"], size="1", color="#94a3b8"),
                    spacing="0",
                    align="start",
                ),
                rx.badge("Draft Ready", color_scheme="purple", variant="solid", size="2"),
                justify="between",
                align="center",
                width="100%",
            ),
            rx.divider(border_color="#334155"),
            # Subject Line
            rx.box(
                rx.text("Subject:", size="1", color="#94a3b8", weight="bold"),
                rx.text(lead["email_subject"], size="2", weight="medium", color="#e2e8f0"),
                background="#0f172a",
                padding="0.5rem 0.75rem",
                border_radius="0.375rem",
                width="100%",
                border="1px solid #1e293b",
            ),
            # Email Pitch Body Quote Block
            rx.box(
                rx.text(lead["email_body"], size="2", color="#cbd5e1", white_space="pre-wrap"),
                background="#0f172a",
                padding="0.75rem",
                border_left="3px solid #a855f7",
                border_radius="0 0.375rem 0.375rem 0",
                width="100%",
            ),
            # Actions: Send, Edit, Cancel
            rx.hstack(
                rx.button(
                    rx.hstack(
                        rx.icon("send", size=14),
                        rx.text("Send"),
                        spacing="1",
                        align="center",
                    ),
                    color_scheme="blue",
                    size="2",
                    on_click=lambda: AppState.send_draft(lead_id),
                    loading=AppState.active_lead_action_id == lead_id,
                    flex="2",
                ),
                rx.button(
                    rx.hstack(
                        rx.icon("pencil", size=14),
                        rx.text("Edit"),
                        spacing="1",
                        align="center",
                    ),
                    color_scheme="purple",
                    variant="soft",
                    size="2",
                    on_click=lambda: AppState.open_edit_modal(lead),
                    flex="1",
                ),
                rx.button(
                    rx.icon("trash-2", size=14),
                    color_scheme="red",
                    variant="ghost",
                    size="2",
                    on_click=lambda: AppState.cancel_draft(lead_id),
                ),
                width="100%",
                spacing="2",
                margin_top="0.5rem",
            ),
            spacing="3",
            align="start",
            width="100%",
        ),
        background="#1e293b",
        border="1px solid #334155",
        border_radius="0.75rem",
        padding="1rem",
        width="100%",
        margin_bottom="1rem",
    )


def _dispatched_card(lead: dict[str, Any]) -> rx.Component:
    """Render a Dispatched/Sent Lead Card."""
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.heading(lead["company_name"], size="3", weight="bold", color="white"),
                rx.badge(
                    lead["status"],
                    color_scheme=rx.cond(lead["status"] == "REPLIED_INTERESTED", "cyan", "green"),
                    size="2",
                ),
                justify="between",
                align="center",
                width="100%",
            ),
            rx.text(lead["decision_maker_email"], size="2", color="#94a3b8"),
            rx.text(f"Subject: {lead['email_subject']}", size="2", color="#cbd5e1"),
            rx.text(
                lead["email_body"],
                size="1",
                color="#64748b",
                line_clamp=2,
            ),
            spacing="2",
            align="start",
            width="100%",
        ),
        background="#0f172a",
        border="1px solid #1e293b",
        border_radius="0.75rem",
        padding="1rem",
        width="100%",
        margin_bottom="1rem",
    )


def kanban_board() -> rx.Component:
    """Render the 3-column reactive pipeline Kanban board."""
    return rx.hstack(
        # Column 1: Gate 1 Pending Lead Review
        rx.vstack(
            rx.hstack(
                rx.icon("user-check", size=18, color="#eab308"),
                rx.heading("Gate 1: Lead Qualification", size="4", weight="bold", color="white"),
                rx.badge(AppState.pending_gate1_leads.length().to(str), color_scheme="yellow", size="2"),
                spacing="2",
                align="center",
                margin_bottom="0.5rem",
            ),
            rx.box(
                rx.cond(
                    AppState.pending_gate1_leads.length() > 0,
                    rx.foreach(AppState.pending_gate1_leads, _gate1_card),
                    rx.center(
                        rx.vstack(
                            rx.icon("circle-check", size=32, color="#475569"),
                            rx.text("No pending Gate 1 leads", color="#64748b", size="2"),
                            spacing="2",
                            align="center",
                            padding="3rem 0",
                        ),
                        width="100%",
                    ),
                ),
                width="100%",
            ),
            background="#0b1120",
            border="1px solid #1e293b",
            border_radius="0.75rem",
            padding="1.25rem",
            flex="1",
            min_width="320px",
            height="75vh",
            overflow_y="auto",
        ),
        # Column 2: Gate 2 Pending Draft Review
        rx.vstack(
            rx.hstack(
                rx.icon("file-text", size=18, color="#a855f7"),
                rx.heading("Gate 2: Draft Review", size="4", weight="bold", color="white"),
                rx.badge(AppState.pending_gate2_leads.length().to(str), color_scheme="purple", size="2"),
                spacing="2",
                align="center",
                margin_bottom="0.5rem",
            ),
            rx.box(
                rx.cond(
                    AppState.pending_gate2_leads.length() > 0,
                    rx.foreach(AppState.pending_gate2_leads, _gate2_card),
                    rx.center(
                        rx.vstack(
                            rx.icon("inbox", size=32, color="#475569"),
                            rx.text("No pending Gate 2 drafts", color="#64748b", size="2"),
                            spacing="2",
                            align="center",
                            padding="3rem 0",
                        ),
                        width="100%",
                    ),
                ),
                width="100%",
            ),
            background="#0b1120",
            border="1px solid #1e293b",
            border_radius="0.75rem",
            padding="1.25rem",
            flex="1",
            min_width="320px",
            height="75vh",
            overflow_y="auto",
        ),
        # Column 3: Outbox Dispatched & Replied
        rx.vstack(
            rx.hstack(
                rx.icon("send", size=18, color="#22c55e"),
                rx.heading("Dispatched & Sent", size="4", weight="bold", color="white"),
                rx.badge(AppState.dispatched_leads.length().to(str), color_scheme="green", size="2"),
                spacing="2",
                align="center",
                margin_bottom="0.5rem",
            ),
            rx.box(
                rx.cond(
                    AppState.dispatched_leads.length() > 0,
                    rx.foreach(AppState.dispatched_leads, _dispatched_card),
                    rx.center(
                        rx.vstack(
                            rx.icon("send", size=32, color="#475569"),
                            rx.text("No dispatched emails yet", color="#64748b", size="2"),
                            spacing="2",
                            align="center",
                            padding="3rem 0",
                        ),
                        width="100%",
                    ),
                ),
                width="100%",
            ),
            background="#0b1120",
            border="1px solid #1e293b",
            border_radius="0.75rem",
            padding="1.25rem",
            flex="1",
            min_width="320px",
            height="75vh",
            overflow_y="auto",
        ),
        spacing="4",
        width="100%",
        align="start",
    )
