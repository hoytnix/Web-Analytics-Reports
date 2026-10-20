"""
Unit tests for Gemini AI integration and cascading fallback strategy.
"""

import unittest
from unittest.mock import MagicMock, patch
import requests

from cf_report.config import CADENCE_DEFINITIONS
from cf_report.gemini.client import DEFAULT_MODELS_CASCADE, GeminiClient
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
from cf_report.renderers.html import render_html_section
from cf_report.renderers.markdown import render_markdown_section
from cf_report.utils import markdown_to_html


def _create_mock_metrics() -> SectionMetrics:
    from cf_report.aggregator import aggregate_section

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
        "zone_id": "zone1",
        "zone_name": "example.com",
        "rollup": ZoneRollup(
            requests=5000,
            bytes=10485760,
            cached_requests=4000,
            cached_bytes=8388608,
            threats=5,
            page_views=1500,
        ),
        "subdomains": [{"dimensions": {"clientRequestHTTPHost": "example.com"}, "count": 5000, "sum": {"edgeResponseBytes": 10485760}}],
        "countries": [{"dimensions": {"clientCountryName": "US"}, "count": 5000, "sum": {"edgeResponseBytes": 10485760}}],
        "paths": [{"dimensions": {"clientRequestPath": "/api"}, "count": 3000}],
        "probes": [],
        "statuses": [{"dimensions": {"edgeResponseStatus": 200}, "count": 5000}],
        "caching": [{"dimensions": {"cacheStatus": "hit"}, "count": 4000, "sum": {"edgeResponseBytes": 8388608}}],
        "protocols": [{"dimensions": {"clientRequestHTTPProtocol": "HTTP/3", "clientSSLProtocol": "TLSv1.3"}, "count": 5000}],
        "security": [{"dimensions": {"securityAction": "block", "securitySource": "firewallCustom"}, "count": 5}],
    }]
    rum = CloudflareWebAnalyticsData(
        total_pageviews=1200,
        total_visits=800,
        by_host={"example.com": {"pageviews": 1200, "visits": 800}},
        top_referrers=[BreakdownItem(key="google.com", label="google.com", count=500)],
    )
    vercel = VercelData(is_configured=False)
    return aggregate_section(raw_zones, rum, vercel, window)


class TestMarkdownToHtml(unittest.TestCase):
    def test_empty_string(self):
        self.assertEqual(markdown_to_html(""), "")
        self.assertEqual(markdown_to_html(None), "")

    def test_paragraph_formatting(self):
        md = "This is a **bold** statement and *italic* note with `code`."
        html = markdown_to_html(md)
        self.assertIn("<p>This is a <strong>bold</strong> statement and <em>italic</em> note with <code>code</code>.</p>", html)

    def test_headers_and_lists(self):
        md = """### Executive Overview
Portfolio traffic was steady.

- Key point 1: High cache hit ratio
- Key point 2: Zero origin errors
"""
        html = markdown_to_html(md)
        self.assertIn("Executive Overview</h4>", html)
        self.assertIn("<p>Portfolio traffic was steady.</p>", html)
        self.assertIn("<ul>", html)
        self.assertIn("<li>Key point 1: High cache hit ratio</li>", html)
        self.assertIn("<li>Key point 2: Zero origin errors</li>", html)
        self.assertIn("</ul>", html)


