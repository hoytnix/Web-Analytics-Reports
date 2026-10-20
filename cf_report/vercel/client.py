"""
Vercel Web Analytics client supporting REST API and Vercel CLI metrics query.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from typing import Any, Dict, List, Optional

import requests

from ..config import VERCEL_ALIASES
from ..models import BreakdownItem, VercelData
from ..utils import format_number

logger = logging.getLogger(__name__)

# Slug to project ID resolution (loaded dynamically from configuration)
PROJECT_ALIASES: Dict[str, str] = VERCEL_ALIASES


class VercelClient:
    """Client for Vercel Web Analytics via REST API with CLI fallback."""

    def __init__(
        self,
        token: Optional[str] = None,
        team_id: Optional[str] = None,
        aliases: Optional[Dict[str, str]] = None,
    ):
        self.token = token or ""
        self.team_id = team_id or ""
        self.aliases = aliases if aliases is not None else VERCEL_ALIASES
        self.session = requests.Session()
        if self.token:
            self.session.headers.update({
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            })

    @property
    def is_configured(self) -> bool:
        return bool(self.token)

    def resolve_project_id(self, identifier: str) -> str:
        """Resolve slug alias to official prj_ identifier if applicable."""
        return self.aliases.get(identifier, identifier)

    def fetch_project_analytics_api(
        self, project_id: str, from_ms: int, to_ms: int
    ) -> Dict[str, Any]:
        """Fetch visits count and aggregate referrers via Vercel REST API."""
        if not self.is_configured:
            return {"pageviews": 0, "visitors": 0, "referrers": []}

        pid = self.resolve_project_id(project_id)
        team_param = f"&teamId={self.team_id}" if self.team_id else ""

        count_url = (
            f"https://api.vercel.com/v1/query/web-analytics/visits/count"
            f"?projectId={pid}&since={from_ms}&until={to_ms}{team_param}"
        )
        ref_url = (
            f"https://api.vercel.com/v1/query/web-analytics/visits/aggregate"
            f"?projectId={pid}&since={from_ms}&until={to_ms}&by=referrerHostname&limit=8{team_param}"
        )

        pageviews = 0
        visitors = 0
        referrers: List[Dict[str, Any]] = []

        try:
            r_count = self.session.get(count_url, timeout=10)
            if r_count.status_code == 200:
                data = r_count.json().get("data", {})
                pageviews = data.get("pageviews", 0) or 0
                visitors = data.get("visitors", 0) or 0
        except Exception as e:
            logger.warning(f"Vercel count query failed for {pid}: {e}")

        try:
            r_ref = self.session.get(ref_url, timeout=10)
            if r_ref.status_code == 200:
                data = r_ref.json().get("data", [])
                for item in data:
                    ref_host = item.get("referrerHostname")
                    if ref_host is not None:
                        cnt = item.get("pageviews") or item.get("visitors") or 0
                        referrers.append({
                            "referrer": "(direct / none)" if ref_host == "" else ref_host,
                            "count": cnt,
                        })
        except Exception as e:
            logger.warning(f"Vercel referrers query failed for {pid}: {e}")

        return {
            "pageviews": pageviews,
            "visitors": visitors,
            "referrers": referrers,
        }

    def fetch_project_analytics_cli(
        self, project_id: str, since_iso: str, until_iso: str
    ) -> Dict[str, Any]:
        """Fetch analytics via `vercel metrics` CLI command."""
        if not self.is_configured or not shutil.which("vercel"):
            return {"pageviews": 0, "visitors": 0, "referrers": []}

        pid = self.resolve_project_id(project_id)
        scope_args = ["--scope", self.team_id] if self.team_id else []

        cmd_base = [
            "vercel", "metrics", "vercel.analytics.page_view.count",
            "--project", pid,
            "--token", self.token,
            "--prod",
            "--since", since_iso,
            "--until", until_iso,
            "--json",
            *scope_args,
        ]

        pageviews = 0
        visitors = 0
        referrers: List[Dict[str, Any]] = []

        try:
            # 1. Total pageviews
            res_pv = subprocess.run(cmd_base, capture_output=True, text=True, timeout=15)
            if res_pv.returncode == 0 and res_pv.stdout:
                data = json.loads(res_pv.stdout)
                for item in data.get("summary", []):
                    pageviews += item.get("vercel_analytics_page_view_count_count", 0) or 0
        except Exception as e:
            logger.warning(f"Vercel CLI pageview query failed for {pid}: {e}")

        try:
            # 2. Unique visitors
            cmd_vis = cmd_base + ["-a", "unique/visitorId"]
            res_vis = subprocess.run(cmd_vis, capture_output=True, text=True, timeout=15)
            if res_vis.returncode == 0 and res_vis.stdout:
                data = json.loads(res_vis.stdout)
                for item in data.get("summary", []):
                    visitors += item.get("vercel_analytics_page_view_count_unique_visitorId", 0) or 0
        except Exception as e:
            logger.warning(f"Vercel CLI visitors query failed for {pid}: {e}")

        try:
            # 3. Referrers
            cmd_ref = cmd_base + ["--group-by", "referrerHostname", "--limit", "8"]
            res_ref = subprocess.run(cmd_ref, capture_output=True, text=True, timeout=15)
            if res_ref.returncode == 0 and res_ref.stdout:
                data = json.loads(res_ref.stdout)
                for item in data.get("summary", []):
                    ref_host = item.get("referrerHostname")
                    if ref_host is not None:
                        cnt = item.get("vercel_analytics_page_view_count_count", 0) or 0
                        referrers.append({
                            "referrer": "(direct / none)" if ref_host == "" else ref_host,
                            "count": cnt,
                        })
        except Exception as e:
            logger.warning(f"Vercel CLI referrers query failed for {pid}: {e}")

        return {
            "pageviews": pageviews,
            "visitors": visitors,
            "referrers": referrers,
        }

    def fetch_project_analytics(
        self,
        project_id: str,
        from_ms: int,
        to_ms: int,
        since_iso: str = "",
        until_iso: str = "",
    ) -> Dict[str, Any]:
        """Fetch project analytics using REST API first, falling back to CLI."""
        if not self.is_configured:
            return {"pageviews": 0, "visitors": 0, "referrers": []}

        # Prefer REST API for speed and zero subprocess overhead
        res = self.fetch_project_analytics_api(project_id, from_ms, to_ms)
        if res.get("pageviews", 0) > 0 or res.get("visitors", 0) > 0:
            return res

        # If REST returned 0 or empty and CLI is available, try CLI
        if shutil.which("vercel") and since_iso and until_iso:
            cli_res = self.fetch_project_analytics_cli(project_id, since_iso, until_iso)
            if cli_res.get("pageviews", 0) > 0 or cli_res.get("visitors", 0) > 0:
                return cli_res

        return res
