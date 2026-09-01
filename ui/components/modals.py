"""Interactive dialog modals for draft editing, custom prospecting search, and dynamic filtering constraints."""

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


def _keyword_tag(kw: rx.Var[str]) -> rx.Component:
    """Render an individual target keyword tag chip with a delete action."""
    return rx.badge(
        rx.hstack(
            rx.icon("tag", size=12, color="#38bdf8"),
            rx.text(kw, size="1", weight="medium", color="white"),
            rx.icon(
                "x",
                size=12,
                color="#94a3b8",
                on_click=AppState.remove_scout_keyword(kw),
                cursor="pointer",
                _hover={"color": "#ef4444"},
            ),
            spacing="1",
            align="center",
        ),
        color_scheme="blue",
        variant="surface",
        size="2",
        padding_x="0.5rem",
        padding_y="0.25rem",
        border_radius="9999px",
    )


def _bottleneck_tag(b: rx.Var[str]) -> rx.Component:
    """Render an individual target bottleneck tag chip with a delete action."""
    return rx.badge(
        rx.hstack(
            rx.icon("circle-alert", size=12, color="#c084fc"),
            rx.text(b, size="1", color="white"),
            rx.icon(
                "x",
                size=12,
                color="#94a3b8",
                on_click=AppState.remove_target_bottleneck(b),
                cursor="pointer",
                _hover={"color": "#ef4444"},
            ),
            spacing="1",
            align="center",
        ),
        color_scheme="purple",
        variant="surface",
        size="2",
        padding_x="0.5rem",
        padding_y="0.25rem",
        border_radius="9999px",
    )


def _domain_tag(domain: rx.Var[str]) -> rx.Component:
    """Render an individual excluded domain tag chip with a delete action."""
    return rx.badge(
        rx.hstack(
            rx.icon("shield-alert", size=11, color="#f87171"),
            rx.text(domain, size="1", color="#e2e8f0"),
            rx.icon(
                "x",
                size=11,
                color="#94a3b8",
                on_click=AppState.remove_excluded_domain(domain),
                cursor="pointer",
                _hover={"color": "#ef4444"},
            ),
            spacing="1",
            align="center",
        ),
        color_scheme="gray",
        variant="surface",
        size="1",
        padding_x="0.375rem",
        padding_y="0.15rem",
        border_radius="9999px",
    )