class TestGeminiClientCascadingFallback(unittest.TestCase):
    def setUp(self):
        self.metrics = _create_mock_metrics()
        self.cadence = CADENCE_DEFINITIONS[0]
        self.window = TimeWindow(
            mode="hourly",
            start_iso="2026-10-19T12:00:00Z",
            end_iso="2026-10-20T12:00:00Z",
            display_range="2026-10-19 12:00 UTC to 2026-10-20 12:00 UTC",
            from_epoch_ms=0,
            to_epoch_ms=0,
        )

    def test_is_configured(self):
        client_empty = GeminiClient(api_key="")
        self.assertFalse(client_empty.is_configured)
        self.assertIsNone(client_empty.generate_executive_brief(self.cadence, self.window, self.metrics))

        client_configured = GeminiClient(api_key="valid-test-key")
        self.assertTrue(client_configured.is_configured)

    def test_default_models_cascade_order(self):
        self.assertEqual(
            DEFAULT_MODELS_CASCADE,
            ["gemini-3.8-flash", "gemini-3.5-flash-lite", "gemini-3.5-flash"],
        )

    @patch("cf_report.gemini.client.requests.post")
    def test_first_model_succeeds(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": "Executive Brief from Gemini 3.8 Flash."}]
                    }
                }
            ]
        }
        mock_post.return_value = mock_resp

        client = GeminiClient(api_key="test-key")
        brief = client.generate_executive_brief(self.cadence, self.window, self.metrics)

        self.assertEqual(brief, "Executive Brief from Gemini 3.8 Flash.")
        self.assertEqual(client.last_model_used, "gemini-3.8-flash")
        self.assertEqual(mock_post.call_count, 1)
        self.assertIn("gemini-3.8-flash", mock_post.call_args[0][0])

    @patch("cf_report.gemini.client.requests.post")
    def test_fallback_to_second_model(self, mock_post):
        # 1st call fails (HTTP 404 or 500)
        resp1 = MagicMock()
        resp1.status_code = 404
        resp1.json.return_value = {"error": {"message": "Model gemini-3.8-flash not found"}}

        # 2nd call succeeds (gemini-3.5-flash-lite)
        resp2 = MagicMock()
        resp2.status_code = 200
        resp2.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": "Executive Brief from Gemini 3.5 Flash-Lite."}]
                    }
                }
            ]
        }
        mock_post.side_effect = [resp1, resp2]

        client = GeminiClient(api_key="test-key")
        attempts = []

        def on_attempt(model, success, err):
            attempts.append((model, success))

        brief = client.generate_executive_brief(
            self.cadence, self.window, self.metrics, on_attempt=on_attempt
        )

        self.assertEqual(brief, "Executive Brief from Gemini 3.5 Flash-Lite.")
        self.assertEqual(client.last_model_used, "gemini-3.5-flash-lite")
        self.assertEqual(mock_post.call_count, 2)
        self.assertEqual(attempts, [("gemini-3.8-flash", False), ("gemini-3.5-flash-lite", True)])

    @patch("cf_report.gemini.client.requests.post")
    def test_fallback_to_third_model(self, mock_post):
        # 1st call raises RequestException
        # 2nd call returns 429 Rate Limit
        # 3rd call succeeds with gemini-3.5-flash
        resp2 = MagicMock()
        resp2.status_code = 429
        resp2.json.return_value = {"error": {"message": "Resource exhausted"}}

        resp3 = MagicMock()
        resp3.status_code = 200
        resp3.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": "Executive Brief from Gemini 3.5 Flash."}]
                    }
                }
            ]
        }
        mock_post.side_effect = [
            requests.RequestException("Connection timed out"),
            resp2,
            resp3,
        ]

        client = GeminiClient(api_key="test-key")
        brief = client.generate_executive_brief(self.cadence, self.window, self.metrics)

        self.assertEqual(brief, "Executive Brief from Gemini 3.5 Flash.")
        self.assertEqual(client.last_model_used, "gemini-3.5-flash")
        self.assertEqual(mock_post.call_count, 3)

    @patch("cf_report.gemini.client.requests.post")
    def test_all_models_fail(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 503
        mock_resp.json.return_value = {"error": {"message": "Service unavailable"}}
        mock_post.return_value = mock_resp

        client = GeminiClient(api_key="test-key")
        brief = client.generate_executive_brief(self.cadence, self.window, self.metrics)

        self.assertIsNone(brief)
        self.assertEqual(mock_post.call_count, 3)

    @patch("cf_report.gemini.client.requests.post")
    def test_thinking_tokens_filtered_out(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"thought": True, "text": "Analyzing metrics and zone patterns..."},
                            {"thought": False, "text": "Final Executive Brief for leadership."},
                        ]
                    }
                }
            ]
        }
        mock_post.return_value = mock_resp

        client = GeminiClient(api_key="test-key")
        brief = client.generate_executive_brief(self.cadence, self.window, self.metrics)

        self.assertEqual(brief, "Final Executive Brief for leadership.")


