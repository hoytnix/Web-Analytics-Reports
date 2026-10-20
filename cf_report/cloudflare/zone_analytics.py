"""
Cloudflare Zone Analytics query definition, fetching, and parsing.
"""

from __future__ import annotations

import concurrent.futures
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

from ..models import TimeWindow, ZoneRollup
from .client import CloudflareClient

logger = logging.getLogger(__name__)

GRAPHQL_QUERY_HOURLY = """
query GetZoneHourly($zoneTag: String!, $since: String!, $until: String!) {
  viewer {
    zones(filter: { zoneTag: $zoneTag }) {
      rollup: httpRequests1hGroups(limit: 1000, filter: { datetime_geq: $since, datetime_lt: $until }) {
        sum { requests bytes cachedRequests cachedBytes threats pageViews }
      }
      subdomains: httpRequestsAdaptiveGroups(limit: 15, filter: { datetime_geq: $since, datetime_leq: $until }, orderBy: [count_DESC]) {
        count sum { edgeResponseBytes } dimensions { clientRequestHTTPHost }
      }
      countries: httpRequestsAdaptiveGroups(limit: 15, filter: { datetime_geq: $since, datetime_leq: $until }, orderBy: [count_DESC]) {
        count sum { edgeResponseBytes } dimensions { clientCountryName }
      }
      paths: httpRequestsAdaptiveGroups(limit: 15, filter: { datetime_geq: $since, datetime_leq: $until }, orderBy: [count_DESC]) {
        count dimensions { clientRequestPath }
      }
      probes: httpRequestsAdaptiveGroups(limit: 15, filter: { datetime_geq: $since, datetime_leq: $until, edgeResponseStatus_in: [404, 403] }, orderBy: [count_DESC]) {
        count dimensions { clientRequestPath edgeResponseStatus }
      }
      statuses: httpRequestsAdaptiveGroups(limit: 20, filter: { datetime_geq: $since, datetime_leq: $until }, orderBy: [count_DESC]) {
        count dimensions { edgeResponseStatus }
      }
      caching: httpRequestsAdaptiveGroups(limit: 15, filter: { datetime_geq: $since, datetime_leq: $until }, orderBy: [count_DESC]) {
        count sum { edgeResponseBytes } dimensions { cacheStatus }
      }
      protocols: httpRequestsAdaptiveGroups(limit: 15, filter: { datetime_geq: $since, datetime_leq: $until }, orderBy: [count_DESC]) {
        count dimensions { clientRequestHTTPProtocol clientSSLProtocol }
      }
      security: httpRequestsAdaptiveGroups(limit: 15, filter: { datetime_geq: $since, datetime_leq: $until, securityAction_neq: "none" }, orderBy: [count_DESC]) {
        count dimensions { securityAction securitySource }
      }
    }
  }
}
"""

GRAPHQL_QUERY_DAILY = """
query GetZoneDaily($zoneTag: String!, $sinceDate: String!, $untilDate: String!, $sinceDt: String!, $untilDt: String!) {
  viewer {
    zones(filter: { zoneTag: $zoneTag }) {
      rollup: httpRequests1dGroups(limit: 100, filter: { date_geq: $sinceDate, date_leq: $untilDate }) {
        sum { requests bytes cachedRequests cachedBytes threats pageViews }
      }
      subdomains: httpRequestsAdaptiveGroups(limit: 15, filter: { datetime_geq: $sinceDt, datetime_leq: $untilDt }, orderBy: [count_DESC]) {
        count sum { edgeResponseBytes } dimensions { clientRequestHTTPHost }
      }
      countries: httpRequestsAdaptiveGroups(limit: 15, filter: { datetime_geq: $sinceDt, datetime_leq: $untilDt }, orderBy: [count_DESC]) {
        count sum { edgeResponseBytes } dimensions { clientCountryName }
      }
      paths: httpRequestsAdaptiveGroups(limit: 15, filter: { datetime_geq: $sinceDt, datetime_leq: $untilDt }, orderBy: [count_DESC]) {
        count dimensions { clientRequestPath }
      }
      probes: httpRequestsAdaptiveGroups(limit: 15, filter: { datetime_geq: $sinceDt, datetime_leq: $untilDt, edgeResponseStatus_in: [404, 403] }, orderBy: [count_DESC]) {
        count dimensions { clientRequestPath edgeResponseStatus }
      }
      statuses: httpRequestsAdaptiveGroups(limit: 20, filter: { datetime_geq: $sinceDt, datetime_leq: $untilDt }, orderBy: [count_DESC]) {
        count dimensions { edgeResponseStatus }
      }
      caching: httpRequestsAdaptiveGroups(limit: 15, filter: { datetime_geq: $sinceDt, datetime_leq: $untilDt }, orderBy: [count_DESC]) {
        count sum { edgeResponseBytes } dimensions { cacheStatus }
      }
      protocols: httpRequestsAdaptiveGroups(limit: 15, filter: { datetime_geq: $sinceDt, datetime_leq: $untilDt }, orderBy: [count_DESC]) {
        count dimensions { clientRequestHTTPProtocol clientSSLProtocol }
      }
      security: httpRequestsAdaptiveGroups(limit: 15, filter: { datetime_geq: $sinceDt, datetime_leq: $untilDt, securityAction_neq: "none" }, orderBy: [count_DESC]) {
        count dimensions { securityAction securitySource }
      }
    }
  }
}
"""


