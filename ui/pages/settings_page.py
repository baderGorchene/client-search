"""System configuration and operational settings view."""

import reflex as rx

from config.settings import settings


def _config_row(label: str, value: str, badge_color: str = "blue") -> rx.Component:
    """Render a single configuration parameter item."""
    return rx.hstack(
        rx.text(label, weight="medium", color="#cbd5e1", size="2"),
        rx.badge(value, color_scheme=badge_color, size="2"),
        justify="between",
        align="center",
        padding="0.5rem 0",
        border_bottom="1px solid #1e293b",
        width="100%",
    )


def settings_page() -> rx.Component:
    """Render system settings and operational bounds page."""
    return rx.vstack(
        rx.heading("System Configuration & Infrastructure Health", size="5", weight="bold", color="white"),
        rx.text("Inspect zero-cost architecture parameters and operational safeguard limits.", size="2", color="#94a3b8"),
        rx.hstack(
            # Operational Boundaries
            rx.card(
                rx.vstack(
                    rx.hstack(
                        rx.icon("shield-check", size=20, color="#22c55e"),
                        rx.heading("Safety & Rate Limiting", size="3", weight="bold", color="white"),
                        spacing="2",
                        align="center",
                    ),
                    rx.divider(border_color="#334155"),
                    _config_row("Daily Outbox Cap", f"{settings.DAILY_EMAIL_CAP} emails/day", "green"),
                    _config_row("Min Qualification Fit Score", f"{settings.MIN_LEAD_FIT_SCORE} / 10", "yellow"),
                    _config_row("Outbox Jitter Minimum", f"{settings.EMAIL_JITTER_MIN_SECONDS}s (10m)", "blue"),
                    _config_row("Outbox Jitter Maximum", f"{settings.EMAIL_JITTER_MAX_SECONDS}s (25m)", "blue"),
                    spacing="3",
                    align="start",
                    width="100%",
                ),
                background="#0f172a",
                border="1px solid #1e293b",
                border_radius="0.75rem",
                padding="1.5rem",
                flex="1",
                min_width="320px",
            ),
            # Integrations & Infrastructure Status
            rx.card(
                rx.vstack(
                    rx.hstack(
                        rx.icon("cpu", size=20, color="#3b82f6"),
                        rx.heading("Subsystems & Routing", size="3", weight="bold", color="white"),
                        spacing="2",
                        align="center",
                    ),
                    rx.divider(border_color="#334155"),
                    _config_row("Primary Reasoning LLM", "Gemini 3.7 Flash (AI Studio)", "blue"),
                    _config_row("Fallback LLM Engine", "Llama 3.3 70B (Groq Cloud)", "purple"),
                    _config_row("Discovery Search", "DuckDuckGo (ddgs) + Overpass", "green"),
                    _config_row("Web Extraction", "Crawl4AI (Playwright Chromium)", "cyan"),
                    _config_row("Verification Gate", "Async DNS MX + SMTP Sockets", "green"),
                    _config_row("Outbox Sender", "Gmail API (OAuth2 Credentials)", "red"),
                    spacing="3",
                    align="start",
                    width="100%",
                ),
                background="#0f172a",
                border="1px solid #1e293b",
                border_radius="0.75rem",
                padding="1.5rem",
                flex="1",
                min_width="320px",
            ),
            spacing="4",
            width="100%",
            wrap="wrap",
            margin_top="1rem",
        ),
        spacing="2",
        width="100%",
        align="start",
    )
