"""Live execution log feeds and tabbed pipeline monitor with ephemeral notifications."""

import reflex as rx

from ui.state import AppState, PipelineNode


def _ephemeral_log_item(line: rx.Var[str]) -> rx.Component:
    """Render an individual log entry as a styled ephemeral notification card."""
    border_color = rx.match(
        line.contains("❌") | line.contains("failed") | line.contains("Disqualified"),
        (True, "#ef4444"),
        rx.match(
            line.contains("✅") | line.contains("COMPLETE") | line.contains("resolved") | line.contains("Saving"),
            (True, "#10b981"),
            rx.match(
                line.contains("🤖") | line.contains("Gemini") | line.contains("Evaluation"),
                (True, "#a855f7"),
                rx.match(
                    line.contains("🔍") | line.contains("Searching") | line.contains("Discovered"),
                    (True, "#38bdf8"),
                    rx.match(
                        line.contains("⚠️") | line.contains("⏭️") | line.contains("Skipping"),
                        (True, "#f59e0b"),
                        "#3b82f6",
                    ),
                ),
            ),
        ),
    )

    icon_name = rx.match(
        line.contains("❌"),
        (True, "circle-alert"),
        rx.match(
            line.contains("✅"),
            (True, "circle-check"),
            rx.match(
                line.contains("🤖"),
                (True, "bot"),
                rx.match(
                    line.contains("🔍"),
                    (True, "search"),
                    rx.match(
                        line.contains("🧹"),
                        (True, "filter"),
                        rx.match(
                            line.contains("🌐"),
                            (True, "globe"),
                            rx.match(
                                line.contains("✉️"),
                                (True, "mail"),
                                rx.match(
                                    line.contains("📱"),
                                    (True, "send"),
                                    "terminal",
                                ),
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )

    return rx.box(
        rx.hstack(
            rx.icon(icon_name, size=15, color=border_color),
            rx.text(
                line,
                size="1",
                color="#f1f5f9",
                font_family="ui-monospace, monospace",
                word_break="break-word",
            ),
            spacing="2",
            align="center",
            width="100%",
        ),
        background="rgba(15, 23, 42, 0.8)",
        border_left=f"3px solid {border_color}",
        border_top="1px solid rgba(51, 65, 85, 0.4)",
        border_right="1px solid rgba(51, 65, 85, 0.4)",
        border_bottom="1px solid rgba(51, 65, 85, 0.4)",
        border_radius="0.375rem",
        padding="0.5rem 0.75rem",
        margin_bottom="0.375rem",
        width="100%",
        box_shadow="0 1px 3px rgba(0, 0, 0, 0.3)",
    )


def _step_tab_trigger(node: rx.Var[PipelineNode], tab_value: str) -> rx.Component:
    """Render a tab trigger with live status icon and completion badge."""
    return rx.tabs.trigger(
        rx.hstack(
            rx.cond(
                node.status == "completed",
                rx.icon("circle-check", color="#22c55e", size=14),
                rx.cond(
                    node.status == "active",
                    rx.spinner(size="1", color="blue"),
                    rx.cond(
                        node.status == "error",
                        rx.icon("circle-alert", color="#ef4444", size=14),
                        rx.icon("clock", color="#64748b", size=14),
                    ),
                ),
            ),
            rx.text(node.title, size="1", weight="medium"),
            rx.cond(
                node.status == "completed",
                rx.badge(node.completed_time, color_scheme="green", variant="soft", size="1", font_size="9px"),
                rx.cond(
                    node.status == "active",
                    rx.badge("RUNNING", color_scheme="blue", variant="solid", size="1", font_size="9px"),
                    rx.text(""),
                ),
            ),
            spacing="1",
            align="center",
        ),
        value=tab_value,
    )


def _step_tab_content(node: rx.Var[PipelineNode], tab_value: str) -> rx.Component:
    """Render the log stream and stage metadata for a specific pipeline step tab."""
    return rx.tabs.content(
        rx.vstack(
            # Stage Header Banner
            rx.hstack(
                rx.vstack(
                    rx.hstack(
                        rx.heading(node.title, size="2", weight="bold", color="white"),
                        rx.cond(
                            node.status == "completed",
                            rx.badge("STAGE COMPLETED", color_scheme="green", variant="soft", size="1"),
                            rx.cond(
                                node.status == "active",
                                rx.badge("ACTIVE STREAMING", color_scheme="blue", variant="solid", size="1"),
                                rx.badge("PENDING", color_scheme="gray", variant="surface", size="1"),
                            ),
                        ),
                        spacing="2",
                        align="center",
                    ),
                    rx.text(node.subtitle, size="1", color="#94a3b8"),
                    spacing="0",
                    align="start",
                ),
                justify="between",
                align="center",
                width="100%",
                padding_bottom="0.5rem",
                border_bottom="1px solid #1e293b",
                margin_bottom="0.5rem",
            ),
            # Stage Log Feed or Empty State
            rx.cond(
                node.logs.length() > 0,
                rx.box(
                    rx.vstack(
                        rx.foreach(node.logs, _ephemeral_log_item),
                        spacing="1",
                        align="start",
                        width="100%",
                    ),
                    max_height="280px",
                    overflow_y="auto",
                    width="100%",
                    padding_right="0.25rem",
                ),
                rx.box(
                    rx.hstack(
                        rx.icon("clock", size=18, color="#64748b"),
                        rx.text(
                            "Awaiting upstream execution... Logs will stream here when this stage activates.",
                            size="1",
                            color="#64748b",
                            font_style="italic",
                        ),
                        spacing="2",
                        align="center",
                    ),
                    background="#0b1120",
                    border="1px dashed #1e293b",
                    border_radius="0.5rem",
                    padding="1.25rem",
                    width="100%",
                    text_align="center",
                ),
            ),
            spacing="2",
            align="start",
            width="100%",
        ),
        value=tab_value,
        padding_top="0.75rem",
        width="100%",
    )


def execution_logs_console() -> rx.Component:
    """Render the tabbed real-time execution log monitor with ephemeral step notifications."""
    return rx.card(
        rx.vstack(
            # Monitor Header Toolbar
            rx.hstack(
                rx.hstack(
                    rx.icon("terminal", size=18, color="#38bdf8"),
                    rx.heading("Autonomous Execution Logs & Stage Feeds", size="3", weight="bold", color="white"),
                    rx.cond(
                        AppState.is_scouting,
                        rx.hstack(
                            rx.spinner(size="1"),
                            rx.badge("CYCLE ACTIVE", color_scheme="blue", variant="solid", size="2"),
                            spacing="2",
                            align="center",
                        ),
                        rx.badge("IDLE", color_scheme="gray", variant="surface", size="2"),
                    ),
                    spacing="2",
                    align="center",
                ),
                rx.hstack(
                    rx.button(
                        rx.hstack(
                            rx.icon("sliders-horizontal", size=13),
                            rx.text("Configure Campaign"),
                            spacing="1",
                            align="center",
                        ),
                        variant="soft",
                        color_scheme="blue",
                        size="1",
                        on_click=AppState.open_search_modal,
                    ),
                    rx.button(
                        rx.hstack(
                            rx.icon("rotate-ccw", size=13),
                            rx.text("Clear Logs"),
                            spacing="1",
                            align="center",
                        ),
                        variant="ghost",
                        color_scheme="gray",
                        size="1",
                        on_click=AppState.clear_execution_logs,
                    ),
                    spacing="2",
                    align="center",
                ),
                justify="between",
                align="center",
                width="100%",
            ),
            # Active Cycle Status Banner
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
            # Tabbed Stage Feeds
            rx.tabs.root(
                rx.tabs.list(
                    # Tab 0: All Live Streams
                    rx.tabs.trigger(
                        rx.hstack(
                            rx.icon("activity", size=14, color="#38bdf8"),
                            rx.text("All Feeds", size="1", weight="medium"),
                            rx.badge(
                                AppState.execution_logs.length(),
                                color_scheme="blue",
                                variant="surface",
                                size="1",
                                font_size="9px",
                            ),
                            spacing="1",
                            align="center",
                        ),
                        value="all",
                    ),
                    # Tabs 1 - 6: Pipeline Stages
                    _step_tab_trigger(AppState.pipeline_nodes[0], "step_1"),
                    _step_tab_trigger(AppState.pipeline_nodes[1], "step_2"),
                    _step_tab_trigger(AppState.pipeline_nodes[2], "step_3"),
                    _step_tab_trigger(AppState.pipeline_nodes[3], "step_4"),
                    _step_tab_trigger(AppState.pipeline_nodes[4], "step_5"),
                    _step_tab_trigger(AppState.pipeline_nodes[5], "step_6"),
                    overflow_x="auto",
                    width="100%",
                ),
                # Content for All Feeds
                rx.tabs.content(
                    rx.box(
                        rx.cond(
                            AppState.execution_logs.length() > 0,
                            rx.vstack(
                                rx.foreach(AppState.execution_logs, _ephemeral_log_item),
                                spacing="1",
                                align="start",
                                width="100%",
                            ),
                            rx.box(
                                rx.text(
                                    "No execution logs recorded yet. Launch a prospecting campaign to start streaming.",
                                    size="1",
                                    color="#64748b",
                                    font_style="italic",
                                ),
                                padding="1rem",
                                text_align="center",
                            ),
                        ),
                        max_height="280px",
                        overflow_y="auto",
                        width="100%",
                        padding_top="0.75rem",
                    ),
                    value="all",
                    width="100%",
                ),
                # Content for Individual Step Tabs
                _step_tab_content(AppState.pipeline_nodes[0], "step_1"),
                _step_tab_content(AppState.pipeline_nodes[1], "step_2"),
                _step_tab_content(AppState.pipeline_nodes[2], "step_3"),
                _step_tab_content(AppState.pipeline_nodes[3], "step_4"),
                _step_tab_content(AppState.pipeline_nodes[4], "step_5"),
                _step_tab_content(AppState.pipeline_nodes[5], "step_6"),
                value=AppState.active_log_tab,
                on_change=AppState.set_active_log_tab,
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
    )
