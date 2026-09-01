"""Reflex reactive state and business logic event handlers."""

from __future__ import annotations

import asyncio
import json
from collections import Counter
from typing import Any

import reflex as rx
from loguru import logger
from pydantic import BaseModel, Field

from config.settings import settings
from database.client import get_supabase_client
from database.queries import (
    TABLE_LEADS,
    get_lead_by_id,
    update_lead,
    update_lead_draft,
    update_lead_status,
)
from discovery.geocoder import resolve_lead_coordinates
from dispatch.gmail_sender import dispatch_approved_lead, get_daily_sent_count
from evaluators.llm_service import generate_email_draft
from evaluators.schemas import LeadEvaluation, LeadStatus
from scheduler import run_scouting_pipeline


class PipelineNode(BaseModel):
    """Structured Pydantic schema representing a single scouting stage node."""

    id: str
    step_num: int
    title: str
    subtitle: str
    status: str = "pending"  # "pending", "active", "completed", "error"
    completed_time: str = ""
    logs: list[str] = Field(default_factory=list)


def get_initial_pipeline_nodes() -> list[PipelineNode]:
    """Return clean list of 6 pipeline nodes in deactivated/pending state."""
    return [
        PipelineNode(
            id="1",
            step_num=1,
            title="Discovery & Geo Search",
            subtitle="DuckDuckGo & Overpass Geo API",
            status="pending",
            completed_time="",
            logs=[],
        ),
        PipelineNode(
            id="2",
            step_num=2,
            title="Deduplication & Cache",
            subtitle="Supabase URL & Domain Check",
            status="pending",
            completed_time="",
            logs=[],
        ),
        PipelineNode(
            id="3",
            step_num=3,
            title="Web Extraction & Markdown",
            subtitle="Crawl4AI & Playwright Chromium SPA",
            status="pending",
            completed_time="",
            logs=[],
        ),
        PipelineNode(
            id="4",
            step_num=4,
            title="Contact Verification Gate",
            subtitle="Async DNS MX & Raw SMTP Sockets",
            status="pending",
            completed_time="",
            logs=[],
        ),
        PipelineNode(
            id="5",
            step_num=5,
            title="LLM Reasoning & Fit Scoring",
            subtitle="Gemini 3.5 Flash ICP Bottleneck Analysis",
            status="pending",
            completed_time="",
            logs=[],
        ),
        PipelineNode(
            id="6",
            step_num=6,
            title="Mobile HITL Notification",
            subtitle="Telegram Gate 1 Inline Review Card",
            status="pending",
            completed_time="",
            logs=[],
        ),
    ]


def _process_node_log_update(nodes: list[PipelineNode], msg: str) -> list[PipelineNode]:
    """Assign incoming log line to active node and advance node lifecycle states."""
    import datetime

    current_time_str = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S")
    updated = [n.model_copy(deep=True) for n in nodes]

    step_target: int | None = None
    if "[Step 1/6]" in msg or ("Searching" in msg and "prospects" in msg):
        step_target = 1
    elif "[Step 2/6]" in msg or "Checking deduplication" in msg:
        step_target = 2
    elif "[Step 3/6]" in msg or "Crawling" in msg:
        step_target = 3
    elif "[Step 4/6]" in msg or "Verifying deliverable" in msg:
        step_target = 4
    elif "[Step 5/6]" in msg or "Evaluating" in msg:
        step_target = 5
    elif "[Step 6/6]" in msg or "Pushing Gate 1" in msg:
        step_target = 6
    elif "[FINISH]" in msg or "Scouting cycle complete" in msg or "complete" in msg.lower():
        for n in updated:
            if n.status in ("active", "pending"):
                n.status = "completed"
                if not n.completed_time:
                    n.completed_time = current_time_str
        return updated

    if step_target is not None:
        for n in updated:
            if n.step_num < step_target:
                if n.status != "completed":
                    n.status = "completed"
                    if not n.completed_time:
                        n.completed_time = current_time_str
            elif n.step_num == step_target:
                n.status = "active"
                n.logs.append(msg)
            else:
                if n.status != "completed":
                    n.status = "pending"
    else:
        active_found = False
        for n in updated:
            if n.status == "active":
                n.logs.append(msg)
                active_found = True
                break
        if not active_found and updated:
            updated[0].status = "active"
            updated[0].logs.append(msg)

    return updated


