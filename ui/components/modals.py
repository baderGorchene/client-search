"""Interactive dialog modals for draft editing and custom actions."""

import reflex as rx

from ui.state import AppState


def edit_draft_modal() -> rx.Component:
    """Render the modal dialog for refining cold email copy."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.vstack(
                # Modal Title
                rx.dialog.title(
                    rx.hstack(
                        rx.icon("pencil", size=20, color="#a855f7"),
                        rx.heading("Refine Email Pitch Copy", size="4", weight="bold"),
                        spacing="2",
                        align="center",
                    ),
                ),
                rx.dialog.description(
                    f"Editing cold outreach pitch for {AppState.selected_company_name} ({AppState.selected_recipient_email}).",
                    size="2",
                    color="#94a3b8",
                ),
                # Subject Field
                rx.vstack(
                    rx.text("Subject Line", size="2", weight="bold", color="#cbd5e1"),
                    rx.input(
                        value=AppState.editing_subject,
                        on_change=AppState.set_editing_subject,
                        placeholder="short lowercase subject...",
                        width="100%",
                    ),
                    spacing="1",
                    align="start",
                    width="100%",
                ),
                # Pitch Body Field
                rx.vstack(
                    rx.text("3-Sentence Pitch Body", size="2", weight="bold", color="#cbd5e1"),
                    rx.text_area(
                        value=AppState.editing_body,
                        on_change=AppState.set_editing_body,
                        placeholder="Hi [Name], I noticed your operations...",
                        rows="6",
                        width="100%",
                    ),
                    spacing="1",
                    align="start",
                    width="100%",
                ),
                # Action Buttons
                rx.hstack(
                    rx.button(
                        "Cancel",
                        variant="soft",
                        color_scheme="gray",
                        on_click=AppState.close_edit_modal,
                    ),
                    rx.button(
                        "Save Changes",
                        color_scheme="purple",
                        on_click=AppState.save_edited_draft,
                    ),
                    justify="end",
                    width="100%",
                    spacing="3",
                    margin_top="1rem",
                ),
                spacing="4",
                align="start",
                width="100%",
            ),
            background="#0f172a",
            border="1px solid #334155",
            border_radius="0.75rem",
            padding="1.5rem",
            max_width="550px",
        ),
        open=AppState.is_edit_modal_open,
        on_open_change=lambda _: AppState.close_edit_modal(),
    )
