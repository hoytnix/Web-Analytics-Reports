"""
Markdown Report Renderer generating clean GitHub-Flavored Markdown reports.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from ..models import ReportSection, SectionMetrics
from ..utils import format_bytes, format_number


def render_markdown_section(section: ReportSection) -> str:
    """Render a single ReportSection as GitHub Flavored Markdown."""
    m: SectionMetrics = section.metrics
    lines: List[str] = []

    # Title & Metadata
    lines.append(f"# Cloudflare Portfolio Analytics — {section.display_label}")
    lines.append("")
    lines.append(
        f"> **Monitored Zones:** {len(m.zone_items)} &bull; "
        f"**Range:** {section.window.display_range} &bull; "
        f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
    )
    lines.append("")

    # KPI Summary Table
    v_views_fmt = format_number(m.total_vercel_views) if m.vercel.is_configured else "-"
    v_vis_fmt = format_number(m.total_vercel_visitors) if m.vercel.is_configured else "-"

    lines.append("## Portfolio KPI Summary")
    lines.append("")
    lines.append("| Metric | Value | Metric | Value |")
    lines.append("| :--- | :--- | :--- | :--- |")
    lines.append(f"| **CF Total Requests** | {format_number(m.total_requests)} | **CF Threats Blocked** | {format_number(m.total_threats)} |")
    lines.append(f"| **CF Avg Cache Ratio** | {m.avg_cache_ratio} | **CF Edge Pageviews** | {format_number(m.total_cf_views)} |")
    lines.append(f"| **CF Total Bandwidth** | {format_bytes(m.total_bytes)} | **CF Web Views (RUM)** | {format_number(m.total_cf_web_views)} |")
    lines.append(f"| **CF Cached Bandwidth** | {format_bytes(m.cached_bytes)} | **CF Web Visits (RUM)** | {format_number(m.total_cf_web_visits)} |")
    lines.append(f"| **Vercel Pageviews** | {v_views_fmt} | **Vercel Unique Visitors** | {v_vis_fmt} |")
    lines.append("")

    # Monitored Zones Table
    lines.append("## Monitored Zone Breakdown")
    lines.append("")
    lines.append("| Zone Domain | Requests | Cache % | Bandwidth | Cached BW | Edge Views | Threats | CF Web Views | CF Web Visits | Vercel Views | Vercel Vis |")
    lines.append("| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")

    for z in m.zone_items:
        v_view = format_number(z.vercel_views) if z.vercel_views is not None else "-"
        v_vis = format_number(z.vercel_visitors) if z.vercel_visitors is not None else "-"
        cf_w_view = format_number(z.cf_web_views) if z.cf_web_views is not None else "0"
        cf_w_vis = format_number(z.cf_web_visits) if z.cf_web_visits is not None else "0"

        lines.append(
            f"| `{z.zone_name}` | {format_number(z.requests)} | {z.hit_ratio} | "
            f"{format_bytes(z.bytes)} | {format_bytes(z.cached_bytes)} | "
            f"{format_number(z.cf_views)} | {format_number(z.cf_threats)} | "
            f"**{cf_w_view}** | **{cf_w_vis}** | "
            f"{v_view} | {v_vis} |"
        )
    lines.append("")

    # Deep Analytics Breakdown
    lines.append("---")
    lines.append("## Deep Analytics & Multi-Node Breakdown")
    lines.append("")

    # 1. Subdomains
    lines.append("### 1. Top Subdomains (Hostnames)")
    lines.append("")
    lines.append("| Hostname | Requests | Share | Bandwidth |")
    lines.append("| :--- | ---: | ---: | ---: |")
    for s in m.subdomains:
        lines.append(f"| `{s.label}` | {s.count_formatted} | {s.share_pct} | {s.bytes_formatted} |")
    lines.append("")

    # 2. Countries
    lines.append("### 2. Geographic Distribution (Top Countries)")
    lines.append("")
    lines.append("| Code | Country / Territory | Requests | Share | Bandwidth |")
    lines.append("| :---: | :--- | ---: | ---: | ---: |")
    for c in m.countries:
        lines.append(f"| **{c.key}** | {c.label} | {c.count_formatted} | {c.share_pct} | {c.bytes_formatted} |")
    lines.append("")

    # 3. HTTP Status Codes & Health
    sh = m.status_health
    lines.append("### 3. HTTP Status Codes & Origin Health")
    lines.append("")
    health_badge = "🟢 HEALTHY" if sh.is_healthy else "🟡 MONITOR"
    lines.append(f"**Origin Health Status:** {health_badge} (Origin 5xx Error Rate: `{sh.origin_error_rate}`)")
    lines.append("")
    lines.append("| Status Category | Count | Traffic Share |")
    lines.append("| :--- | ---: | ---: |")
    lines.append(f"| **2xx Success** | {sh.s2xx.count_formatted} | {sh.s2xx.share_pct} |")
    lines.append(f"| **3xx Redirection** | {sh.s3xx.count_formatted} | {sh.s3xx.share_pct} |")
    lines.append(f"| **4xx Client Error** | {sh.s4xx.count_formatted} | {sh.s4xx.share_pct} |")
    lines.append(f"| **5xx Origin Error** | {sh.s5xx.count_formatted} | {sh.s5xx.share_pct} |")
    lines.append("")

    # 4. Cache Efficiency
    ce = m.cache_efficiency
    lines.append("### 4. Cache Efficiency & Bandwidth Savings")
    lines.append("")
    lines.append(f"- **Request Cache Hit Ratio:** `{ce.req_hit_ratio}`")
    lines.append(f"- **Bandwidth Cache Hit Ratio:** `{ce.bytes_hit_ratio}`")
    lines.append(f"- **Total Saved Bandwidth:** `{ce.saved_bytes}`")
    lines.append("")
    lines.append("| Cache Status | Requests | Share | Bandwidth |")
    lines.append("| :--- | ---: | ---: | ---: |")
    for item in ce.breakdown:
        lines.append(f"| `{item.key}` | {item.count_formatted} | {item.share_pct} | {item.bytes_formatted} |")
    lines.append("")

    # 5. Top Endpoints & Probes
    lines.append("### 5. Top Visited Endpoints & Suspicious Probes")
    lines.append("")
    lines.append("#### Top Visited Routes")
    lines.append("| Route Path | Requests |")
    lines.append("| :--- | ---: |")
    for p in m.paths:
        lines.append(f"| `{p.label}` | {p.count_formatted} |")
    lines.append("")

    lines.append("#### Suspicious Probes & Scans (404 / 403)")
    lines.append("| Probe Path | Status | Requests |")
    lines.append("| :--- | :---: | ---: |")
    for pr in m.probes:
        lines.append(f"| `{pr.path}` | `{pr.status}` | {pr.count_formatted} |")
    lines.append("")

    # 6. Protocols & TLS
    pr = m.protocols
    lines.append("### 6. Client Protocols & Modern Encryption")
    lines.append("")
    lines.append(f"- **HTTP/3 (QUIC) Adoption:** `{pr.h3_adoption}`")
    lines.append(f"- **TLS 1.3 Modern Cipher Adoption:** `{pr.tls13_adoption}`")
    lines.append("")
    lines.append("| Protocol Version | Requests | Share |")
    lines.append("| :--- | ---: | ---: |")
    for item in pr.http_breakdown:
        lines.append(f"| {item.label} | {item.count_formatted} | {item.share_pct} |")
    for item in pr.ssl_breakdown:
        lines.append(f"| {item.label} | {item.count_formatted} | {item.share_pct} |")
    lines.append("")

    # 7. Security & Threat Mitigation
    sec = m.security
    lines.append("### 7. Security & Threat Mitigation")
    lines.append("")
    lines.append(f"**Total Mitigated Threat Events:** `{sec.total_threats_formatted}`")
    lines.append("")
    if sec.breakdown:
        lines.append("| Action | Security Source | Triggered Events |")
        lines.append("| :--- | :--- | ---: |")
        for s in sec.breakdown:
            lines.append(f"| `{s.action}` | `{s.source}` | {s.count_formatted} |")
    else:
        lines.append("> _Zero threats mitigated (All traffic clean)_")
    lines.append("")

    # 8. Cloudflare Web Analytics (RUM) Real Visitor Telemetry
    wa = m.web_analytics
    lines.append("### 8. Cloudflare Web Analytics (Real Visitor Acquisition)")
    lines.append("")
    lines.append(
        f"- **Total Client-Side Pageviews:** `{format_number(wa.total_pageviews)}`  \n"
        f"- **Total Client-Side Visits:** `{format_number(wa.total_visits)}`"
    )
    lines.append("")

    if wa.top_referrers:
        lines.append("#### Top Referring Sources (Cloudflare RUM)")
        lines.append("| Referring Source / Domain | Pageviews | Share |")
        lines.append("| :--- | ---: | ---: |")
        for ref in wa.top_referrers:
            lines.append(f"| `{ref.label}` | {ref.count_formatted} | {ref.share_pct} |")
        lines.append("")

    if wa.top_devices or wa.top_browsers:
        lines.append("#### Client Environments")
        lines.append("| Device Form Factor | Views | Share | Browser | Views | Share |")
        lines.append("| :--- | ---: | ---: | :--- | ---: | ---: |")
        max_rows = max(len(wa.top_devices), len(wa.top_browsers))
        for i in range(max_rows):
            d = wa.top_devices[i] if i < len(wa.top_devices) else None
            b = wa.top_browsers[i] if i < len(wa.top_browsers) else None
            d_str = f"{d.label} | {d.count_formatted} | {d.share_pct}" if d else " | | "
            b_str = f"{b.label} | {b.count_formatted} | {b.share_pct}" if b else " | | "
            lines.append(f"| {d_str} | {b_str} |")
        lines.append("")

    # 9. Vercel Top Referrers & Traffic Sources
    lines.append("### 9. Vercel Acquisition & Referrers")
    lines.append("")
    if not m.vercel.is_configured:
        lines.append("> ℹ️ _Set `VERCEL_TOKEN` to display real client-side acquisition sources from Vercel Web Analytics._")
    elif m.vercel.referrers:
        lines.append("| Traffic Source / Referrer | Visits |")
        lines.append("| :--- | ---: |")
        for r in m.vercel.referrers:
            lines.append(f"| `{r.label}` | {r.count_formatted} |")
    else:
        lines.append("> _Zero external referrers recorded during this period._")
    lines.append("")

    return "\n".join(lines)


def render_full_markdown_document(
    doc_title: str,
    sections: List[ReportSection],
) -> str:
    """Combine multiple report sections into a consolidated Markdown document."""
    header = [
        f"# {doc_title}",
        "",
        f"> Generated on {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')} using Cloudflare & Vercel Analytics Reporter v2.0",
        "",
        "---",
        "",
    ]
    section_texts = [render_markdown_section(s) for s in sections]
    return "\n".join(header) + "\n\n---\n\n".join(section_texts) + "\n"