def parse_zone_rollup(rollup_list: List[Dict[str, Any]]) -> ZoneRollup:
    """Sum items from rollup array."""
    req = 0
    b = 0
    creq = 0
    cb = 0
    thr = 0
    views = 0

    for item in rollup_list:
        s = item.get("sum") or {}
        req += s.get("requests") or 0
        b += s.get("bytes") or 0
        creq += s.get("cachedRequests") or 0
        cb += s.get("cachedBytes") or 0
        thr += s.get("threats") or 0
        views += s.get("pageViews") or 0

    return ZoneRollup(
        requests=req,
        bytes=b,
        cached_requests=creq,
        cached_bytes=cb,
        threats=thr,
        page_views=views,
    )


def fetch_single_zone(
    client: CloudflareClient,
    zone_id: str,
    zone_name: str,
    window: TimeWindow,
) -> Dict[str, Any]:
    """Fetch analytics for a single zone."""
    if window.mode == "hourly":
        query = GRAPHQL_QUERY_HOURLY
        variables = {
            "zoneTag": zone_id,
            "since": window.start_iso,
            "until": window.end_iso,
        }
    else:
        query = GRAPHQL_QUERY_DAILY
        variables = {
            "zoneTag": zone_id,
            "sinceDate": window.since_date,
            "untilDate": window.until_date,
            "sinceDt": window.since_dt,
            "untilDt": window.until_dt,
        }

    res = client.execute_graphql(query, variables)
    errors = res.get("errors")

    zone_data: Dict[str, Any] = {
        "zone_id": zone_id,
        "zone_name": zone_name,
        "success": not bool(errors),
        "errors": errors,
        "rollup": ZoneRollup(),
        "subdomains": [],
        "countries": [],
        "paths": [],
        "probes": [],
        "statuses": [],
        "caching": [],
        "protocols": [],
        "security": [],
    }

    if errors:
        logger.warning(f"Zone {zone_name} returned GraphQL errors: {errors}")
        return zone_data

    zones = res.get("data", {}).get("viewer", {}).get("zones", [])
    if not zones:
        return zone_data

    raw_zone = zones[0] or {}
    zone_data["rollup"] = parse_zone_rollup(raw_zone.get("rollup") or [])
    zone_data["subdomains"] = raw_zone.get("subdomains") or []
    zone_data["countries"] = raw_zone.get("countries") or []
    zone_data["paths"] = raw_zone.get("paths") or []
    zone_data["probes"] = raw_zone.get("probes") or []
    zone_data["statuses"] = raw_zone.get("statuses") or []
    zone_data["caching"] = raw_zone.get("caching") or []
    zone_data["protocols"] = raw_zone.get("protocols") or []
    zone_data["security"] = raw_zone.get("security") or []

    return zone_data


def fetch_all_zones(
    client: CloudflareClient,
    zones: List[Tuple[str, str]],
    window: TimeWindow,
    parallel: bool = True,
    on_progress: Optional[Callable[[str, bool], None]] = None,
) -> List[Dict[str, Any]]:
    """Fetch analytics for all configured zones, optionally in parallel."""
    results: List[Dict[str, Any]] = []

    if parallel and len(zones) > 1:
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(zones), 8)) as executor:
            future_to_zone = {
                executor.submit(fetch_single_zone, client, zid, zname, window): (zid, zname)
                for zid, zname in zones
            }
            # Maintain original order by waiting and mapping back
            zone_results_map: Dict[str, Dict[str, Any]] = {}
            for future in concurrent.futures.as_completed(future_to_zone):
                zid, zname = future_to_zone[future]
                try:
                    data = future.result()
                    zone_results_map[zid] = data
                    if on_progress:
                        on_progress(zname, data["success"])
                except Exception as e:
                    logger.error(f"Error querying {zname}: {e}")
                    failed_data = {
                        "zone_id": zid,
                        "zone_name": zname,
                        "success": False,
                        "errors": [{"message": str(e)}],
                        "rollup": ZoneRollup(),
                        "subdomains": [],
                        "countries": [],
                        "paths": [],
                        "probes": [],
                        "statuses": [],
                        "caching": [],
                        "protocols": [],
                        "security": [],
                    }
                    zone_results_map[zid] = failed_data
                    if on_progress:
                        on_progress(zname, False)

            # Re-order according to original zone list
            for zid, _ in zones:
                if zid in zone_results_map:
                    results.append(zone_results_map[zid])
    else:
        for zid, zname in zones:
            data = fetch_single_zone(client, zid, zname, window)
            results.append(data)
            if on_progress:
                on_progress(zname, data["success"])

    return results