def scout_campaign_modal() -> rx.Component:
    """Render the organized, structured prospecting campaign configuration modal."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.vstack(
                # Modal Header
                rx.dialog.title(
                    rx.hstack(
                        rx.icon("sparkles", size=20, color="#38bdf8"),
                        rx.heading("Configure Prospecting Campaign", size="4", weight="bold", color="white"),
                        spacing="2",
                        align="center",
                    ),
                ),
                rx.dialog.description(
                    "Set up target business niches, localized geographic parameters, and AI qualification constraints.",
                    size="2",
                    color="#94a3b8",
                ),

                # -------------------------------------------------------------
                # Step 1: Target Businesses / Niches (Tags + Quick Add)
                # -------------------------------------------------------------
                rx.box(
                    rx.vstack(
                        rx.hstack(
                            rx.icon("search", size=16, color="#38bdf8"),
                            rx.text("1. Target Business Niches & Verticals", size="2", weight="bold", color="white"),
                            rx.badge(
                                f"{AppState.scout_keywords_count} Active",
                                color_scheme="blue",
                                variant="surface",
                                size="1",
                            ),
                            spacing="2",
                            align="center",
                        ),
                        # Active Keyword Tags
                        rx.box(
                            rx.hstack(
                                rx.foreach(AppState.scout_keywords_list, _keyword_tag),
                                spacing="2",
                                wrap="wrap",
                                width="100%",
                            ),
                            width="100%",
                            min_height="32px",
                        ),
                        # Input & Add Button
                        rx.hstack(
                            rx.input(
                                value=AppState.new_keyword_input,
                                on_change=AppState.set_new_keyword_input,
                                placeholder="Type a business niche (e.g. Solar Contractors, Logistics Forwarders)...",
                                width="100%",
                                size="2",
                            ),
                            rx.button(
                                rx.hstack(
                                    rx.icon("plus", size=14),
                                    rx.text("Add Niche"),
                                    spacing="1",
                                    align="center",
                                ),
                                size="2",
                                color_scheme="blue",
                                on_click=AppState.add_scout_keyword,
                            ),
                            spacing="2",
                            width="100%",
                        ),
                        # Quick Preset Chips
                        rx.hstack(
                            rx.text("Quick Presets:", size="1", color="#64748b", weight="medium"),
                            rx.button(
                                "+ Freight & Logistics",
                                size="1",
                                variant="surface",
                                color_scheme="gray",
                                on_click=lambda: AppState.add_keyword_preset("Freight Forwarders & 3PL"),
                            ),
                            rx.button(
                                "+ Solar Contractors",
                                size="1",
                                variant="surface",
                                color_scheme="gray",
                                on_click=lambda: AppState.add_keyword_preset("Solar & Roofing Contractors"),
                            ),
                            rx.button(
                                "+ Property Managers",
                                size="1",
                                variant="surface",
                                color_scheme="gray",
                                on_click=lambda: AppState.add_keyword_preset("Commercial Property Management"),
                            ),
                            rx.button(
                                "+ Digital Agencies",
                                size="1",
                                variant="surface",
                                color_scheme="gray",
                                on_click=lambda: AppState.add_keyword_preset("Boutique Digital Agencies"),
                            ),
                            spacing="2",
                            align="center",
                            wrap="wrap",
                        ),
                        spacing="2",
                        align="start",
                        width="100%",
                    ),
                    background="#0b1120",
                    border="1px solid #1e293b",
                    border_radius="0.5rem",
                    padding="0.875rem",
                    width="100%",
                ),

                # -------------------------------------------------------------
                # Step 2: Location & Language
                # -------------------------------------------------------------
                rx.grid(
                    rx.vstack(
                        rx.hstack(
                            rx.icon("map-pin", size=14, color="#38bdf8"),
                            rx.text("Target Metro Area / City", size="1", weight="bold", color="#cbd5e1"),
                            spacing="1",
                            align="center",
                        ),
                        rx.input(
                            value=AppState.scout_location,
                            on_change=AppState.set_scout_location,
                            placeholder="e.g. Chicago, IL or Paris, France",
                            width="100%",
                            size="2",
                        ),
                        spacing="1",
                        align="start",
                        width="100%",
                    ),
                    rx.vstack(
                        rx.hstack(
                            rx.icon("languages", size=14, color="#a855f7"),
                            rx.text("Search & AI Language", size="1", weight="bold", color="#cbd5e1"),
                            spacing="1",
                            align="center",
                        ),
                        rx.select.root(
                            rx.select.trigger(placeholder="Select language...", size="2"),
                            rx.select.content(
                                rx.select.item("🇺🇸 English (US / Global)", value="en"),
                                rx.select.item("🇫🇷 French (Français)", value="fr"),
                                rx.select.item("🇸🇦 Arabic (العربية)", value="ar"),
                            ),
                            value=AppState.scout_language,
                            on_change=AppState.set_scout_language,
                        ),
                        spacing="1",
                        align="start",
                        width="100%",
                    ),
                    columns="2",
                    spacing="3",
                    width="100%",
                ),

                # -------------------------------------------------------------
                # Step 3: Core Productized Offer & Pitch
                # -------------------------------------------------------------
                rx.box(
                    rx.vstack(
                        rx.hstack(
                            rx.icon("sparkles", size=16, color="#38bdf8"),
                            rx.text("2. Productized Service Offer / Pitch", size="2", weight="bold", color="white"),
                            spacing="1",
                            align="center",
                        ),
                        rx.select.root(
                            rx.select.trigger(placeholder="Choose automation offer...", size="2"),
                            rx.select.content(
                                rx.select.item("📄 Invoice, Waybill & Paperwork OCR Pipelines", value="ocr"),
                                rx.select.item("🤖 Real-Time Inbound Booking & Triage Agents", value="triage"),
                                rx.select.item("📊 Custom Ops Dashboards & ERP Synchronization", value="dashboard"),
                                rx.select.item("⚡ Custom Specific Automation Offer", value="custom"),
                            ),
                            value=AppState.scout_offer_preset,
                            on_change=AppState.set_scout_offer_preset,
                        ),
                        rx.input(
                            value=AppState.scout_custom_offer_notes,
                            on_change=AppState.set_scout_custom_offer_notes,
                            placeholder="Optional: Specific focus details (e.g. Focus on TMS waybill ingestion)...",
                            width="100%",
                            size="2",
                        ),
                        spacing="2",
                        align="start",
                        width="100%",
                    ),
                    background="#0b1120",
                    border="1px solid #1e293b",
                    border_radius="0.5rem",
                    padding="0.875rem",
                    width="100%",
                ),

                # -------------------------------------------------------------
                # Step 4: Ideal Qualification Bottlenecks to Detect
                # -------------------------------------------------------------
                rx.box(
                    rx.vstack(
                        rx.hstack(
                            rx.icon("circle-check", size=16, color="#10b981"),
                            rx.text("3. Target Operational Bottlenecks", size="2", weight="bold", color="white"),
                            spacing="1",
                            align="center",
                        ),
                        # Active Bottlenecks Tags
                        rx.box(
                            rx.hstack(
                                rx.foreach(AppState.scout_target_bottlenecks, _bottleneck_tag),
                                spacing="2",
                                wrap="wrap",
                                width="100%",
                            ),
                            width="100%",
                        ),
                        # Add Bottleneck Input
                        rx.hstack(
                            rx.input(
                                value=AppState.new_bottleneck_input,
                                on_change=AppState.set_new_bottleneck_input,
                                placeholder="Add specific bottleneck to detect (e.g. Manual customs manifest entry)...",
                                width="100%",
                                size="2",
                            ),
                            rx.button(
                                rx.hstack(
                                    rx.icon("plus", size=14),
                                    rx.text("Add"),
                                    spacing="1",
                                    align="center",
                                ),
                                size="2",
                                color_scheme="purple",
                                on_click=AppState.add_target_bottleneck,
                            ),
                            spacing="2",
                            width="100%",
                        ),
                        # Quick Bottleneck Presets
                        rx.hstack(
                            rx.text("Suggestions:", size="1", color="#64748b", weight="medium"),
                            rx.button(
                                "+ High Paperwork Volume",
                                size="1",
                                variant="surface",
                                color_scheme="gray",
                                on_click=lambda: AppState.add_bottleneck_preset("High daily volume of paperwork & waybills"),
                            ),
                            rx.button(
                                "+ Manual ERP Entry",
                                size="1",
                                variant="surface",
                                color_scheme="gray",
                                on_click=lambda: AppState.add_bottleneck_preset("Manual ERP & spreadsheet data entry"),
                            ),
                            rx.button(
                                "+ Repetitive Bookings",
                                size="1",
                                variant="surface",
                                color_scheme="gray",
                                on_click=lambda: AppState.add_bottleneck_preset("Repetitive booking and customer inquiry triage"),
                            ),
                            spacing="2",
                            align="center",
                            wrap="wrap",
                        ),
                        spacing="2",
                        align="start",
                        width="100%",
                    ),
                    background="#0b1120",
                    border="1px solid #1e293b",
                    border_radius="0.5rem",
                    padding="0.875rem",
                    width="100%",
                ),

                # -------------------------------------------------------------
                # Step 5: Disqualification Rules (Anti-Profile Checkboxes)
                # -------------------------------------------------------------
                rx.box(
                    rx.vstack(
                        rx.hstack(
                            rx.icon("ban", size=16, color="#ef4444"),
                            rx.text("4. Disqualification Rules (Anti-Profile)", size="2", weight="bold", color="white"),
                            spacing="1",
                            align="center",
                        ),
                        rx.grid(
                            rx.hstack(
                                rx.switch(
                                    checked=AppState.scout_exclude_freelancers,
                                    on_change=AppState.set_scout_exclude_freelancers,
                                ),
                                rx.text("Exclude Solo Freelancers & Micro-teams", size="1", color="#cbd5e1"),
                                spacing="2",
                                align="center",
                            ),
                            rx.hstack(
                                rx.switch(
                                    checked=AppState.scout_exclude_local_kiosks,
                                    on_change=AppState.set_scout_exclude_local_kiosks,
                                ),
                                rx.text("Exclude Retail Shops & Restaurants", size="1", color="#cbd5e1"),
                                spacing="2",
                                align="center",
                            ),
                            rx.hstack(
                                rx.switch(
                                    checked=AppState.scout_exclude_no_digital,
                                    on_change=AppState.set_scout_exclude_no_digital,
                                ),
                                rx.text("Exclude Non-Digital Workflows", size="1", color="#cbd5e1"),
                                spacing="2",
                                align="center",
                            ),
                            columns="2",
                            spacing="3",
                            width="100%",
                        ),
                        rx.input(
                            value=AppState.scout_custom_disqualification,
                            on_change=AppState.set_scout_custom_disqualification,
                            placeholder="Optional custom rule (e.g. Exclude companies with < 3 employees)...",
                            width="100%",
                            size="2",
                        ),
                        spacing="2",
                        align="start",
                        width="100%",
                    ),
                    background="#0b1120",
                    border="1px solid #1e293b",
                    border_radius="0.5rem",
                    padding="0.875rem",
                    width="100%",
                ),

                # -------------------------------------------------------------
                # Step 6: Thresholds, Blocklist & Dispatch Settings
                # -------------------------------------------------------------
                rx.box(
                    rx.vstack(
                        rx.hstack(
                            rx.icon("sliders-horizontal", size=16, color="#38bdf8"),
                            rx.text("5. Filters, Blocklist & Dispatch", size="2", weight="bold", color="white"),
                            spacing="1",
                            align="center",
                        ),
                        rx.grid(
                            rx.vstack(
                                rx.hstack(
                                    rx.text("Min Fit Score:", size="1", color="#94a3b8"),
                                    rx.badge(f"{AppState.scout_min_score}/10", color_scheme="blue", variant="solid", size="1"),
                                    spacing="1",
                                    align="center",
                                ),
                                rx.input(
                                    value=AppState.scout_min_score,
                                    on_change=AppState.set_scout_min_score,
                                    type="number",
                                    min="1",
                                    max="10",
                                    size="2",
                                    width="100%",
                                ),
                                spacing="1",
                                align="start",
                                width="100%",
                            ),
                            rx.vstack(
                                rx.hstack(
                                    rx.text("Limit per Niche:", size="1", color="#94a3b8"),
                                    rx.badge(AppState.scout_limit, color_scheme="cyan", variant="surface", size="1"),
                                    spacing="1",
                                    align="center",
                                ),
                                rx.input(
                                    value=AppState.scout_limit,
                                    on_change=AppState.set_scout_limit,
                                    type="number",
                                    min="1",
                                    max="50",
                                    size="2",
                                    width="100%",
                                ),
                                spacing="1",
                                align="start",
                                width="100%",
                            ),
                            columns="2",
                            spacing="3",
                            width="100%",
                        ),
                        # Excluded Domains Tags
                        rx.vstack(
                            rx.text("Excluded Domains Blocklist:", size="1", color="#94a3b8", weight="medium"),
                            rx.box(
                                rx.hstack(
                                    rx.foreach(AppState.scout_excluded_domains_list, _domain_tag),
                                    spacing="1",
                                    wrap="wrap",
                                    width="100%",
                                ),
                                width="100%",
                            ),
                            rx.hstack(
                                rx.input(
                                    value=AppState.new_excluded_domain_input,
                                    on_change=AppState.set_new_excluded_domain_input,
                                    placeholder="Add domain to blocklist (e.g. yelp.com)...",
                                    size="2",
                                    width="100%",
                                ),
                                rx.button(
                                    rx.hstack(
                                        rx.icon("plus", size=13),
                                        rx.text("Block"),
                                        spacing="1",
                                        align="center",
                                    ),
                                    size="2",
                                    variant="soft",
                                    color_scheme="gray",
                                    on_click=AppState.add_excluded_domain,
                                ),
                                spacing="2",
                                width="100%",
                            ),
                            spacing="1",
                            align="start",
                            width="100%",
                        ),
                        # Toggles
                        rx.hstack(
                            rx.hstack(
                                rx.switch(
                                    checked=AppState.scout_verify_strict,
                                    on_change=AppState.set_scout_verify_strict,
                                ),
                                rx.text("Strict SMTP Mailbox Verification", size="1", color="#cbd5e1"),
                                spacing="2",
                                align="center",
                            ),
                            rx.hstack(
                                rx.switch(
                                    checked=AppState.scout_push_telegram,
                                    on_change=AppState.set_scout_push_telegram,
                                ),
                                rx.text("Push to Telegram Gate 1", size="1", color="#cbd5e1"),
                                spacing="2",
                                align="center",
                            ),
                            spacing="4",
                            align="center",
                            width="100%",
                            padding_top="0.25rem",
                        ),
                        spacing="2",
                        align="start",
                        width="100%",
                    ),
                    background="#0b1120",
                    border="1px solid #1e293b",
                    border_radius="0.5rem",
                    padding="0.875rem",
                    width="100%",
                ),

                # -------------------------------------------------------------
                # Modal Footer Actions
                # -------------------------------------------------------------
                rx.hstack(
                    rx.button(
                        "Cancel",
                        variant="soft",
                        color_scheme="gray",
                        on_click=AppState.close_search_modal,
                    ),
                    rx.button(
                        rx.hstack(
                            rx.icon("rocket", size=15),
                            rx.text("Launch Scouting Pipeline"),
                            spacing="1",
                            align="center",
                        ),
                        color_scheme="blue",
                        size="2",
                        on_click=AppState.trigger_scouting,
                        loading=AppState.is_scouting,
                    ),
                    justify="end",
                    width="100%",
                    spacing="3",
                    margin_top="0.5rem",
                ),
                spacing="3",
                align="start",
                width="100%",
            ),
            background="#0f172a",
            border="1px solid #334155",
            border_radius="0.75rem",
            padding="1.5rem",
            max_width="660px",
            max_height="90vh",
            overflow_y="auto",
        ),
        open=AppState.is_search_modal_open,
        on_open_change=AppState.set_search_modal_open,
    )
