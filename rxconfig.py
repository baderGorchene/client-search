"""Reflex application configuration."""

import reflex as rx

config = rx.Config(
    app_name="ui",
    title="Client Search | Autonomous Prospecting Dashboard",
    plugins=[
        rx.plugins.RadixThemesPlugin(
            theme=rx.theme(
                appearance="dark",
                has_background=True,
                accent_color="blue",
                gray_color="slate",
            )
        )
    ],
    disable_plugins=[rx.plugins.SitemapPlugin],
)
