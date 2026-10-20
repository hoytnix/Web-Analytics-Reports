"""
Cloudflare Web Analytics (RUM) integration.
Queries rumPageloadEventsAdaptiveGroups to fetch real client-side visitor metrics,
pageviews, visits, host breakdown, top paths, referrers, devices, and browsers.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple

from ..models import (
    BreakdownItem,
    CloudflareWebAnalyticsData,
    TimeWindow,
)
from ..utils import format_number, format_percent
from .client import CloudflareClient

logger = logging.getLogger(__name__)

GRAPHQL_RUM_QUERY = """
query GetAccountRum($accountTag: String!, $since: String!, $until: String!) {
  viewer {
    accounts(filter: { accountTag: $accountTag }) {
      byHost: rumPageloadEventsAdaptiveGroups(
        limit: 100,
        filter: { datetime_geq: $since, datetime_leq: $until },
        orderBy: [count_DESC]
      ) {
        count
        sum { visits }
        dimensions { requestHost siteTag }
      }
      referrers: rumPageloadEventsAdaptiveGroups(
        limit: 20,
        filter: { datetime_geq: $since, datetime_leq: $until },
        orderBy: [count_DESC]
      ) {
        count
        sum { visits }
        dimensions { refererHost }
      }
      paths: rumPageloadEventsAdaptiveGroups(
        limit: 20,
        filter: { datetime_geq: $since, datetime_leq: $until },
        orderBy: [count_DESC]
      ) {
        count
        dimensions { requestPath }
      }
      countries: rumPageloadEventsAdaptiveGroups(
        limit: 20,
        filter: { datetime_geq: $since, datetime_leq: $until },
        orderBy: [count_DESC]
      ) {
        count
        sum { visits }
        dimensions { countryName }
      }
      devices: rumPageloadEventsAdaptiveGroups(
        limit: 10,
        filter: { datetime_geq: $since, datetime_leq: $until },
        orderBy: [count_DESC]
      ) {
        count
        dimensions { deviceType }
      }
      browsers: rumPageloadEventsAdaptiveGroups(
        limit: 10,
        filter: { datetime_geq: $since, datetime_leq: $until },
        orderBy: [count_DESC]
      ) {
        count
        dimensions { userAgentBrowser }
      }
    }
  }
}
"""


def fetch_cloudflare_web_analytics(
    client: CloudflareClient,
    window: TimeWindow,
) -> CloudflareWebAnalyticsData:
    """Fetch and parse Cloudflare Web Analytics (RUM) for the account."""
    account_id = client.account_id
    if not account_id:
        logger.warning("No Cloudflare Account ID available for Web Analytics query.")
        return CloudflareWebAnalyticsData()

    variables = {
        "accountTag": account_id,
        "since": window.since_dt,
        "until": window.until_dt,
    }

    res = client.execute_graphql(GRAPHQL_RUM_QUERY, variables)
    if res.get("errors"):
        logger.warning(f"Cloudflare Web Analytics GraphQL error: {res['errors']}")
        return CloudflareWebAnalyticsData()

    accounts = res.get("data", {}).get("viewer", {}).get("accounts", [])
    if not accounts:
        return CloudflareWebAnalyticsData()

    acc_data = accounts[0] or {}

    # 1. Parse byHost
    by_host_raw = acc_data.get("byHost") or []
    by_host: Dict[str, Dict[str, int]] = {}
    total_views = 0
    total_visits = 0

    for item in by_host_raw:
        dims = item.get("dimensions") or {}
        host = (dims.get("requestHost") or "").strip().lower()
        cnt = item.get("count") or 0
        vis = (item.get("sum") or {}).get("visits") or 0

        total_views += cnt
        total_visits += vis

        if host not in by_host:
            by_host[host] = {"pageviews": 0, "visits": 0}
        by_host[host]["pageviews"] += cnt
        by_host[host]["visits"] += vis

    # 2. Parse Referrers
    referrers_raw = acc_data.get("referrers") or []
    top_referrers: List[BreakdownItem] = []
    ref_map: Dict[str, int] = {}
    for item in referrers_raw:
        ref = (item.get("dimensions") or {}).get("refererHost") or ""
        ref_label = "(direct / none)" if not ref else ref
        ref_map[ref_label] = ref_map.get(ref_label, 0) + (item.get("count") or 0)

    for ref_label, cnt in sorted(ref_map.items(), key=lambda x: x[1], reverse=True)[:10]:
        top_referrers.append(
            BreakdownItem(
                key=ref_label,
                label=ref_label,
                count=cnt,
                count_formatted=format_number(cnt),
                share_pct=format_percent(cnt, total_views),
            )
        )

    # 3. Parse Paths
    paths_raw = acc_data.get("paths") or []
    top_paths: List[BreakdownItem] = []
    path_map: Dict[str, int] = {}
    for item in paths_raw:
        p = (item.get("dimensions") or {}).get("requestPath") or "/"
        path_map[p] = path_map.get(p, 0) + (item.get("count") or 0)

    for p, cnt in sorted(path_map.items(), key=lambda x: x[1], reverse=True)[:10]:
        top_paths.append(
            BreakdownItem(
                key=p,
                label=p,
                count=cnt,
                count_formatted=format_number(cnt),
                share_pct=format_percent(cnt, total_views),
            )
        )

    # 4. Parse Countries
    countries_raw = acc_data.get("countries") or []
    top_countries: List[BreakdownItem] = []
    country_map: Dict[str, int] = {}
    for item in countries_raw:
        c = (item.get("dimensions") or {}).get("countryName") or "Unknown"
        country_map[c] = country_map.get(c, 0) + (item.get("count") or 0)

    for c, cnt in sorted(country_map.items(), key=lambda x: x[1], reverse=True)[:8]:
        top_countries.append(
            BreakdownItem(
                key=c,
                label=c,
                count=cnt,
                count_formatted=format_number(cnt),
                share_pct=format_percent(cnt, total_views),
            )
        )

    # 5. Parse Devices
    devices_raw = acc_data.get("devices") or []
    top_devices: List[BreakdownItem] = []
    dev_map: Dict[str, int] = {}
    for item in devices_raw:
        d = (item.get("dimensions") or {}).get("deviceType") or "unknown"
        dev_map[d.title()] = dev_map.get(d.title(), 0) + (item.get("count") or 0)

    for d, cnt in sorted(dev_map.items(), key=lambda x: x[1], reverse=True):
        top_devices.append(
            BreakdownItem(
                key=d,
                label=d,
                count=cnt,
                count_formatted=format_number(cnt),
                share_pct=format_percent(cnt, total_views),
            )
        )

    # 6. Parse Browsers
    browsers_raw = acc_data.get("browsers") or []
    top_browsers: List[BreakdownItem] = []
    br_map: Dict[str, int] = {}
    for item in browsers_raw:
        b = (item.get("dimensions") or {}).get("userAgentBrowser") or "Unknown"
        br_map[b] = br_map.get(b, 0) + (item.get("count") or 0)

    for b, cnt in sorted(br_map.items(), key=lambda x: x[1], reverse=True)[:8]:
        top_browsers.append(
            BreakdownItem(
                key=b,
                label=b,
                count=cnt,
                count_formatted=format_number(cnt),
                share_pct=format_percent(cnt, total_views),
            )
        )

    return CloudflareWebAnalyticsData(
        total_pageviews=total_views,
        total_visits=total_visits,
        by_host=by_host,
        top_referrers=top_referrers,
        top_paths=top_paths,
        top_countries=top_countries,
        top_devices=top_devices,
        top_browsers=top_browsers,
    )


def match_zone_web_analytics(
    zone_name: str,
    web_analytics: CloudflareWebAnalyticsData,
) -> Tuple[int, int]:
    """
    Match and sum Cloudflare Web Analytics pageviews and visits for a given zone domain,
    including any subdomains (e.g. www.tehwiz.com, kissav.tehwiz.com for tehwiz.com).
    """
    domain = zone_name.lower().strip()
    views = 0
    visits = 0

    for host, metrics in web_analytics.by_host.items():
        if host == domain or host.endswith(f".{domain}"):
            views += metrics.get("pageviews", 0)
            visits += metrics.get("visits", 0)

    return views, visits
