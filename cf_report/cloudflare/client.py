"""
Cloudflare API Client handling GraphQL and REST endpoints with authentication and error handling.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)


class CloudflareClient:
    """Wrapper for Cloudflare REST and GraphQL APIs."""

    def __init__(self, api_token: str, account_id: Optional[str] = None):
        self.api_token = api_token
        self._account_id = account_id
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
            "User-Agent": "CloudflareAnalyticsReporter/2.0",
        })
        self._has_pro_referrers: Optional[bool] = None

    @property
    def account_id(self) -> str:
        """Get or discover Cloudflare Account ID."""
        if not self._account_id:
            self._account_id = self.discover_account_id()
        return self._account_id

    def discover_account_id(self) -> str:
        """Discover account ID from the /accounts endpoint."""
        try:
            resp = self.session.get("https://api.cloudflare.com/client/v4/accounts", timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("result", [])
                if results and "id" in results[0]:
                    return results[0]["id"]
        except Exception as e:
            logger.warning(f"Could not auto-discover account ID: {e}")
        return ""

    def execute_graphql(self, query: str, variables: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a GraphQL query against Cloudflare's endpoint."""
        url = "https://api.cloudflare.com/client/v4/graphql"
        payload = {"query": query, "variables": variables}

        try:
            resp = self.session.post(url, json=payload, timeout=30)
            if resp.status_code != 200:
                logger.error(f"GraphQL request failed HTTP {resp.status_code}: {resp.text[:200]}")
                return {"errors": [{"message": f"HTTP {resp.status_code}: {resp.text[:100]}"}]}
            return resp.json()
        except Exception as e:
            logger.error(f"GraphQL request exception: {e}")
            return {"errors": [{"message": str(e)}]}

    def probe_referrers_access(self, test_zone: str) -> bool:
        """Probe if account/zone has access to clientRequestReferer (Pro/Enterprise tier)."""
        if self._has_pro_referrers is not None:
            return self._has_pro_referrers

        probe_query = """
        query ProbeReferrers($zoneTag: String!) {
          viewer {
            zones(filter: { zoneTag: $zoneTag }) {
              httpRequestsAdaptiveGroups(limit: 1) {
                dimensions { clientRequestReferer }
              }
            }
          }
        }
        """
        res = self.execute_graphql(probe_query, {"zoneTag": test_zone})
        has_access = False
        try:
            zones = res.get("data", {}).get("viewer", {}).get("zones", [])
            if zones and zones[0].get("httpRequestsAdaptiveGroups") is not None:
                has_access = True
        except Exception:
            has_access = False

        self._has_pro_referrers = has_access
        return has_access
