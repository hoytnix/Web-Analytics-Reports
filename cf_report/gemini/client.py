"""
Gemini AI Client with cascading model fallback for generating analytical Executive Briefs.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, Tuple
import requests

from ..config import CadenceDefinition
from ..models import SectionMetrics, TimeWindow
from ..utils import format_bytes, format_number

logger = logging.getLogger("cf_report.gemini")

DEFAULT_MODELS_CASCADE: List[str] = [
    "gemini-3.8-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
]

API_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiClient:
    """
    Client for interacting with Google's Gemini models via the Generative Language REST API.
    Executes a cascading fallback strategy:
      1. gemini-3.8-flash
      2. gemini-3.5-flash-lite
      3. gemini-3.5-flash
    """

    def __init__(
        self,
        api_key: str = "",
        models: Optional[List[str]] = None,
        timeout: int = 30,
    ) -> None:
        self.api_key = (api_key or "").strip()
        self.models = list(models) if models is not None else list(DEFAULT_MODELS_CASCADE)
        self.timeout = timeout
        self.last_model_used: Optional[str] = None

    @property
    def is_configured(self) -> bool:
        """Return True if a non-empty API key is configured."""
        return bool(self.api_key)

    def _build_prompt(
        self,
        cadence: CadenceDefinition,
        window: TimeWindow,
        metrics: SectionMetrics,
    ) -> str:
        """Construct a structured, data-grounded prompt for the executive brief."""
        # Top zones summary
        sorted_zones = sorted(metrics.zone_items, key=lambda z: z.requests, reverse=True)
        top_zones_summary: List[str] = [
            f"  - {z.zone_name}: {z.requests:,} reqs | {z.hit_ratio} cached | {format_bytes(z.bytes)} | {z.cf_threats} threats | "
            f"CF RUM views: {format_number(z.cf_web_views)} | Vercel views: {format_number(z.vercel_views)}"
            for z in sorted_zones[:6]
        ]

        top_countries = [f"{c.label} ({c.share_pct})" for c in metrics.countries[:5]]
        top_paths = [f"{p.label} ({p.count:,} reqs)" for p in metrics.paths[:5]]
        top_probes = [f"{pr.path} [HTTP {pr.status}] ({pr.count:,} reqs)" for pr in metrics.probes[:5]]
        threats_summary = [f"{s.action} via {s.source} ({s.count:,})" for s in metrics.security.breakdown[:4]]
        cf_refs = [f"{r.label} ({r.count:,} views)" for r in metrics.web_analytics.top_referrers[:4]]
        vercel_refs = [f"{r.label} ({r.count:,} visits)" for r in metrics.vercel.referrers[:4]]

        zones_block = "\n".join(top_zones_summary) if top_zones_summary else "  - No active zones recorded"
        countries_block = ", ".join(top_countries) if top_countries else "N/A"
        paths_block = ", ".join(top_paths) if top_paths else "N/A"
        probes_block = ", ".join(top_probes) if top_probes else "None detected"
        threats_block = ", ".join(threats_summary) if threats_summary else "Zero threats mitigated"
        cf_refs_block = ", ".join(cf_refs) if cf_refs else "Direct / Unspecified"
        vercel_refs_block = ", ".join(vercel_refs) if vercel_refs else "Direct / None"

        prompt = f"""You are a senior infrastructure, cloud operations, and security analyst. Provide a high-level, executive-ready analytical brief summarizing portfolio traffic, performance, and security for the following reporting timeframe.

### REPORTING TIMEFRAME:
- Cadence: {cadence.display_label}
- Interval: {window.display_range}

### PORTFOLIO HIGH-LEVEL KPIS:
- Total Cloudflare Requests: {format_number(metrics.total_requests)}
- Average Cache Hit Ratio: {metrics.avg_cache_ratio}
- Total Bandwidth: {format_bytes(metrics.total_bytes)} (Cached: {format_bytes(metrics.cached_bytes)} | Saved: {metrics.cache_efficiency.saved_bytes})
- Edge Pageviews: {format_number(metrics.total_cf_views)}
- Mitigated Threats: {format_number(metrics.total_threats)}
- Cloudflare Web Analytics (RUM): {format_number(metrics.total_cf_web_views)} pageviews, {format_number(metrics.total_cf_web_visits)} visits
- Vercel Web Analytics: {format_number(metrics.total_vercel_views)} pageviews, {format_number(metrics.total_vercel_visitors)} visitors
- Origin 5xx Error Rate: {metrics.status_health.origin_error_rate} (Health Status: {'Healthy' if metrics.status_health.is_healthy else 'Attention Required'})
- HTTP Status Distribution: 2xx: {metrics.status_health.s2xx.share_pct}, 3xx: {metrics.status_health.s3xx.share_pct}, 4xx: {metrics.status_health.s4xx.share_pct}, 5xx: {metrics.status_health.s5xx.share_pct}
- Modern Protocol Adoption: HTTP/3: {metrics.protocols.h3_adoption}, TLS 1.3: {metrics.protocols.tls13_adoption}

