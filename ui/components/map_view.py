"""Interactive Geographic Map component for visualized B2B prospect locations."""

from typing import Any

import reflex as rx

from ui.state import AppState


def _map_stat_badge(icon_name: str, label: str, val: rx.Var[Any], color_scheme: str) -> rx.Component:
    """Render a metric badge for the map header toolbar."""
    return rx.badge(
        rx.hstack(
            rx.icon(icon_name, size=13),
            rx.text(f"{label}: ", size="1", color="#cbd5e1"),
            rx.text(val, size="1", weight="bold"),
            spacing="1",
            align="center",
        ),
        color_scheme=color_scheme,
        variant="surface",
        size="2",
        padding_x="0.625rem",
        padding_y="0.25rem",
    )


def _quick_lead_card(lead: dict[str, Any]) -> rx.Component:
    """Render an individual quick prospect card in the map carousel."""
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.text(lead["company_name"], size="1", weight="bold", color="white", max_width="150px", truncate=True),
                rx.badge(
                    f"{lead['fit_score']}/10",
                    color_scheme=rx.cond(
                        lead["fit_score"].to(int) >= 9,
                        "green",
                        rx.cond(lead["fit_score"].to(int) >= 7, "blue", "amber"),
                    ),
                    variant="solid",
                    size="1",
                ),
                justify="between",
                align="center",
                width="100%",
            ),
            rx.hstack(
                rx.icon("map-pin", size=11, color="#38bdf8"),
                rx.text(lead["location"], size="1", color="#94a3b8", truncate=True),
                spacing="1",
                align="center",
            ),
            rx.hstack(
                rx.text(lead["decision_maker_name"], size="1", color="#cbd5e1", truncate=True),
                rx.badge(lead["status"], color_scheme="purple", size="1", variant="surface"),
                justify="between",
                align="center",
                width="100%",
            ),
            spacing="1",
            align="start",
            width="100%",
        ),
        background="#0b1120",
        border="1px solid #1e293b",
        border_radius="0.5rem",
        padding="0.625rem",
        min_width="220px",
        max_width="240px",
        _hover={"border_color": "#38bdf8", "cursor": "pointer"},
    )


def leads_geo_map() -> rx.Component:
    """Render interactive dark-mode Leaflet map showing discovered prospects by location."""
    return rx.card(
        rx.vstack(
            # Map Header Toolbar
            rx.hstack(
                rx.hstack(
                    rx.icon("map-pin", size=20, color="#38bdf8"),
                    rx.vstack(
                        rx.heading("Interactive Leads Geographic Map", size="3", weight="bold", color="white"),
                        rx.text("Spatial distribution of qualified B2B prospects across target metro hubs", size="1", color="#94a3b8"),
                        spacing="0",
                    ),
                    spacing="2",
                    align="center",
                ),
                # Metric Indicators
                rx.hstack(
                    _map_stat_badge("globe", "Mapped Prospects", AppState.total_leads_count, "blue"),
                    _map_stat_badge("target", "High Fit (9-10)", AppState.high_fit_leads_count, "green"),
                    _map_stat_badge("map", "Active Location", AppState.scout_location, "purple"),
                    spacing="2",
                    align="center",
                    wrap="wrap",
                ),
                justify="between",
                align="center",
                width="100%",
                wrap="wrap",
                gap="0.75rem",
                padding_bottom="0.5rem",
                border_bottom="1px solid #1e293b",
            ),
            # Leaflet Map Canvas (Embedded in sandboxed iframe with srcdoc for reliable JS execution)
            rx.box(
                rx.el.iframe(
                    src_doc=AppState.leaflet_map_html,
                    width="100%",
                    height="500px",
                    style={
                        "border": "none",
                        "borderRadius": "0.5rem",
                        "background": "#0b1120",
                        "display": "block",
                    },
                ),
                width="100%",
                border_radius="0.5rem",
                overflow="hidden",
                border="1px solid #1e293b",
            ),
            # Quick Leads Switcher Deck
            rx.vstack(
                rx.hstack(
                    rx.icon("navigation", size=14, color="#38bdf8"),
                    rx.text("Quick Leads Switcher (Use Prev/Next buttons on map HUD or click cards below):", size="1", weight="bold", color="#cbd5e1"),
                    spacing="1",
                    align="center",
                ),
                rx.box(
                    rx.hstack(
                        rx.foreach(AppState.filtered_leads, _quick_lead_card),
                        spacing="2",
                        overflow_x="auto",
                        padding_y="0.25rem",
                        width="100%",
                    ),
                    width="100%",
                ),
                spacing="1",
                align="start",
                width="100%",
                padding_top="0.25rem",
            ),
            # Map Legend & Filter Bar
            rx.hstack(
                rx.hstack(
                    rx.text("Legend:", size="1", color="#64748b", weight="bold"),
                    rx.badge(
                        rx.hstack(
                            rx.box(width="8px", height="8px", border_radius="50%", background="#10b981"),
                            rx.text("High Priority (9-10)"),
                            spacing="1",
                            align="center",
                        ),
                        variant="soft",
                        color_scheme="green",
                        size="1",
                    ),
                    rx.badge(
                        rx.hstack(
                            rx.box(width="8px", height="8px", border_radius="50%", background="#38bdf8"),
                            rx.text("Qualified (7-8)"),
                            spacing="1",
                            align="center",
                        ),
                        variant="soft",
                        color_scheme="blue",
                        size="1",
                    ),
                    rx.badge(
                        rx.hstack(
                            rx.box(width="8px", height="8px", border_radius="50%", background="#f59e0b"),
                            rx.text("Moderate (5-6)"),
                            spacing="1",
                            align="center",
                        ),
                        variant="soft",
                        color_scheme="amber",
                        size="1",
                    ),
                    spacing="2",
                    align="center",
                    wrap="wrap",
                ),
                rx.text(
                    "Keyboard: Press [◀ / ▶] Left/Right arrows inside map to cycle between leads.",
                    size="1",
                    color="#64748b",
                    font_style="italic",
                ),
                justify="between",
                align="center",
                width="100%",
                wrap="wrap",
                padding_top="0.25rem",
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
    )
