"""Live execution nodes and Mermaid-style pipeline DAG component."""

import reflex as rx

from ui.state import AppState, PipelineNode


def _log_line_item(line: rx.Var[str]) -> rx.Component:
    """Render an individual execution step log line."""
    return rx.hstack(
        rx.text(
            line,
            size="1",
            color=rx.match(
                line.contains("❌"),
                (True, "#f87171"),
                rx.match(
                    line.contains("✅"),
                    (True, "#4ade80"),
                    rx.match(
                        line.contains("Step"),
                        (True, "#60a5fa"),
                        "#cbd5e1",
                    ),
                ),
            ),
            font_family="ui-monospace, monospace",
        ),
        spacing="1",
        align="center",
        width="100%",
    )


def _mermaid_node_card(node: rx.Var[PipelineNode], step_tag: str) -> rx.Component:
    """Render an individual Mermaid-style flowchart node with active log stream."""
    return rx.box(
        rx.vstack(
            # Node Header Bar
            rx.hstack(
                rx.hstack(
                    rx.badge(
                        step_tag,
                        color_scheme="gray",
                        variant="surface",
                        size="1",
                        font_family="monospace",
                    ),
                    # Node State Icon: check / spinner / error / clock
                    rx.cond(
                        node.status == "completed",
                        rx.icon("circle-check", color="#22c55e", size=18),
                        rx.cond(
                            node.status == "active",
                            rx.spinner(size="1", color="blue"),
                            rx.cond(
                                node.status == "error",
                                rx.icon("circle-alert", color="#ef4444", size=18),
                                rx.icon("clock", color="#64748b", size=18),
                            ),
                        ),
                    ),
                    rx.vstack(
                        rx.text(
                            node.title,
                            size="2",
                            weight="bold",
                            color=rx.cond(node.status == "pending", "#94a3b8", "white"),
                        ),
                        rx.text(node.subtitle, size="1", color="#64748b"),
                        spacing="0",
                        align="start",
                    ),
                    spacing="2",
                    align="center",
                ),
                # Status Badge & Completed Time
                rx.cond(
                    node.status == "completed",
                    rx.badge(
                        rx.hstack(
                            rx.icon("check", size=10),
                            rx.text(node.completed_time),
                            spacing="1",
                            align="center",
                        ),
                        color_scheme="green",
                        variant="soft",
                        size="1",
                    ),
                    rx.cond(
                        node.status == "active",
                        rx.badge(
                            "ACTIVE", color_scheme="blue", variant="solid", size="1"
                        ),
                        rx.cond(
                            node.status == "error",
                            rx.badge(
                                "FAILED", color_scheme="red", variant="solid", size="1"
                            ),
                            rx.badge(
                                "PENDING",
                                color_scheme="gray",
                                variant="surface",
                                size="1",
                            ),
                        ),
                    ),
                ),
                justify="between",
                align="center",
                width="100%",
            ),
            # Node Body / Embedded Real-time Logs
            rx.cond(
                node.status == "active",
                rx.box(
                    rx.vstack(
                        rx.foreach(node.logs, _log_line_item),
                        spacing="1",
                        align="start",
                        width="100%",
                    ),
                    background="#020617",
                    border="1px solid #1e3a8a",
                    border_radius="0.375rem",
                    padding="0.5rem",
                    max_height="140px",
                    overflow_y="auto",
                    width="100%",
                    margin_top="0.375rem",
                ),
                rx.cond(
                    (node.status == "completed") & (node.logs.length() > 0),
                    rx.box(
                        rx.vstack(
                            rx.foreach(node.logs, _log_line_item),
                            spacing="1",
                            align="start",
                            width="100%",
                        ),
                        background="#02061780",
                        border="1px solid #1e293b",
                        border_radius="0.375rem",
                        padding="0.5rem",
                        max_height="90px",
                        overflow_y="auto",
                        width="100%",
                        margin_top="0.25rem",
                    ),
                    rx.box(
                        rx.text(
                            "Waiting for upstream node signal...",
                            size="1",
                            color="#475569",
                            font_style="italic",
                        ),
                        padding_top="0.25rem",
                    ),
                ),
            ),
            spacing="2",
            align="start",
            width="100%",
        ),
        background=rx.match(
            node.status,
            ("active", "rgba(15, 23, 42, 0.95)"),
            ("completed", "rgba(15, 23, 42, 0.85)"),
            ("error", "rgba(30, 10, 10, 0.85)"),
            "rgba(15, 23, 42, 0.4)",
        ),
        border=rx.match(
            node.status,
            ("active", "2px solid #3b82f6"),
            ("completed", "1.5px solid #10b981"),
            ("error", "1.5px solid #ef4444"),
            "1.5px dashed #334155",
        ),
        border_radius="0.75rem",
        padding="1rem",
        width="100%",
        min_width="250px",
        flex="1",
        opacity=rx.cond(node.status == "pending", "0.6", "1.0"),
        box_shadow=rx.cond(
            node.status == "active", "0 0 20px rgba(59, 130, 246, 0.35)", "none"
        ),
    )


