"""
Command-Line Interface and execution coordinator for Cloudflare & Vercel Reporting.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from .aggregator import aggregate_section
from .cloudflare.client import CloudflareClient
from .cloudflare.web_analytics import fetch_cloudflare_web_analytics
from .cloudflare.zone_analytics import fetch_all_zones
from .config import (
    CADENCE_DEFINITIONS,
    CF_ACCOUNT_ID,
    CF_API_TOKEN,
    TARGET_ALIASES,
    VERCEL_PROJECTS,
    VERCEL_TEAM_ID,
    VERCEL_TOKEN,
    ZONES,
    CadenceDefinition,
)
from .models import BreakdownItem, ReportSection, TimeWindow, VercelData
from .renderers.cli import render_cli_section
from .renderers.html import render_full_html_document
from .renderers.markdown import render_full_markdown_document
from .renderers.pdf import render_pdf
from .utils import calculate_time_window
from .vercel.client import VercelClient

logger = logging.getLogger("cf_report")


def build_parser() -> argparse.ArgumentParser:
    """Build argument parser with full CLI options."""
    parser = argparse.ArgumentParser(
        prog="report",
        description="Modular Cloudflare & Vercel Analytics Reporting Suite",
    )
    parser.add_argument(
        "target",
        nargs="?",
        default="all",
        help="Reporting period cadence: 24h, 48h, 4d, 7d, 30d, or all (default: all)",
    )
    parser.add_argument(
        "-o", "--output",
        help="Custom output file path (e.g. report.pdf or report.md)",
    )
    parser.add_argument(
        "--format",
        choices=["pdf", "markdown", "md", "html", "all"],
        default="pdf",
        help="Output format: pdf, markdown (md), html, or all (default: pdf)",
    )
    parser.add_argument(
        "--markdown", "--md",
        dest="markdown",
        action="store_true",
        help="Generate Markdown (.md) report file alongside or instead of PDF",
    )
    parser.add_argument(
        "--no-pdf",
        action="store_true",
        help="Skip PDF rendering and display terminal report only",
    )
    parser.add_argument(
        "--html-only",
        action="store_true",
        help="Generate and save HTML report without rendering to PDF",
    )
    parser.add_argument(
        "--no-parallel",
        action="store_true",
        help="Disable concurrent zone querying",
    )
    parser.add_argument(
        "--cf-token",
        help="Override Cloudflare API token",
    )
    parser.add_argument(
        "--cf-account",
        help="Override Cloudflare Account ID",
    )
    parser.add_argument(
        "--vercel-token",
        help="Override Vercel API token",
    )
    parser.add_argument(
        "--engine",
        choices=["weasyprint", "chromium", "google-chrome"],
        help="Select specific PDF rendering engine",
    )
    return parser


def process_section(
    cadence: CadenceDefinition,
    cf_client: CloudflareClient,
    vercel_client: VercelClient,
    parallel: bool = True,
    reference_dt: Optional[datetime] = None,
) -> ReportSection:
    """Query all APIs and construct an aggregated ReportSection."""
    window: TimeWindow = calculate_time_window(cadence, reference_dt)

    print("")
    print(f"\033[38;5;208m{'=' * 74}\033[0m")
    print(f"\033[1m==> Fetching [{cadence.display_label.upper()}] Data: {window.display_range}\033[0m")
    print(f"\033[38;5;208m{'=' * 74}\033[0m")

    # Progress reporter
    def on_progress(zone_name: str, success: bool) -> None:
        status_tag = "\033[32m[OK]\033[0m" if success else "\033[31m[FAILED]\033[0m"
        print(f"  -> Querying {zone_name:<22} {status_tag}")

    # 1. Fetch Cloudflare Zone Analytics
    raw_zones = fetch_all_zones(
        client=cf_client,
        zones=ZONES,
        window=window,
        parallel=parallel,
        on_progress=on_progress,
    )

    # 2. Fetch Cloudflare Web Analytics (RUM) for all sites
    print(f"  -> Querying Cloudflare Web Analytics (RUM)... ", end="", flush=True)
    web_analytics = fetch_cloudflare_web_analytics(cf_client, window)
    print("\033[32m[OK]\033[0m")

    # 3. Fetch Vercel Analytics (if configured)
    v_by_project: Dict[str, Dict] = {}
    v_total_views = 0
    v_total_vis = 0
    v_all_refs: Dict[str, int] = {}

    if vercel_client.is_configured:
        print(f"  -> Querying Vercel Web Analytics... ", end="", flush=True)
        for domain, proj_id in VERCEL_PROJECTS.items():
            stats = vercel_client.fetch_project_analytics(
                project_id=proj_id,
                from_ms=window.from_epoch_ms,
                to_ms=window.to_epoch_ms,
                since_iso=window.start_iso,
                until_iso=window.end_iso,
            )
            v_by_project[domain] = stats
            v_total_views += stats.get("pageviews", 0)
            v_total_vis += stats.get("visitors", 0)
            for r in stats.get("referrers", []):
                ref_name = r.get("referrer", "(direct / none)")
                v_all_refs[ref_name] = v_all_refs.get(ref_name, 0) + (r.get("count", 0) or 0)
        print("\033[32m[OK]\033[0m")

    vercel_referrers = [
        {"referrer": r, "count": cnt}
        for r, cnt in sorted(v_all_refs.items(), key=lambda x: x[1], reverse=True)[:8]
    ]

    v_ref_items = [
        BreakdownItem(
            key=r["referrer"],
            label=r["referrer"],
            count=r["count"],
            count_formatted=str(r["count"]),
        )
        for r in vercel_referrers
    ]

    vercel_data = VercelData(
        total_pageviews=v_total_views,
        total_visitors=v_total_vis,
        by_project=v_by_project,
        referrers=v_ref_items,
        is_configured=vercel_client.is_configured,
    )

    # 4. Probe referrers access
    has_pro = cf_client.probe_referrers_access(ZONES[0][0]) if ZONES else False

    # 5. Aggregate into SectionMetrics
    metrics = aggregate_section(
        raw_zones_data=raw_zones,
        web_analytics=web_analytics,
        vercel_data=vercel_data,
        window=window,
        has_pro_referrers=has_pro,
    )

    section = ReportSection(
        cadence_key=cadence.key,
        label=cadence.label,
        display_label=cadence.display_label,
        window=window,
        metrics=metrics,
    )

    # Print CLI terminal report
    render_cli_section(section)

    return section


def main(argv: Optional[List[str]] = None) -> int:
    """Main CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args(argv)

    target_key = TARGET_ALIASES.get(args.target.lower().strip())
    if not target_key:
        print(f"Error: Unknown cadence target '{args.target}'.", file=sys.stderr)
        print("Valid targets: 24h, 48h, 4d, 7d, 30d, all", file=sys.stderr)
        return 1

    # Initialize Clients
    cf_token = args.cf_token or CF_API_TOKEN
    cf_account = args.cf_account or CF_ACCOUNT_ID
    vercel_token = args.vercel_token or VERCEL_TOKEN
    parallel = not args.no_parallel

    if not cf_token:
        print(
            "Error: Cloudflare API token is not configured.\n"
            "Please set CF_API_TOKEN in .env.local, as an environment variable, or pass --cf-token.",
            file=sys.stderr,
        )
        return 1

    if not ZONES:
        print(
            "Error: No Cloudflare zones are configured.\n"
            "Please create a zones.yaml file (see zones.example.yaml) with your zone IDs and domains.",
            file=sys.stderr,
        )
        return 1

    cf_client = CloudflareClient(api_token=cf_token, account_id=cf_account)
    vercel_client = VercelClient(token=vercel_token, team_id=VERCEL_TEAM_ID)

    timestamp_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    reference_now = datetime.now(timezone.utc)

    if target_key == "all":
        print("")
        print(f"\033[38;5;208m{'=' * 74}\033[0m")
        print(f"\033[1m==> Generating Consolidated Report (All 5 Periods)\033[0m")
        print(f"\033[38;5;208m{'=' * 74}\033[0m")

        sections: List[ReportSection] = []
        for cadence in CADENCE_DEFINITIONS:
            sec = process_section(
                cadence=cadence,
                cf_client=cf_client,
                vercel_client=vercel_client,
                parallel=parallel,
                reference_dt=reference_now,
            )
            sections.append(sec)

        doc_title = "Cloudflare Analytics - Consolidated Report"
        base_name = f"cloudflare_report_consolidated_{timestamp_str}"
    else:
        cadence = next(c for c in CADENCE_DEFINITIONS if c.key == target_key)
        sec = process_section(
            cadence=cadence,
            cf_client=cf_client,
            vercel_client=vercel_client,
            parallel=parallel,
            reference_dt=reference_now,
        )
        sections = [sec]
        doc_title = f"Cloudflare Analytics - {cadence.display_label}"
        base_name = f"cloudflare_report_{cadence.label}_{timestamp_str}"

    # Determine desired formats
    out_arg = args.output
    is_out_md = out_arg and out_arg.endswith(".md")
    is_out_html = out_arg and out_arg.endswith(".html")

    generate_markdown = args.markdown or args.format in ("markdown", "md", "all") or is_out_md
    generate_html = args.html_only or args.format in ("html", "all") or is_out_html
    generate_pdf = (not args.no_pdf) and (args.format in ("pdf", "all")) and (not is_out_md) and (not is_out_html) and (not args.html_only)

    # 1. Markdown generation
    if generate_markdown:
        md_content = render_full_markdown_document(doc_title=doc_title, sections=sections)
        md_file = Path(out_arg if is_out_md else f"{base_name}.md")
        md_file.write_text(md_content, encoding="utf-8")
        print(f"\n  \033[32m==> Generated Markdown Report: {md_file}\033[0m")

    # 2. HTML & PDF generation
    if generate_html or generate_pdf:
        full_html = render_full_html_document(doc_title=doc_title, sections=sections)

        if generate_html:
            html_file = Path(out_arg if is_out_html else f"{base_name}.html")
            html_file.write_text(full_html, encoding="utf-8")
            print(f"  \033[32m==> Saved HTML Report: {html_file}\033[0m")

        if generate_pdf:
            pdf_path = Path(out_arg) if (out_arg and not is_out_md and not is_out_html) else Path(f"{base_name}.pdf")
            success = render_pdf(
                html_content=full_html,
                output_pdf_path=pdf_path,
                prefer_engine=args.engine,
            )
            if not success:
                print("Warning: PDF generation failed.", file=sys.stderr)
                return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
