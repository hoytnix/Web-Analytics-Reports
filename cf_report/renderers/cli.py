"""
CLI Terminal Renderer with ANSI color formatting.
"""

from __future__ import annotations

import os
import sys
from typing import List

from ..models import ReportSection, SectionMetrics
from ..utils import format_bytes, format_number


class Colors:
    """ANSI color definitions with NO_COLOR awareness."""

    def __init__(self):
        use_color = sys.stdout.isatty() and os.environ.get("NO_COLOR", "0") != "1"
        self.BOLD = "\033[1m" if use_color else ""
        self.DIM = "\033[2m" if use_color else ""
        self.RESET = "\033[0m" if use_color else ""
        self.RED = "\033[31m" if use_color else ""
        self.GREEN = "\033[32m" if use_color else ""
        self.YELLOW = "\033[33m" if use_color else ""
        self.BLUE = "\033[34m" if use_color else ""
        self.MAGENTA = "\033[35m" if use_color else ""
        self.CYAN = "\033[36m" if use_color else ""
        self.WHITE = "\033[37m" if use_color else ""
        self.ORANGE = "\033[38;5;208m" if use_color else ""
        self.GRAY = "\033[90m" if use_color else ""


c = Colors()


def render_cli_section(section: ReportSection) -> None:
    """Print beautifully formatted report section to standard output."""
    m: SectionMetrics = section.metrics

    print("")
    print(f"{c.ORANGE}================================================================================{c.RESET}")
    print(f"{c.BOLD}==> Fetching [{section.display_label.upper()}] Data: {section.window.display_range}{c.RESET}")
    print(f"{c.ORANGE}================================================================================{c.RESET}")

    print("")
    print(f"{c.BOLD}{c.CYAN}--------------------------------------------------------------------------------{c.RESET}")
    print(f"{c.BOLD}{c.WHITE}CLOUDFLARE PORTFOLIO REPORT — [{section.display_label.upper()}]{c.RESET}")
    print(f"{c.DIM}Range: {section.window.display_range} | {len(m.zone_items)} Zones Monitored{c.RESET}")
    print(f"{c.BOLD}{c.CYAN}--------------------------------------------------------------------------------{c.RESET}")

    # Primary KPI Summary Grid
    cf_req_fmt = format_number(m.total_requests)
    cf_thr_fmt = format_number(m.total_threats)
    cf_web_views_fmt = format_number(m.total_cf_web_views)
    cf_web_vis_fmt = format_number(m.total_cf_web_visits)
    v_views_fmt = format_number(m.total_vercel_views) if m.vercel.is_configured else "-"
    v_vis_fmt = format_number(m.total_vercel_visitors) if m.vercel.is_configured else "-"

    print(
        f"  {c.BOLD}{'CF Requests:':<18}{c.RESET} {cf_req_fmt:<12} | "
        f"{c.BOLD}{'CF Avg Cache:':<16}{c.RESET} {m.avg_cache_ratio:<10} | "
        f"{c.BOLD}{'CF Threats:':<16}{c.RESET} {cf_thr_fmt}"
    )
    print(
        f"  {c.BOLD}{'CF Bandwidth:':<18}{c.RESET} {format_bytes(m.total_bytes):<12} | "
        f"{c.BOLD}{'CF Web Views:':<16}{c.RESET} {cf_web_views_fmt:<10} | "
        f"{c.BOLD}{'CF Web Visits:':<16}{c.RESET} {cf_web_vis_fmt}"
    )
    print(
        f"  {c.BOLD}{'CF Cached BW:':<18}{c.RESET} {format_bytes(m.cached_bytes):<12} | "
        f"{c.BOLD}{'Vercel Views:':<16}{c.RESET} {v_views_fmt:<10} | "
        f"{c.BOLD}{'Vercel Visitors:':<16}{c.RESET} {v_vis_fmt}"
    )
    print("")

    # 1. Subdomains
    print(f"  {c.BOLD}{c.BLUE}1. TOP SUBDOMAINS (HOSTNAMES){c.RESET}")
    print(f"     {'HOSTNAME':<34} {'REQUESTS':>10} {'SHARE':>8} {'BANDWIDTH':>12}")
    for item in m.subdomains:
        print(f"     {item.label[:34]:<34} {item.count_formatted:>10} {item.share_pct:>8} {item.bytes_formatted:>12}")
    print("")

    # 2. Countries
    print(f"  {c.BOLD}{c.GREEN}2. GEOGRAPHIC DISTRIBUTION (TOP COUNTRIES){c.RESET}")
    print(f"     {'CODE':<6} {'COUNTRY':<26} {'REQUESTS':>10} {'SHARE':>8} {'BANDWIDTH':>12}")
    for item in m.countries:
        print(f"     {item.key:<6} {item.label[:26]:<26} {item.count_formatted:>10} {item.share_pct:>8} {item.bytes_formatted:>12}")
    print("")

    # 3. HTTP Status Codes & Origin Health
    sh = m.status_health
    print(f"  {c.BOLD}{c.MAGENTA}3. HTTP STATUS CODES & HEALTH{c.RESET}")
    print(f"     2xx: {sh.s2xx.count_formatted} ({sh.s2xx.share_pct}){'':<6} 3xx: {sh.s3xx.count_formatted} ({sh.s3xx.share_pct})")
    print(f"     4xx: {sh.s4xx.count_formatted} ({sh.s4xx.share_pct}){'':<6} 5xx: {sh.s5xx.count_formatted} ({sh.s5xx.share_pct})")
    health_status = "HEALTHY" if sh.is_healthy else "MONITOR"
    print(f"     Origin 5xx Error Rate: {sh.origin_error_rate} [Health: {health_status}]")
    print("")

    # 4. Cache Efficiency
    ce = m.cache_efficiency
    print(f"  {c.BOLD}{c.YELLOW}4. CACHE EFFICIENCY & SAVINGS{c.RESET}")
    print(f"     Request CHR: {ce.req_hit_ratio:<10}  Bandwidth CHR: {ce.bytes_hit_ratio:<10}  Saved BW: {ce.saved_bytes}")
    print("")

    # 5. Top Request Paths & Probe Endpoints
    print(f"  {c.BOLD}{c.ORANGE}5. TOP VISITED PATHS & PROBES{c.RESET}")
    print(f"     {'TOP VISITED ENDPOINT':<40} {'REQS':>6} | {'SUSPICIOUS PROBE (404/403)':<34} {'REQS':>6}")
    max_rows = max(len(m.paths), len(m.probes), 5)
    for i in range(max_rows):
        p_str = f"{m.paths[i].label[:32]} ({m.paths[i].count_formatted})" if i < len(m.paths) else ""
        pr_str = f"{m.probes[i].path[:28]} ({m.probes[i].count_formatted})" if i < len(m.probes) else ""
        if p_str or pr_str:
            print(f"     {p_str:<47} | {pr_str}")
    print("")

    # 6. Protocols & TLS
    pr = m.protocols
    print(f"  {c.BOLD}{c.CYAN}6. CLIENT PROTOCOLS & ENCRYPTION{c.RESET}")
    print(f"     HTTP/3 (QUIC) Adoption: {pr.h3_adoption:<10}  TLS 1.3 Modern Adoption: {pr.tls13_adoption}")
    print("")

    # 7. Security & Threat Mitigation
    sec = m.security
    print(f"  {c.BOLD}{c.RED}7. SECURITY & THREAT MITIGATION{c.RESET}")
    print(f"     Threats Mitigated: {sec.total_threats_formatted}")
    for item in sec.breakdown:
        if item.action != "unknown":
            print(f"     Action: {item.action} ({item.source}) -> {item.count_formatted} events")
    print("")

    # 8. Cloudflare Web Analytics (RUM) Real Traffic
    wa = m.web_analytics
    print(f"  {c.BOLD}{c.BLUE}8. CLOUDFLARE WEB ANALYTICS (REAL VISITOR TRAFFIC){c.RESET}")
    print(f"     Total Pageviews: {cf_web_views_fmt:<10} Total Visits: {cf_web_vis_fmt}")

    if wa.top_referrers:
        print(f"     {c.DIM}--- Top Referring Sources (CF Web Analytics) ---{c.RESET}")
        print(f"     {'REFERRING SOURCE':<46} {'PAGEVIEWS':>10}")
        for ref in wa.top_referrers[:6]:
            print(f"     {ref.label[:46]:<46} {ref.count_formatted:>10}")

    if wa.top_devices or wa.top_browsers:
        dev_str = " | ".join(f"{d.label}: {d.count_formatted}" for d in wa.top_devices[:3])
        br_str = " | ".join(f"{b.label}: {b.count_formatted}" for b in wa.top_browsers[:4])
        print(f"     {c.DIM}Devices: {dev_str}{c.RESET}")
        print(f"     {c.DIM}Browsers: {br_str}{c.RESET}")
    print("")

    # 9. Vercel Traffic Acquisition
    print(f"  {c.BOLD}{c.MAGENTA}9. VERCEL TOP REFERRERS & TRAFFIC SOURCES{c.RESET}")
    if not m.vercel.is_configured:
        print(f"     {c.DIM}[Export VERCEL_TOKEN to populate real Vercel acquisition sources]{c.RESET}")
    elif not m.vercel.referrers:
        print(f"     No external referrer visits recorded in this period.")
    else:
        print(f"     {'REFERRING SOURCE / DOMAIN':<46} {'VISITS':>8}")
        for r in m.vercel.referrers[:8]:
            print(f"     {r.label[:46]:<46} {r.count_formatted:>8}")

    print(f"{c.BOLD}{c.CYAN}--------------------------------------------------------------------------------{c.RESET}")
