"""
Unit tests for the Cloudflare & Vercel Analytics reporting package.
"""

import unittest
from datetime import datetime, timezone
from cf_report.config import CADENCE_DEFINITIONS, CadenceDefinition
from cf_report.models import (
    BreakdownItem,
    CloudflareWebAnalyticsData,
    ReportSection,
    SectionMetrics,
    TimeWindow,
    VercelData,
    ZoneReportItem,
    ZoneRollup,
)
from cf_report.utils import (
    calculate_time_window,
    format_bytes,
    format_number,
    format_percent,
    get_country_name,
)
from cf_report.cloudflare.web_analytics import match_zone_web_analytics
from cf_report.aggregator import aggregate_section
from cf_report.renderers.markdown import render_markdown_section
from cf_report.renderers.html import render_html_section


class TestFormattingUtils(unittest.TestCase):
    def test_format_bytes(self):
        self.assertEqual(format_bytes(500), "500 B")
        self.assertEqual(format_bytes(1024), "1.00 KiB")
        self.assertEqual(format_bytes(1048576), "1.00 MiB")
        self.assertEqual(format_bytes(1073741824), "1.00 GiB")
        self.assertEqual(format_bytes(1500000000), "1.40 GiB")
        self.assertEqual(format_bytes(0), "0 B")
        self.assertEqual(format_bytes(None), "0 B")

    def test_format_number(self):
        self.assertEqual(format_number(1000), "1,000")
        self.assertEqual(format_number(1234567), "1,234,567")
        self.assertEqual(format_number(None), "-")

    def test_format_percent(self):
        self.assertEqual(format_percent(5, 100), "5.0%")
        self.assertEqual(format_percent(1, 3, decimals=2), "33.33%")
        self.assertEqual(format_percent(0, 0), "0.0%")

    def test_get_country_name(self):
        self.assertEqual(get_country_name("US"), "United States")
        self.assertEqual(get_country_name("NL"), "Netherlands")
        self.assertEqual(get_country_name("XYZ"), "XYZ")


class TestTimeWindow(unittest.TestCase):
    def test_hourly_window(self):
        ref_dt = datetime(2026, 10, 20, 12, 0, 0, tzinfo=timezone.utc)
        cadence = CADENCE_DEFINITIONS[0]  # 24h
        window = calculate_time_window(cadence, ref_dt)
        self.assertEqual(window.mode, "hourly")
        self.assertEqual(window.start_iso, "2026-10-19T12:00:00Z")
        self.assertEqual(window.end_iso, "2026-10-20T12:00:00Z")

    def test_daily_window(self):
        ref_dt = datetime(2026, 10, 20, 12, 0, 0, tzinfo=timezone.utc)
        cadence = next(c for c in CADENCE_DEFINITIONS if c.key == "7d")
        window = calculate_time_window(cadence, ref_dt)
        self.assertEqual(window.mode, "daily")
        self.assertEqual(window.since_date, "2026-10-13")
        self.assertEqual(window.until_date, "2026-10-19")
        self.assertEqual(window.since_dt, "2026-10-13T00:00:00Z")
        self.assertEqual(window.until_dt, "2026-10-19T23:59:59Z")


class TestWebAnalyticsMatching(unittest.TestCase):
    def test_match_zone_web_analytics(self):
        rum_data = CloudflareWebAnalyticsData(
            total_pageviews=50,
            total_visits=30,
            by_host={
                "tehwiz.com": {"pageviews": 10, "visits": 5},
                "www.tehwiz.com": {"pageviews": 20, "visits": 15},
                "sub.tehwiz.com": {"pageviews": 5, "visits": 2},
                "otherdomain.com": {"pageviews": 15, "visits": 8},
            },
        )
        views, visits = match_zone_web_analytics("tehwiz.com", rum_data)
        self.assertEqual(views, 35)
        self.assertEqual(visits, 22)

        views_other, visits_other = match_zone_web_analytics("otherdomain.com", rum_data)
        self.assertEqual(views_other, 15)
        self.assertEqual(visits_other, 8)

        views_none, visits_none = match_zone_web_analytics("unknown.com", rum_data)
        self.assertEqual(views_none, 0)
        self.assertEqual(visits_none, 0)


class TestAggregationAndRendering(unittest.TestCase):
    def test_aggregate_and_render_markdown(self):
        window = TimeWindow(
            mode="hourly",
            start_iso="2026-10-19T12:00:00Z",
            end_iso="2026-10-20T12:00:00Z",
            display_range="2026-10-19 12:00 UTC to 2026-10-20 12:00 UTC",
            from_epoch_ms=0,
            to_epoch_ms=0,
            since_dt="2026-10-19T12:00:00Z",
            until_dt="2026-10-20T12:00:00Z",
        )

        raw_zones = [{
            "zone_id": "zone123",
            "zone_name": "example.com",
            "rollup": ZoneRollup(
                requests=1000,
                bytes=2048000,
                cached_requests=250,
                cached_bytes=512000,
                threats=10,
                page_views=300,
            ),
            "subdomains": [{
                "dimensions": {"clientRequestHTTPHost": "example.com"},
                "count": 1000,
                "sum": {"edgeResponseBytes": 2048000},
            }],
            "countries": [{
                "dimensions": {"clientCountryName": "US"},
                "count": 1000,
                "sum": {"edgeResponseBytes": 2048000},
            }],
            "paths": [{"dimensions": {"clientRequestPath": "/"}, "count": 1000}],
            "probes": [],
            "statuses": [{"dimensions": {"edgeResponseStatus": 200}, "count": 1000}],
            "caching": [{"dimensions": {"cacheStatus": "hit"}, "count": 250, "sum": {"edgeResponseBytes": 512000}}],
            "protocols": [{"dimensions": {"clientRequestHTTPProtocol": "HTTP/2", "clientSSLProtocol": "TLSv1.3"}, "count": 1000}],
            "security": [{"dimensions": {"securityAction": "block", "securitySource": "firewallCustom"}, "count": 10}],
        }]

        rum_data = CloudflareWebAnalyticsData(
            total_pageviews=50,
            total_visits=25,
            by_host={"example.com": {"pageviews": 50, "visits": 25}},
            top_referrers=[BreakdownItem(key="google.com", label="google.com", count=50, count_formatted="50", share_pct="100.0%")],
            top_devices=[BreakdownItem(key="Desktop", label="Desktop", count=50, count_formatted="50", share_pct="100.0%")],
            top_browsers=[BreakdownItem(key="Chrome", label="Chrome", count=50, count_formatted="50", share_pct="100.0%")],
        )

        vercel_data = VercelData(is_configured=False)

        metrics = aggregate_section(raw_zones, rum_data, vercel_data, window)
        self.assertEqual(metrics.total_requests, 1000)
        self.assertEqual(metrics.total_cf_web_views, 50)
        self.assertEqual(metrics.total_cf_web_visits, 25)
        self.assertEqual(metrics.avg_cache_ratio, "25.0%")

        section = ReportSection(
            cadence_key="24h",
            label="last_24_hours",
            display_label="Last 24 Hours",
            window=window,
            metrics=metrics,
        )

        md = render_markdown_section(section)
        self.assertIn("# Cloudflare Portfolio Analytics — Last 24 Hours", md)
        self.assertIn("CF Web Views (RUM)", md)
        self.assertIn("google.com", md)

        html = render_html_section(section)
        self.assertIn("CF Web Views", html)
        self.assertIn("example.com", html)


if __name__ == "__main__":
    unittest.main()