class TestReportSectionWithBrief(unittest.TestCase):
    def test_rendering_with_executive_brief(self):
        metrics = _create_mock_metrics()
        window = TimeWindow(
            mode="hourly",
            start_iso="2026-10-19T12:00:00Z",
            end_iso="2026-10-20T12:00:00Z",
            display_range="2026-10-19 12:00 UTC to 2026-10-20 12:00 UTC",
            from_epoch_ms=0,
            to_epoch_ms=0,
        )
        brief_text = "**Executive Overview**: Healthy network activity.\n\n- Key traffic driver: example.com"
        section = ReportSection(
            cadence_key="24h",
            label="last_24_hours",
            display_label="Last 24 Hours",
            window=window,
            metrics=metrics,
            executive_brief=brief_text,
        )

        # Markdown rendering check
        md = render_markdown_section(section)
        self.assertIn("## Executive Brief", md)
        self.assertIn("Healthy network activity.", md)
        # Verify Executive Brief is placed at the end after results
        self.assertGreater(md.index("## Executive Brief"), md.index("### 9. Vercel Acquisition"))

        # HTML rendering check
        html = render_html_section(section)
        self.assertIn("Executive Brief", html)
        self.assertIn("Healthy network activity.", html)
        self.assertIn("<li>Key traffic driver: example.com</li>", html)
        self.assertIn("brief-wrapper", html)
        # Verify brief is on its own page after the breakdown results
        self.assertGreater(html.index("brief-wrapper"), html.index("breakdown-wrapper"))


class TestCliGeminiIntegration(unittest.TestCase):
    @patch("cf_report.cli.VercelClient")
    @patch("cf_report.cli.fetch_all_zones")
    @patch("cf_report.cli.fetch_cloudflare_web_analytics")
    @patch("cf_report.cli.render_pdf")
    def test_consolidated_generates_brief_per_timeframe(
        self, mock_pdf, mock_web_analytics, mock_zones, mock_vercel
    ):
        from cf_report.cli import main

        mock_zones.return_value = []
        mock_web_analytics.return_value = CloudflareWebAnalyticsData()
        mock_pdf.return_value = True
        mock_vercel.return_value.is_configured = False

        mock_gemini = MagicMock()
        mock_gemini.is_configured = True
        mock_gemini.last_model_used = "gemini-3.8-flash"
        mock_gemini.generate_executive_brief.side_effect = [
            "Brief for 24h",
            "Brief for 48h",
            "Brief for 4d",
            "Brief for 7d",
            "Brief for 30d",
        ]

        with patch("cf_report.cli.GeminiClient", return_value=mock_gemini):
            with patch("cf_report.cli.ZONES", [("zone1", "test.com")]):
                with patch("cf_report.cli.CF_API_TOKEN", "mock-token"):
                    code = main(["all", "--no-pdf", "--gemini-key", "test-key"])
                    self.assertEqual(code, 0)
                    # For consolidated report, it must generate an executive brief for all 5 timeframes
                    self.assertEqual(mock_gemini.generate_executive_brief.call_count, 5)

    @patch("cf_report.cli.VercelClient")
    @patch("cf_report.cli.fetch_all_zones")
    @patch("cf_report.cli.fetch_cloudflare_web_analytics")
    def test_no_gemini_key_skips_brief(self, mock_web_analytics, mock_zones, mock_vercel):
        from cf_report.cli import main

        mock_zones.return_value = []
        mock_web_analytics.return_value = CloudflareWebAnalyticsData()
        mock_vercel.return_value.is_configured = False

        mock_gemini = MagicMock()
        mock_gemini.is_configured = False

        with patch("cf_report.cli.GeminiClient", return_value=mock_gemini):
            with patch("cf_report.cli.ZONES", [("zone1", "test.com")]):
                with patch("cf_report.cli.CF_API_TOKEN", "mock-token"):
                    with patch("cf_report.cli.GEMINI_API_KEY", ""):
                        code = main(["24h", "--no-pdf"])
                        self.assertEqual(code, 0)
                        mock_gemini.generate_executive_brief.assert_not_called()


if __name__ == "__main__":
    unittest.main()