def _horizontal_edge(
    source_node: rx.Var[PipelineNode], label: str = ""
) -> rx.Component:
    """Render an edge connector arrow aligned horizontally with the node header bar."""
    edge_color = rx.match(
        source_node.status,
        ("completed", "#10b981"),
        ("active", "#3b82f6"),
        "#334155",
    )
    return rx.vstack(
        rx.cond(
            label != "",
            rx.badge(
                label,
                variant="surface",
                color_scheme="gray",
                size="1",
                font_family="monospace",
                font_size="9px",
            ),
            rx.text(""),
        ),
        rx.hstack(
            rx.box(
                width="28px",
                height="2px",
                background=edge_color,
            ),
            rx.icon(
                "chevron-right",
                size=14,
                color=edge_color,
                stroke_width=2.5,
                margin_left="-4px",
            ),
            spacing="0",
            align="center",
        ),
        spacing="1",
        align="center",
        justify="center",
        margin_top="1.25rem",
        min_width="44px",
    )


def _stage_bridge(source_node: rx.Var[PipelineNode]) -> rx.Component:
    """Render a full-width stage transition rail between diagram rows."""
    bridge_color = rx.match(
        source_node.status,
        ("completed", "#10b981"),
        ("active", "#3b82f6"),
        "#334155",
    )
    return rx.hstack(
        rx.box(height="1px", flex="1", background=bridge_color, opacity="0.4"),
        rx.hstack(
            rx.icon("arrow-down", size=14, color=bridge_color),
            rx.badge(
                "STAGE 1 → STAGE 2 : CONTACT RESOLUTION & REASONING",
                variant="surface",
                color_scheme="gray",
                size="1",
                font_size="10px",
                font_family="monospace",
            ),
            rx.icon("arrow-down", size=14, color=bridge_color),
            spacing="2",
            align="center",
            padding_x="1rem",
            padding_y="0.25rem",
            border=rx.match(
                source_node.status,
                ("completed", "1px solid #10b98140"),
                ("active", "1px solid #3b82f640"),
                "1px solid #334155",
            ),
            border_radius="9999px",
            background="#0b1120",
        ),
        rx.box(height="1px", flex="1", background=bridge_color, opacity="0.4"),
        spacing="2",
        align="center",
        width="100%",
        margin_y="0.75rem",
    )


def execution_logs_console() -> rx.Component:
    """Render the real-time Mermaid-style connected DAG pipeline diagram."""
    return rx.card(
        rx.vstack(
            # Graph Header Toolbar
            rx.hstack(
                rx.hstack(
                    rx.icon("git-fork", size=18, color="#38bdf8"),
                    rx.heading(
                        "Autonomous Pipeline Flowchart",
                        size="3",
                        weight="bold",
                        color="white",
                    ),
                    rx.badge(
                        "graph LR", color_scheme="cyan", variant="surface", size="1"
                    ),
                    rx.cond(
                        AppState.is_scouting,
                        rx.hstack(
                            rx.spinner(size="1"),
                            rx.badge(
                                "CYCLE IN PROGRESS",
                                color_scheme="blue",
                                variant="solid",
                                size="2",
                            ),
                            spacing="2",
                            align="center",
                        ),
                        rx.badge(
                            "6 CONNECTED NODES",
                            color_scheme="gray",
                            variant="surface",
                            size="2",
                        ),
                    ),
                    spacing="2",
                    align="center",
                ),
                rx.button(
                    rx.hstack(
                        rx.icon("rotate-ccw", size=13),
                        rx.text("Reset Graph"),
                        spacing="1",
                        align="center",
                    ),
                    variant="ghost",
                    color_scheme="gray",
                    size="1",
                    on_click=AppState.reset_pipeline_nodes,
                ),
                justify="between",
                align="center",
                width="100%",
            ),
            # Active Stage Status Banner (if executing)
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
            # Connected Mermaid Diagram Canvas
            rx.box(
                rx.vstack(
                    # Row 1: Steps 1 -> 2 -> 3
                    rx.hstack(
                        _mermaid_node_card(AppState.pipeline_nodes[0], "#01"),
                        _horizontal_edge(AppState.pipeline_nodes[0], "candidates"),
                        _mermaid_node_card(AppState.pipeline_nodes[1], "#02"),
                        _horizontal_edge(AppState.pipeline_nodes[1], "filtered"),
                        _mermaid_node_card(AppState.pipeline_nodes[2], "#03"),
                        width="100%",
                        align="start",
                        justify="between",
                    ),
                    # Stage Bridge between Row 1 and Row 2
                    _stage_bridge(AppState.pipeline_nodes[2]),
                    # Row 2: Steps 4 -> 5 -> 6
                    rx.hstack(
                        _mermaid_node_card(AppState.pipeline_nodes[3], "#04"),
                        _horizontal_edge(AppState.pipeline_nodes[3], "valid SMTP"),
                        _mermaid_node_card(AppState.pipeline_nodes[4], "#05"),
                        _horizontal_edge(AppState.pipeline_nodes[4], "score >= 7"),
                        _mermaid_node_card(AppState.pipeline_nodes[5], "#06"),
                        width="100%",
                        align="start",
                        justify="between",
                    ),
                    spacing="2",
                    width="100%",
                ),
                background="radial-gradient(#1e293b 1.5px, #0a0f1d 1.5px)",
                background_size="20px 20px",
                border="1px solid #1e293b",
                border_radius="0.75rem",
                padding="1.25rem",
                width="100%",
                overflow_x="auto",
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