### ACTIVE MONITORED ZONES ({len(metrics.zone_items)} TOTAL):
{zones_block}

### TRAFFIC & SECURITY TELEMETRY:
- Top Geographic Origins: {countries_block}
- Top Requested Endpoints: {paths_block}
- Suspicious Probes / Scanners (404/403): {probes_block}
- Security Events Mitigated: {threats_block}
- Acquisition Referrers (CF RUM): {cf_refs_block}
- Acquisition Referrers (Vercel): {vercel_refs_block}

### INSTRUCTIONS:
Generate a concise, impactful executive brief (150 to 250 words) structured into three distinct sections:
1. **Executive Overview**: A 2-sentence narrative of portfolio traffic volume, key drivers, and overall health status.
2. **Key Insights**: 3 to 4 crisp bullet points analyzing noteworthy patterns in traffic distribution, caching/bandwidth savings, security threats or scanner probes, and user acquisition.
3. **Operational Recommendations**: 1 or 2 actionable engineering/operations recommendations based on this timeframe's data.

Format strictly in clean GitHub Flavored Markdown (do not wrap the entire response in a markdown code fence). Keep the tone professional, objective, and executive-friendly. Only reference numbers and details substantiated by the data above."""
        return prompt

    def _call_model(self, model: str, prompt: str) -> Tuple[bool, str]:
        """
        Attempt to generate content using a specific Gemini model.
        Returns (success: bool, content_or_error_message: str).
        """
        url = f"{API_BASE_URL}/{model}:generateContent"
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }
        params = {
            "key": self.api_key,
        }
        payload = {
            "contents": [
                {
                    "parts": [{"text": prompt}],
                }
            ],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 1024,
            },
        }

        try:
            resp = requests.post(
                url,
                headers=headers,
                params=params,
                json=payload,
                timeout=self.timeout,
            )

            if resp.status_code != 200:
                err_msg = f"HTTP {resp.status_code}"
                try:
                    err_json = resp.json()
                    if "error" in err_json and "message" in err_json["error"]:
                        err_msg = f"HTTP {resp.status_code} ({err_json['error']['message']})"
                except Exception:
                    pass
                return False, err_msg

            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                return False, "No candidates in response"

            candidate = candidates[0]
            parts = candidate.get("content", {}).get("parts", [])
            if not parts:
                return False, "No parts in candidate content"

            # Prefer non-thought text parts (in case model has chain-of-thought)
            non_thought_parts = [
                p["text"]
                for p in parts
                if isinstance(p, dict) and "text" in p and not p.get("thought", False)
            ]
            if non_thought_parts:
                text = "\n".join(non_thought_parts).strip()
            else:
                text = "\n".join(
                    p["text"] for p in parts if isinstance(p, dict) and "text" in p
                ).strip()

            if not text:
                return False, "Empty text extracted from candidate"

            return True, text

        except requests.RequestException as e:
            return False, f"Network error: {e}"
        except Exception as e:
            return False, f"Unexpected error: {e}"

    def generate_executive_brief(
        self,
        cadence: CadenceDefinition,
        window: TimeWindow,
        metrics: SectionMetrics,
        on_attempt: Optional[Callable[[str, bool, Optional[str]], None]] = None,
    ) -> Optional[str]:
        """
        Generate an executive brief using a cascading fallback strategy:
        Attempts Gemini 3.8 Flash, then Gemini 3.5 Flash-Lite, then Gemini 3.5 Flash.
        """
        if not self.is_configured:
            return None

        prompt = self._build_prompt(cadence, window, metrics)

        for model in self.models:
            success, result_or_err = self._call_model(model, prompt)
            if success:
                self.last_model_used = model
                if on_attempt:
                    on_attempt(model, True, None)
                return result_or_err

            if on_attempt:
                on_attempt(model, False, result_or_err)
            logger.warning("Gemini model '%s' failed: %s. Falling back to next model...", model, result_or_err)

        logger.error("All Gemini fallback models exhausted: %s", self.models)
        return None