class AppState(rx.State):
    """Primary reactive state manager for the client scouting dashboard."""

    # Data Collections
    leads: list[dict[str, Any]] = []  # noqa: RUF012
    daily_sent_count: int = 0
    daily_cap: int = settings.DAILY_EMAIL_CAP

    # UI Loading & Status Flags
    is_loading: bool = False
    is_scouting: bool = False
    status_message: str = ""
    active_tab: str = "kanban"
    active_lead_action_id: str = ""
    current_step_description: str = ""
    execution_logs: list[str] = []  # noqa: RUF012
    pipeline_nodes: list[PipelineNode] = get_initial_pipeline_nodes()
    active_log_tab: str = "all"

    # Search & Filtering & View Modes
    search_query: str = ""
    selected_status_filter: str = "ALL"
    view_mode: str = "kanban"  # "kanban", "map", "table"

    # Custom Discovery Campaign Configuration & Structured Constraints
    is_search_modal_open: bool = False
    scout_vertical: str = "logistics"
    scout_keywords: str = "logistics freight forwarders, solar contractors, boutique design agencies"
    scout_keywords_list: list[str] = [  # noqa: RUF012
        "Freight Forwarders & 3PL",
        "Solar & Roofing Contractors",
        "Boutique Marketing Agencies",
    ]
    new_keyword_input: str = ""

    scout_location: str = "Chicago, IL"
    scout_language: str = "en"  # "en", "fr", "ar"
    scout_limit: int = 5
    scout_min_score: int = settings.MIN_LEAD_FIT_SCORE

    scout_excluded_domains: str = (
        "yelp.com, yellowpages.com, linkedin.com, wikipedia.org, "
        "indeed.com, glassdoor.com, tripadvisor.com, facebook.com, twitter.com"
    )
    scout_excluded_domains_list: list[str] = [  # noqa: RUF012
        "yelp.com",
        "yellowpages.com",
        "linkedin.com",
        "wikipedia.org",
        "indeed.com",
        "glassdoor.com",
        "tripadvisor.com",
        "facebook.com",
        "twitter.com",
    ]
    new_excluded_domain_input: str = ""

    # Structured Offer & AI Lead Evaluation Constraints
    scout_offer_preset: str = "ocr"  # "ocr", "triage", "dashboard", "custom"
    scout_custom_offer_notes: str = ""
    scout_custom_angle: str = "AI workflow automation, invoice OCR, and inbound triage bots"

    scout_target_bottlenecks: list[str] = [  # noqa: RUF012
        "High daily volume of paperwork & waybills",
        "Manual ERP & spreadsheet data entry",
        "Repetitive booking and customer inquiry triage",
    ]
    new_bottleneck_input: str = ""

    scout_exclude_freelancers: bool = True
    scout_exclude_local_kiosks: bool = True
    scout_exclude_no_digital: bool = True
    scout_custom_disqualification: str = ""

    scout_core_offer: str = (
        "High-value productized workflow automation ($0 infrastructure cost architectures):\n"
        "1. Unstructured Invoice, Waybill & Paperwork OCR Extraction Pipelines.\n"
        "2. Real-Time Inbound Booking & Customer Triage Agents.\n"
        "3. Custom Operations Dashboards & Cross-Platform Inventory Synchronization."
    )
    scout_target_criteria: str = (
        "- Logistics, Freight & Trucking SMBs: High daily volume of bills of lading, customs manifests, dispatching overhead.\n"
        "- Real Estate & Property Management: Repetitive tenant maintenance tickets, scheduling friction, lead follow-up.\n"
        "- Boutique Agencies & E-commerce ($500k–$3M ARR): High order volume, manual supplier reconciliation, customer support triage."
    )
    scout_disqualified_criteria: str = (
        "- Solo micro-businesses or single freelancers.\n"
        "- Local kiosks, restaurants, or businesses without meaningful digital operations or paperwork flow.\n"
        "- Companies without clear operational bottlenecks."
    )
    scout_verify_strict: bool = True
    scout_push_telegram: bool = True

    # Modal Draft Editing State
    is_edit_modal_open: bool = False
    selected_lead_id: str = ""
    selected_company_name: str = ""
    selected_recipient_email: str = ""
    editing_subject: str = ""
    editing_body: str = ""

    # --------------------------------------------------------------------------
    # Computed Properties (Vars)
    # --------------------------------------------------------------------------

    @rx.var
    def scout_keywords_count(self) -> int:
        """Count number of custom business keywords configured."""
        if self.scout_keywords_list:
            return len(self.scout_keywords_list)
        return len([k.strip() for k in self.scout_keywords.split(",") if k.strip()])

    @rx.var
    def scout_language_label(self) -> str:
        """User-facing label for selected search language."""
        mapping = {
            "en": "English (US/Global)",
            "fr": "French (Français)",
            "ar": "Arabic (العربية)",
        }
        return mapping.get(self.scout_language, "English")

    @rx.var
    def scout_resolved_core_offer(self) -> str:
        """Resolve human-selected offer preset into structured prompt context."""
        presets = {
            "ocr": "Unstructured Invoice, Waybill & Paperwork OCR Extraction Pipelines (eliminating manual ERP/spreadsheet entry).",
            "triage": "Real-Time Inbound Booking & Customer Triage Agents (voice/chat booking agents handling high ticket volumes).",
            "dashboard": "Custom Operations Dashboards & Cross-Platform Inventory Synchronization.",
            "custom": "Custom productized workflow automation.",
        }
        base = presets.get(self.scout_offer_preset, presets["ocr"])
        if self.scout_custom_offer_notes.strip():
            return f"{base}\nSpecific Focus: {self.scout_custom_offer_notes.strip()}"
        return base

    @rx.var
    def scout_resolved_target_criteria(self) -> str:
        """Resolve active target bottlenecks into structured prompt criteria."""
        if not self.scout_target_bottlenecks:
            return "- SMBs with operational bottlenecks and manual paperwork overhead."
        return "\n".join(f"- Companies facing: {b}" for b in self.scout_target_bottlenecks)

    @rx.var
    def scout_resolved_disqualified_criteria(self) -> str:
        """Resolve active disqualification toggles into structured anti-profile prompt rules."""
        rules = []
        if self.scout_exclude_freelancers:
            rules.append("- Solo micro-businesses, single freelancers, or sole proprietorships.")
        if self.scout_exclude_local_kiosks:
            rules.append("- Local kiosks, physical retail storefronts, restaurants, or businesses without digital operations.")
        if self.scout_exclude_no_digital:
            rules.append("- Companies without clear operational bottlenecks, digital workflows, or B2B contracts.")
        if self.scout_custom_disqualification.strip():
            rules.append(f"- {self.scout_custom_disqualification.strip()}")
        return "\n".join(rules) if rules else "- No special exclusions."

    @rx.var
    def total_leads_count(self) -> int:
        return len(self.leads)

    @rx.var
    def pending_gate1_leads(self) -> list[dict[str, Any]]:
        return [l for l in self.leads if l.get("status") == LeadStatus.PENDING_LEAD_REVIEW.value]

    @rx.var
    def pending_gate2_leads(self) -> list[dict[str, Any]]:
        return [l for l in self.leads if l.get("status") == LeadStatus.DRAFT_GENERATED.value]

    @rx.var
    def dispatched_leads(self) -> list[dict[str, Any]]:
        return [
            l for l in self.leads
            if l.get("status") in (
                LeadStatus.EMAIL_SENT.value,
                LeadStatus.REPLIED_INTERESTED.value,
                LeadStatus.REPLIED_NOT_INTERESTED.value,
            )
        ]

    @rx.var
    def discarded_leads(self) -> list[dict[str, Any]]:
        return [
            l for l in self.leads
            if l.get("status") in (LeadStatus.LEAD_REJECTED.value, LeadStatus.DRAFT_REJECTED.value)
        ]

    @rx.var
    def status_counts(self) -> dict[str, int]:
        counts = Counter(l.get("status", "UNKNOWN") for l in self.leads)
        return {
            "pending_gate1": counts.get(LeadStatus.PENDING_LEAD_REVIEW.value, 0),
            "pending_gate2": counts.get(LeadStatus.DRAFT_GENERATED.value, 0),
            "sent": counts.get(LeadStatus.EMAIL_SENT.value, 0),
            "interested": counts.get(LeadStatus.REPLIED_INTERESTED.value, 0),
            "rejected": counts.get(LeadStatus.LEAD_REJECTED.value, 0) + counts.get(LeadStatus.DRAFT_REJECTED.value, 0),
        }

    @rx.var
    def filtered_leads(self) -> list[dict[str, Any]]:
        results = self.leads
        if self.selected_status_filter != "ALL":
            results = [l for l in results if l.get("status") == self.selected_status_filter]

        if self.search_query.strip():
            q = self.search_query.lower()
            results = [
                l for l in results
                if q in str(l.get("company_name", "")).lower()
                or q in str(l.get("website_url", "")).lower()
                or q in str(l.get("decision_maker_email", "")).lower()
                or q in str(l.get("summary", "")).lower()
            ]
        return results

    @rx.var
    def high_fit_leads_count(self) -> int:
        """Count of leads with fit score >= 9."""
        return len([l for l in self.leads if int(l.get("fit_score") or 0) >= 9])

    @rx.var
    def leaflet_map_html(self) -> str:
        """Generate self-contained Leaflet Dark Mode HTML map for all filtered leads."""
        from discovery.geocoder import resolve_lead_location_label

        points: list[dict[str, Any]] = []
        for lead in self.filtered_leads:
            coords = resolve_lead_coordinates(
                location=lead.get("location"),
                summary=lead.get("summary"),
                company_name=lead.get("company_name"),
                website_url=lead.get("website_url"),
                lead_id=str(lead.get("id", "")),
                fallback_location=self.scout_location,
            )
            loc_label = resolve_lead_location_label(
                location=lead.get("location"),
                company_name=lead.get("company_name"),
                website_url=lead.get("website_url"),
                summary=lead.get("summary"),
                fallback_location=self.scout_location,
            )
            if coords:
                points.append({
                    "id": str(lead.get("id", "")),
                    "company_name": str(lead.get("company_name", "Unknown Business")),
                    "website_url": str(lead.get("website_url", "#")),
                    "decision_maker_name": str(lead.get("decision_maker_name", "")),
                    "decision_maker_title": str(lead.get("decision_maker_title", "")),
                    "decision_maker_email": str(lead.get("decision_maker_email", "")),
                    "fit_score": int(lead.get("fit_score", 5) or 5),
                    "status": str(lead.get("status", "PENDING_LEAD_REVIEW")),
                    "suggested_angle": str(lead.get("suggested_angle", "")),
                    "location": loc_label,
                    "lat": coords[0],
                    "lon": coords[1],
                })

        leads_json = json.dumps(points)
        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        html, body {{ width: 100%; height: 100%; background: #0b1120; font-family: system-ui, -apple-system, sans-serif; overflow: hidden; position: relative; }}
        #map {{ width: 100%; height: 100%; background: #0b1120; }}
        .leaflet-tile-pane {{
            filter: brightness(0.6) invert(1) contrast(3) hue-rotate(200deg) saturate(0.3) brightness(0.7);
        }}
        .leaflet-popup-content-wrapper {{ background: #0f172a !important; color: #f8fafc !important; border: 1px solid #334155 !important; border-radius: 8px !important; box-shadow: 0 10px 25px -5px rgba(0,0,0,0.6) !important; padding: 0 !important; }}
        .leaflet-popup-content {{ margin: 0 !important; }}
        .leaflet-popup-tip {{ background: #0f172a !important; border: 1px solid #334155 !important; }}
        .leaflet-container {{ background: #0b1120 !important; }}

        /* Floating HUD Navigation Bar */
        .map-nav-bar {{
            position: absolute;
            top: 12px;
            left: 50%;
            transform: translateX(-50%);
            z-index: 1000;
            display: flex;
            align-items: center;
            gap: 8px;
            background: rgba(15, 23, 42, 0.92);
            backdrop-filter: blur(8px);
            border: 1px solid #334155;
            border-radius: 9999px;
            padding: 6px 14px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
            max-width: 95%;
        }}
        .nav-btn {{
            background: #1e293b;
            color: #e2e8f0;
            border: 1px solid #475569;
            border-radius: 9999px;
            padding: 5px 12px;
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 4px;
            transition: all 0.15s ease;
            white-space: nowrap;
        }}
        .nav-btn:hover {{
            background: #3b82f6;
            color: #ffffff;
            border-color: #3b82f6;
        }}
        .lead-select {{
            background: #0b1120;
            color: #f8fafc;
            border: 1px solid #334155;
            border-radius: 6px;
            padding: 5px 10px;
            font-size: 12px;
            font-weight: 500;
            cursor: pointer;
            max-width: 260px;
            outline: none;
        }}
        .lead-counter {{
            color: #94a3b8;
            font-size: 11px;
            font-weight: 600;
            white-space: nowrap;
        }}
    </style>
</head>
<body>
    <div class="map-nav-bar">
        <button class="nav-btn" onclick="prevLead()">◀ Prev</button>
        <select id="lead-select" class="lead-select" onchange="jumpToLead(this.value)">
            <!-- Options populated dynamically -->
        </select>
        <button class="nav-btn" onclick="nextLead()">Next ▶</button>
        <button class="nav-btn" onclick="fitAllLeads()" style="background: #0f766e; border-color: #14b8a6;">🎯 Fit All</button>
    </div>

    <div id="map"></div>

    <script>
        var map;
        var markers = [];
        var bounds = [];
        var leads = {leads_json};
        var currentLeadIndex = 0;

        function initMap() {{
            if (typeof L === 'undefined') {{
                setTimeout(initMap, 50);
                return;
            }}
            map = L.map('map', {{
                zoomControl: true,
                attributionControl: false
            }}).setView([36.8065, 10.1815], 4);

            L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                maxZoom: 19,
                attribution: '&copy; OpenStreetMap'
            }}).addTo(map);

            var selectEl = document.getElementById('lead-select');
            selectEl.innerHTML = '';

            leads.forEach(function(lead, idx) {{
                var score = lead.fit_score || 5;
                var color = score >= 9 ? '#10b981' : (score >= 7 ? '#38bdf8' : (score >= 5 ? '#f59e0b' : '#ef4444'));

                var marker = L.circleMarker([lead.lat, lead.lon], {{
                    radius: score >= 9 ? 9 : 7,
                    fillColor: color,
                    color: '#ffffff',
                    weight: 2,
                    opacity: 1,
                    fillOpacity: 0.85
                }}).addTo(map);

                var cleanUrl = (lead.website_url || '').replace("https://", "").replace("http://", "").split("/")[0];
                var popupHtml = '<div style="min-width: 230px; padding: 12px; font-family: system-ui, sans-serif;">' +
                    '<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">' +
                        '<strong style="font-size: 13px; color: #ffffff;">' + lead.company_name + '</strong>' +
                        '<span style="background: ' + color + '33; color: ' + color + '; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: bold; border: 1px solid ' + color + ';">' + score + '/10</span>' +
                    '</div>' +
                    (lead.location ? '<div style="font-size: 11px; color: #38bdf8; margin-bottom: 4px; font-weight: 500;">📍 ' + lead.location + '</div>' : '') +
                    (lead.website_url && lead.website_url !== '#' ? '<div style="margin-bottom: 4px;"><a href="' + lead.website_url + '" target="_blank" style="color: #60a5fa; font-size: 11px; text-decoration: none;">🌐 ' + cleanUrl + ' ↗</a></div>' : '') +
                    (lead.decision_maker_name ? '<div style="font-size: 11px; color: #cbd5e1; margin-bottom: 2px;">👤 ' + lead.decision_maker_name + (lead.decision_maker_title ? ' (' + lead.decision_maker_title + ')' : '') + '</div>' : '') +
                    (lead.decision_maker_email ? '<div style="font-size: 11px; color: #10b981; margin-bottom: 4px;">✉️ ' + lead.decision_maker_email + '</div>' : '') +
                    (lead.suggested_angle ? '<div style="font-size: 10px; color: #94a3b8; margin-top: 6px; padding-top: 6px; border-top: 1px solid #334155; font-style: italic;">🎯 ' + lead.suggested_angle + '</div>' : '') +
                '</div>';

                marker.bindPopup(popupHtml);
                markers.push(marker);
                bounds.push([lead.lat, lead.lon]);

                // Add to dropdown
                var opt = document.createElement('option');
                opt.value = idx;
                opt.textContent = (idx + 1) + '. ' + lead.company_name + ' (' + score + '/10' + (lead.location ? ' - ' + lead.location.split(',')[0] : '') + ')';
                selectEl.appendChild(opt);
            }});

            if (bounds.length > 0) {{
                map.fitBounds(bounds, {{ padding: [60, 60], maxZoom: 13 }});
            }}

            setTimeout(function() {{ map.invalidateSize(); }}, 200);
        }}

        function focusLead(idx) {{
            if (idx < 0 || idx >= leads.length) return;
            currentLeadIndex = idx;
            var lead = leads[idx];
            var marker = markers[idx];
            
            document.getElementById('lead-select').value = idx;
            map.flyTo([lead.lat, lead.lon], 13, {{
                duration: 1.0,
                easeLinearity: 0.25
            }});
            setTimeout(function() {{
                marker.openPopup();
            }}, 600);
        }}

        function jumpToLead(idxStr) {{
            var idx = parseInt(idxStr, 10);
            focusLead(idx);
        }}

        function nextLead() {{
            if (leads.length === 0) return;
            var nextIdx = (currentLeadIndex + 1) % leads.length;
            focusLead(nextIdx);
        }}

        function prevLead() {{
            if (leads.length === 0) return;
            var prevIdx = (currentLeadIndex - 1 + leads.length) % leads.length;
            focusLead(prevIdx);
        }}

        function fitAllLeads() {{
            if (bounds.length > 0) {{
                map.fitBounds(bounds, {{ padding: [60, 60], maxZoom: 13 }});
            }}
        }}

        // Keyboard shortcuts: Left/Right arrows
        document.addEventListener('keydown', function(e) {{
            if (e.key === 'ArrowRight') {{ nextLead(); }}
            if (e.key === 'ArrowLeft') {{ prevLead(); }}
        }});

        initMap();
    </script>
</body>
</html>"""

    # --------------------------------------------------------------------------
    # Event Handlers
    # --------------------------------------------------------------------------

    def set_view_mode(self, mode: str | list[str]) -> None:
        """Set the dashboard display view mode ('kanban', 'map', 'table')."""
        if isinstance(mode, list):
            self.view_mode = mode[0] if mode else "kanban"
        else:
            self.view_mode = str(mode)

    async def fetch_leads(self) -> None:
        """Fetch all leads from Supabase and calculate active metrics."""
        self.is_loading = True
        try:
            sb = await get_supabase_client()
            response = await sb.table(TABLE_LEADS).select("*").order("created_at", desc=True).execute()
            self.leads = response.data or []
            self.daily_sent_count = await get_daily_sent_count()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to fetch leads from Supabase")
            self.status_message = f"Error fetching data: {exc}"
        finally:
            self.is_loading = False

    async def handle_dnd_drop(self, payload: str) -> None:
        """Handle drag-and-drop event from Kanban board columns."""
        if not payload or ":" not in payload:
            return
        parts = payload.split(":")
        if len(parts) >= 2:
            lead_id = parts[0].strip()
            target_col = parts[1].strip()
            await self.move_lead_status(lead_id, target_col)

    async def move_lead_status(self, lead_id: str, target_column: str) -> None:
        """Move a lead to a new workflow status when dragged and dropped between Kanban columns."""
        lead_id = str(lead_id).strip()
        if not lead_id:
            return

        lead = next((l for l in self.leads if str(l.get("id")) == lead_id), None)
        current_status = lead.get("status") if lead else None
        if not current_status:
            db_lead = await get_lead_by_id(lead_id)
            current_status = db_lead.get("status") if db_lead else None

        if target_column == "gate2":
            if current_status == "PENDING_LEAD_REVIEW" or not current_status:
                await self.approve_lead(lead_id)
        elif target_column == "dispatched":
            if current_status == "DRAFT_GENERATED" or not current_status:
                await self.send_draft(lead_id)
            elif current_status == "PENDING_LEAD_REVIEW":
                # Auto-approve then dispatch
                await self.approve_lead(lead_id)
                await self.send_draft(lead_id)
        elif target_column == "gate1":
            if current_status != "PENDING_LEAD_REVIEW":
                await update_lead_status(lead_id, LeadStatus.PENDING_LEAD_REVIEW)
                self.status_message = "Moved lead back to Gate 1 Lead Qualification."
                await self.fetch_leads()
        elif target_column == "discarded":
            await self.discard_lead(lead_id)

    async def approve_lead(self, lead_id: str) -> None:
        """Approve Gate 1: Generate AI cold pitch draft and transition to DRAFT_GENERATED."""
        self.is_loading = True
        self.active_lead_action_id = lead_id
        try:
            lead = await get_lead_by_id(lead_id)
            if not lead:
                self.status_message = "Lead not found"
                return

            # Generate cold pitch copy if not already generated
            subject = lead.get("email_subject")
            body = lead.get("email_body")
            if not subject or not body:
                eval_obj = LeadEvaluation(
                    company_name=lead["company_name"],
                    website_url=lead["website_url"],
                    decision_maker_name=lead.get("decision_maker_name") or "Operations Lead",
                    decision_maker_title=lead.get("decision_maker_title") or "Leadership",
                    decision_maker_email=lead.get("decision_maker_email") or "",
                    fit_score=lead.get("fit_score", 8),
                    summary=lead.get("summary", ""),
                    pros=lead.get("pros") or [],
                    cons=lead.get("cons") or [],
                    suggested_angle=lead.get("suggested_angle", "Workflow automation"),
                )
                draft = await generate_email_draft(eval_obj)
                subject = draft.subject
                body = draft.body

            await update_lead_draft(lead_id=lead_id, email_subject=subject, email_body=body)
            await update_lead_status(lead_id, LeadStatus.DRAFT_GENERATED)
            self.status_message = f"Approved lead '{lead.get('company_name')}'. Draft generated for Gate 2."
            await self.fetch_leads()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to approve lead")
            self.status_message = f"Approval failed: {exc}"
        finally:
            self.is_loading = False
            self.active_lead_action_id = ""

    async def discard_lead(self, lead_id: str) -> None:
        """Discard Gate 1 lead: transition to LEAD_REJECTED."""
        self.active_lead_action_id = lead_id
        try:
            await update_lead_status(lead_id, LeadStatus.LEAD_REJECTED)
            self.status_message = "Lead discarded."
            await self.fetch_leads()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to discard lead")
            self.status_message = f"Discard failed: {exc}"
        finally:
            self.active_lead_action_id = ""

    async def send_draft(self, lead_id: str) -> None:
        """Approve Gate 2: Dispatch email via Gmail API and mark EMAIL_SENT."""
        self.is_loading = True
        self.active_lead_action_id = lead_id
        try:
            res = await dispatch_approved_lead(lead_id=lead_id, apply_jitter=False)
            self.status_message = f"Dispatched email to {res.get('to_email')} ({res.get('company_name')})."
            await self.fetch_leads()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to dispatch draft")
            self.status_message = f"Dispatch failed: {exc}"
        finally:
            self.is_loading = False
            self.active_lead_action_id = ""

    async def cancel_draft(self, lead_id: str) -> None:
        """Cancel Gate 2 draft: transition to DRAFT_REJECTED."""
        self.active_lead_action_id = lead_id
        try:
            await update_lead_status(lead_id, LeadStatus.DRAFT_REJECTED)
            self.status_message = "Draft cancelled."
            await self.fetch_leads()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to cancel draft")
            self.status_message = f"Cancellation failed: {exc}"
        finally:
            self.active_lead_action_id = ""

    def open_search_modal(self) -> None:
        """Open the custom prospecting campaign configuration modal."""
        self.is_search_modal_open = True

    def close_search_modal(self) -> None:
        """Close the custom prospecting campaign configuration modal."""
        self.is_search_modal_open = False

    def set_search_modal_open(self, is_open: bool) -> None:
        """Set search modal open state directly."""
        self.is_search_modal_open = is_open

    def set_active_log_tab(self, tab: str) -> None:
        """Switch active log feed tab."""
        self.active_log_tab = tab

    def set_new_keyword_input(self, val: str) -> None:
        """Set active new keyword input value."""
        self.new_keyword_input = val

    def add_scout_keyword(self) -> None:
        """Add entered keyword to the target search keywords list."""
        val = self.new_keyword_input.strip()
        if val and val not in self.scout_keywords_list:
            self.scout_keywords_list = [*self.scout_keywords_list, val]
        self.new_keyword_input = ""

    def add_keyword_preset(self, preset: str) -> None:
        """Quickly add a preset industry/niche keyword chip."""
        if preset and preset not in self.scout_keywords_list:
            self.scout_keywords_list = [*self.scout_keywords_list, preset]

    def remove_scout_keyword(self, kw: str) -> None:
        """Remove a keyword from the active search targets."""
        self.scout_keywords_list = [k for k in self.scout_keywords_list if k != kw]

    def set_new_excluded_domain_input(self, val: str) -> None:
        """Set active new domain blocklist input value."""
        self.new_excluded_domain_input = val

    def add_excluded_domain(self) -> None:
        """Add entered domain to the disqualified domains list."""
        val = self.new_excluded_domain_input.strip().lower()
        # Clean protocol or leading slash
        val = val.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]
        if val and val not in self.scout_excluded_domains_list:
            self.scout_excluded_domains_list = [*self.scout_excluded_domains_list, val]
        self.new_excluded_domain_input = ""

    def remove_excluded_domain(self, domain: str) -> None:
        """Remove a domain from the exclusion blocklist."""
        self.scout_excluded_domains_list = [d for d in self.scout_excluded_domains_list if d != domain]

    def set_scout_offer_preset(self, val: str) -> None:
        """Set productized core offer preset ('ocr', 'triage', 'dashboard', 'custom')."""
        self.scout_offer_preset = val

    def set_scout_custom_offer_notes(self, val: str) -> None:
        """Set custom offer angle / specific notes."""
        self.scout_custom_offer_notes = val

    def set_new_bottleneck_input(self, val: str) -> None:
        """Set new target bottleneck input value."""
        self.new_bottleneck_input = val

    def add_target_bottleneck(self) -> None:
        """Add entered bottleneck to the target criteria list."""
        val = self.new_bottleneck_input.strip()
        if val and val not in self.scout_target_bottlenecks:
            self.scout_target_bottlenecks = [*self.scout_target_bottlenecks, val]
        self.new_bottleneck_input = ""

    def add_bottleneck_preset(self, preset: str) -> None:
        """Quickly add a common operational bottleneck chip."""
        if preset and preset not in self.scout_target_bottlenecks:
            self.scout_target_bottlenecks = [*self.scout_target_bottlenecks, preset]

    def remove_target_bottleneck(self, item: str) -> None:
        """Remove a bottleneck from the target criteria list."""
        self.scout_target_bottlenecks = [b for b in self.scout_target_bottlenecks if b != item]

    def set_scout_exclude_freelancers(self, val: bool) -> None:
        """Toggle disqualification for solo micro-businesses and freelancers."""
        self.scout_exclude_freelancers = bool(val)

    def set_scout_exclude_local_kiosks(self, val: bool) -> None:
        """Toggle disqualification for retail shops and local restaurants."""
        self.scout_exclude_local_kiosks = bool(val)

    def set_scout_exclude_no_digital(self, val: bool) -> None:
        """Toggle disqualification for businesses without digital workflow."""
        self.scout_exclude_no_digital = bool(val)

    def set_scout_custom_disqualification(self, val: str) -> None:
        """Set optional custom disqualification rule."""
        self.scout_custom_disqualification = val

    def set_scout_keywords(self, val: str) -> None:
        """Update target business keywords."""
        self.scout_keywords = val

    def set_scout_location(self, val: str) -> None:
        """Update target search location."""
        self.scout_location = val

    def set_scout_language(self, val: str) -> None:
        """Update search language ('en', 'fr', 'ar')."""
        self.scout_language = val

    def set_scout_min_score(self, val: Any) -> None:
        """Update min fit score threshold."""
        try:
            self.scout_min_score = max(1, min(10, int(val)))
        except (ValueError, TypeError):
            pass

    def set_scout_limit(self, val: Any) -> None:
        """Update max prospects limit per keyword."""
        try:
            self.scout_limit = max(1, min(50, int(val)))
        except (ValueError, TypeError):
            pass

    def set_scout_excluded_domains(self, val: str) -> None:
        """Update dynamic excluded domains blocklist."""
        self.scout_excluded_domains = val

    def set_scout_custom_angle(self, val: str) -> None:
        """Update custom value proposition offer angle."""
        self.scout_custom_angle = val

    def set_scout_core_offer(self, val: str) -> None:
        """Update custom core offer prompt constraints."""
        self.scout_core_offer = val

    def set_scout_target_criteria(self, val: str) -> None:
        """Update custom target qualification criteria prompt constraints."""
        self.scout_target_criteria = val

    def set_scout_disqualified_criteria(self, val: str) -> None:
        """Update custom disqualified criteria prompt constraints."""
        self.scout_disqualified_criteria = val

    def set_scout_verify_strict(self, val: bool) -> None:
        """Update strict SMTP verification toggle."""
        self.scout_verify_strict = bool(val)

    def set_scout_push_telegram(self, val: bool) -> None:
        """Update Telegram Gate 1 push toggle."""
        self.scout_push_telegram = bool(val)

    def open_edit_modal(self, lead: dict[str, Any]) -> None:
        """Open the draft copy editor modal."""
        self.selected_lead_id = str(lead.get("id", ""))
        self.selected_company_name = str(lead.get("company_name", ""))
        self.selected_recipient_email = str(lead.get("decision_maker_email", ""))
        self.editing_subject = str(lead.get("email_subject", ""))
        self.editing_body = str(lead.get("email_body", ""))
        self.is_edit_modal_open = True

    def close_edit_modal(self) -> None:
        """Close the draft copy editor modal."""
        self.is_edit_modal_open = False

    async def save_edited_draft(self) -> None:
        """Save edited email subject and body to database."""
        if not self.selected_lead_id:
            return
        try:
            await update_lead(
                self.selected_lead_id,
                email_subject=self.editing_subject,
                email_body=self.editing_body,
                status=LeadStatus.DRAFT_GENERATED.value,
            )
            self.is_edit_modal_open = False
            self.status_message = "Draft updated successfully."
            await self.fetch_leads()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to save edited draft")
            self.status_message = f"Save failed: {exc}"

    async def trigger_scouting(self):  # type: ignore[no-untyped-def]
        """Execute a one-shot prospect scouting cycle with real-time log streaming."""
        self.is_search_modal_open = False
        self.is_scouting = True
        self.pipeline_nodes = get_initial_pipeline_nodes()
        self.execution_logs = ["🚀 [INIT] Starting background scouting cycle..."]
        self.current_step_description = "Starting scouting cycle..."

        # Parse custom business keywords from list or fallback string
        kw_list = [k.strip() for k in self.scout_keywords_list if k.strip()]
        if not kw_list:
            kw_list = [k.strip() for k in self.scout_keywords.split(",") if k.strip()]
        if not kw_list:
            kw_list = [self.scout_vertical or "logistics"]

        # Parse excluded domains from list or fallback string
        excluded_list = [d.strip() for d in self.scout_excluded_domains_list if d.strip()]
        if not excluded_list:
            excluded_list = [d.strip() for d in self.scout_excluded_domains.split(",") if d.strip()]

        # Resolve dynamic prompt constraints
        offer_str = self.scout_resolved_core_offer or self.scout_core_offer
        target_str = self.scout_resolved_target_criteria or self.scout_target_criteria
        disqualified_str = self.scout_resolved_disqualified_criteria or self.scout_disqualified_criteria

        self.status_message = (
            f"Running discovery for {len(kw_list)} niche(s) in {self.scout_location} ({self.scout_language.upper()})..."
        )
        yield

        queue: asyncio.Queue[str] = asyncio.Queue()

        async def _on_progress(msg: str) -> None:
            await queue.put(msg)

        task = asyncio.create_task(
            run_scouting_pipeline(
                keywords=kw_list,
                locations=[self.scout_location],
                language=self.scout_language,
                max_prospects_per_vertical=self.scout_limit,
                min_fit_score=self.scout_min_score,
                custom_angle=self.scout_custom_angle,
                core_offer=offer_str,
                target_criteria=target_str,
                disqualified_criteria=disqualified_str,
                disqualified_domains=excluded_list,
                verify_strict=self.scout_verify_strict,
                push_to_telegram=self.scout_push_telegram,
                progress_callback=_on_progress,
            )
        )

        while not task.done() or not queue.empty():
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=0.1)
                self.execution_logs.append(msg)
                self.current_step_description = msg
                self.pipeline_nodes = _process_node_log_update(self.pipeline_nodes, msg)
                yield
            except TimeoutError:
                yield

        try:
            stats = task.result()
            self.status_message = (
                f"Scouting complete: Found {stats.get('discovered', 0)}, "
                f"Qualified {stats.get('qualified', 0)} new prospects."
            )
            self.pipeline_nodes = _process_node_log_update(self.pipeline_nodes, "[FINISH] Complete")
        except Exception as exc:  # noqa: BLE001
            logger.exception("Scouting execution failed")
            self.status_message = f"Scouting failed: {exc}"
            self.execution_logs.append(f"❌ Execution error: {exc}")
            err_nodes = [n.model_copy(deep=True) for n in self.pipeline_nodes]
            for n in err_nodes:
                if n.status == "active":
                    n.status = "error"
                    n.logs = list(n.logs) + [f"❌ Execution error: {exc}"]
            self.pipeline_nodes = err_nodes
        finally:
            self.is_scouting = False

        yield
        await self.fetch_leads()

    def reset_pipeline_nodes(self) -> None:
        """Reset all nodes back to initial deactivated pending state."""
        self.pipeline_nodes = get_initial_pipeline_nodes()
        self.execution_logs = []
        self.current_step_description = ""

    def clear_execution_logs(self) -> None:
        """Clear execution log history and reset nodes."""
        self.reset_pipeline_nodes()

    def set_active_tab(self, tab_name: str) -> None:
        self.active_tab = tab_name

    def clear_status_message(self) -> None:
        self.status_message = ""

    def set_search_query(self, value: str) -> None:
        self.search_query = value

    def set_selected_status_filter(self, value: str) -> None:
        self.selected_status_filter = value

    def set_scout_vertical(self, value: str) -> None:
        self.scout_vertical = value

    def set_editing_subject(self, value: str) -> None:
        self.editing_subject = value

    def set_editing_body(self, value: str) -> None:
        self.editing_body = value

