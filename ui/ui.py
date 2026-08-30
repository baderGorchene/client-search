"""Main Reflex application entrypoint and view assembly."""

import reflex as rx

from ui.components.navbar import navbar
from ui.pages.dashboard import dashboard_page
from ui.pages.leads import leads_page
from ui.pages.settings_page import settings_page
from ui.state import AppState


def index() -> rx.Component:
    """Render the primary single-page application layout."""
    return rx.box(
        # Navigation Bar Header
        navbar(),
        # Main Content Container
        rx.box(
            rx.match(
                AppState.active_tab,
                ("kanban", dashboard_page()),
                ("table", leads_page()),
                ("scout", dashboard_page()),
                ("settings", settings_page()),
                dashboard_page(),
            ),
            width="100%",
            max_width="1400px",
            margin="0 auto",
            padding="2rem",
        ),
        background="#030712",
        min_height="100vh",
        color="#f8fafc",
        font_family="system-ui, -apple-system, sans-serif",
    )


# App Initialization
app = rx.App()
app.add_page(
    index,
    route="/",
    title="Client Search | Autonomous Prospecting Dashboard",
    on_load=AppState.fetch_leads,
)
