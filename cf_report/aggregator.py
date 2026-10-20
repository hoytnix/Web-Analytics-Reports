"""
Data aggregation engine computing portfolio KPIs, rollups, and multi-node breakdowns.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .cloudflare.web_analytics import match_zone_web_analytics
from .models import (
    BreakdownItem,
    CacheEfficiency,
    CloudflareWebAnalyticsData,
    ProbeItem,
    ProtocolsData,
    SectionMetrics,
    SecurityData,
    SecurityItem,
    StatusHealth,
    StatusHealthGroup,
    TimeWindow,
    VercelData,
    ZoneReportItem,
    ZoneRollup,
)
from .utils import (
    format_bytes,
    format_number,
    format_percent,
    get_country_name,
)


def aggregate_section(
    raw_zones_data: List[Dict[str, Any]],
    web_analytics: CloudflareWebAnalyticsData,
    vercel_data: VercelData,
    window: TimeWindow,
    has_pro_referrers: bool = False,
) -> SectionMetrics:
    """Combine and aggregate all data sources for a reporting section."""

    # 1. Zone items and portfolio sums
    total_req = 0
    total_bytes = 0
    cached_req = 0
    cached_bytes = 0
    total_cf_views = 0
    total_threats = 0

    zone_items: List[ZoneReportItem] = []

    for zd in raw_zones_data:
        zid = zd["zone_id"]
        zname = zd["zone_name"]
        rollup: ZoneRollup = zd.get("rollup") or ZoneRollup()

        total_req += rollup.requests
        total_bytes += rollup.bytes
        cached_req += rollup.cached_requests
        cached_bytes += rollup.cached_bytes
        total_cf_views += rollup.page_views
        total_threats += rollup.threats

        hit_ratio = format_percent(rollup.cached_requests, rollup.requests)

        # Match Cloudflare Web Analytics (RUM) for this domain
        cf_web_views, cf_web_visits = match_zone_web_analytics(zname, web_analytics)

        # Match Vercel metrics
        v_proj_data = vercel_data.by_project.get(zname)
        v_views = v_proj_data.get("pageviews") if v_proj_data else None
        v_vis = v_proj_data.get("visitors") if v_proj_data else None

        zone_items.append(
            ZoneReportItem(
                zone_id=zid,
                zone_name=zname,
                requests=rollup.requests,
                hit_ratio=hit_ratio,
                bytes=rollup.bytes,
                cached_bytes=rollup.cached_bytes,
                cf_views=rollup.page_views,
                cf_threats=rollup.threats,
                cf_web_views=cf_web_views,
                cf_web_visits=cf_web_visits,
                vercel_views=v_views,
                vercel_visitors=v_vis,
            )
        )

    avg_cache_ratio = format_percent(cached_req, total_req)

    # 2. Subdomains Breakdown (from all zones)
    subdomain_counts: Dict[str, Dict[str, int]] = {}
    for zd in raw_zones_data:
        for item in zd.get("subdomains", []):
            host = (item.get("dimensions") or {}).get("clientRequestHTTPHost")
            if host:
                cnt = item.get("count", 0) or 0
                b = (item.get("sum") or {}).get("edgeResponseBytes", 0) or 0
                if host not in subdomain_counts:
                    subdomain_counts[host] = {"count": 0, "bytes": 0}
                subdomain_counts[host]["count"] += cnt
                subdomain_counts[host]["bytes"] += b

    sorted_subdomains = sorted(
        subdomain_counts.items(), key=lambda x: x[1]["count"], reverse=True
    )[:8]
    subdomains_breakdown: List[BreakdownItem] = [
        BreakdownItem(
            key=host,
            label=host,
            count=data["count"],
            bytes=data["bytes"],
            count_formatted=format_number(data["count"]),
            bytes_formatted=format_bytes(data["bytes"]),
            share_pct=format_percent(data["count"], total_req),
        )
        for host, data in sorted_subdomains
    ]

    # 3. Countries Breakdown
    country_counts: Dict[str, Dict[str, int]] = {}
    for zd in raw_zones_data:
        for item in zd.get("countries", []):
            code = (item.get("dimensions") or {}).get("clientCountryName")
            if code:
                cnt = item.get("count", 0) or 0
                b = (item.get("sum") or {}).get("edgeResponseBytes", 0) or 0
                if code not in country_counts:
                    country_counts[code] = {"count": 0, "bytes": 0}
                country_counts[code]["count"] += cnt
                country_counts[code]["bytes"] += b

    sorted_countries = sorted(
        country_counts.items(), key=lambda x: x[1]["count"], reverse=True
    )[:8]
    countries_breakdown: List[BreakdownItem] = [
        BreakdownItem(
            key=code,
            label=get_country_name(code),
            count=data["count"],
            bytes=data["bytes"],
            count_formatted=format_number(data["count"]),
            bytes_formatted=format_bytes(data["bytes"]),
            share_pct=format_percent(data["count"], total_req),
        )
        for code, data in sorted_countries
    ]

    # 4. Top Request Paths
    path_counts: Dict[str, int] = {}
    for zd in raw_zones_data:
        for item in zd.get("paths", []):
            p = (item.get("dimensions") or {}).get("clientRequestPath")
            if p:
                path_counts[p] = path_counts.get(p, 0) + (item.get("count", 0) or 0)

    sorted_paths = sorted(path_counts.items(), key=lambda x: x[1], reverse=True)[:8]
    paths_breakdown: List[BreakdownItem] = [
        BreakdownItem(
            key=p,
            label=p,
            count=cnt,
            count_formatted=format_number(cnt),
            share_pct=format_percent(cnt, total_req),
        )
        for p, cnt in sorted_paths
    ]

    # 5. Suspicious Probes (404/403)
    probe_counts: Dict[Tuple[str, int], int] = {}
    for zd in raw_zones_data:
        for item in zd.get("probes", []):
            dims = item.get("dimensions") or {}
            p = dims.get("clientRequestPath")
            status = dims.get("edgeResponseStatus", 404)
            if p:
                probe_counts[(p, status)] = probe_counts.get((p, status), 0) + (
                    item.get("count", 0) or 0
                )

    sorted_probes = sorted(probe_counts.items(), key=lambda x: x[1], reverse=True)[:8]
    probes_breakdown: List[ProbeItem] = [
        ProbeItem(
            path=p,
            status=status,
            count=cnt,
            count_formatted=format_number(cnt),
        )
        for (p, status), cnt in sorted_probes
    ]

    # 6. Status Codes & Origin Health
    status_counts: Dict[int, int] = {}
    for zd in raw_zones_data:
        for item in zd.get("statuses", []):
            status = (item.get("dimensions") or {}).get("edgeResponseStatus")
            if status is not None:
                status_counts[status] = status_counts.get(status, 0) + (
                    item.get("count", 0) or 0
                )

    s2xx = sum(cnt for status, cnt in status_counts.items() if 200 <= status < 300)
    s3xx = sum(cnt for status, cnt in status_counts.items() if 300 <= status < 400)
    s4xx = sum(cnt for status, cnt in status_counts.items() if 400 <= status < 500)
    s5xx = sum(cnt for status, cnt in status_counts.items() if 500 <= status < 600)
    total_status = sum(status_counts.values())

    origin_err_pct = format_percent(s5xx, total_status)
    is_healthy = (s5xx / total_status < 0.01) if total_status > 0 else True

    status_health = StatusHealth(
        s2xx=StatusHealthGroup(
            count=s2xx,
            count_formatted=format_number(s2xx),
            share_pct=format_percent(s2xx, total_status),
        ),
        s3xx=StatusHealthGroup(
            count=s3xx,
            count_formatted=format_number(s3xx),
            share_pct=format_percent(s3xx, total_status),
        ),
        s4xx=StatusHealthGroup(
            count=s4xx,
            count_formatted=format_number(s4xx),
            share_pct=format_percent(s4xx, total_status),
        ),
        s5xx=StatusHealthGroup(
            count=s5xx,
            count_formatted=format_number(s5xx),
            share_pct=format_percent(s5xx, total_status),
        ),
        origin_error_rate=origin_err_pct,
        is_healthy=is_healthy,
    )

    # 7. Cache Efficiency
    cache_counts: Dict[str, Dict[str, int]] = {}
    for zd in raw_zones_data:
        for item in zd.get("caching", []):
            c_status = (item.get("dimensions") or {}).get("cacheStatus")
            if c_status:
                c_status_up = c_status.upper()
                cnt = item.get("count", 0) or 0
                b = (item.get("sum") or {}).get("edgeResponseBytes", 0) or 0
                if c_status_up not in cache_counts:
                    cache_counts[c_status_up] = {"count": 0, "bytes": 0}
                cache_counts[c_status_up]["count"] += cnt
                cache_counts[c_status_up]["bytes"] += b

    cache_total_req = sum(d["count"] for d in cache_counts.values())
    cache_total_bytes = sum(d["bytes"] for d in cache_counts.values())

    cache_hit_req = sum(
        d["count"]
        for st, d in cache_counts.items()
        if st in ("HIT", "REVALIDATED")
    )
    cache_hit_bytes = sum(
        d["bytes"]
        for st, d in cache_counts.items()
        if st in ("HIT", "REVALIDATED")
    )

    cache_breakdown: List[BreakdownItem] = [
        BreakdownItem(
            key=st,
            label=st,
            count=data["count"],
            bytes=data["bytes"],
            count_formatted=format_number(data["count"]),
            bytes_formatted=format_bytes(data["bytes"]),
            share_pct=format_percent(data["count"], cache_total_req),
        )
        for st, data in sorted(cache_counts.items(), key=lambda x: x[1]["count"], reverse=True)
    ]

    cache_efficiency = CacheEfficiency(
        req_hit_ratio=format_percent(cache_hit_req, cache_total_req),
        bytes_hit_ratio=format_percent(cache_hit_bytes, cache_total_bytes),
        saved_bytes=format_bytes(cache_hit_bytes),
        breakdown=cache_breakdown,
    )

    # 8. Protocols Breakdown
    http_counts: Dict[str, int] = {}
    ssl_counts: Dict[str, int] = {}
    for zd in raw_zones_data:
        for item in zd.get("protocols", []):
            dims = item.get("dimensions") or {}
            http_proto = dims.get("clientRequestHTTPProtocol")
            ssl_proto = dims.get("clientSSLProtocol")
            cnt = item.get("count", 0) or 0

            if http_proto:
                http_counts[http_proto] = http_counts.get(http_proto, 0) + cnt

            if ssl_proto:
                ssl_label = "Plaintext (HTTP)" if ssl_proto == "none" else ssl_proto
                ssl_counts[ssl_label] = ssl_counts.get(ssl_label, 0) + cnt

    proto_total = sum(http_counts.values())
    h3_count = http_counts.get("HTTP/3", 0)

    ssl_total = sum(ssl_counts.values())
    tls13_count = ssl_counts.get("TLSv1.3", 0)

    http_breakdown: List[BreakdownItem] = [
        BreakdownItem(
            key=p,
            label=p,
            count=cnt,
            count_formatted=format_number(cnt),
            share_pct=format_percent(cnt, proto_total),
        )
        for p, cnt in sorted(http_counts.items(), key=lambda x: x[1], reverse=True)
    ]

    ssl_breakdown: List[BreakdownItem] = [
        BreakdownItem(
            key=s,
            label=s,
            count=cnt,
            count_formatted=format_number(cnt),
            share_pct=format_percent(cnt, ssl_total),
        )
        for s, cnt in sorted(ssl_counts.items(), key=lambda x: x[1], reverse=True)
    ]

    protocols = ProtocolsData(
        h3_adoption=format_percent(h3_count, proto_total),
        tls13_adoption=format_percent(tls13_count, ssl_total),
        http_breakdown=http_breakdown,
        ssl_breakdown=ssl_breakdown,
    )

    # 9. Security Breakdown
    sec_counts: Dict[Tuple[str, str], int] = {}
    for zd in raw_zones_data:
        for item in zd.get("security", []):
            dims = item.get("dimensions") or {}
            action = dims.get("securityAction", "unknown")
            source = dims.get("securitySource", "unknown")
            if action not in ("none", "unknown"):
                sec_counts[(action, source)] = sec_counts.get((action, source), 0) + (
                    item.get("count", 0) or 0
                )

    sec_items: List[SecurityItem] = [
        SecurityItem(
            action=action,
            source=source,
            count=cnt,
            count_formatted=format_number(cnt),
        )
        for (action, source), cnt in sorted(
            sec_counts.items(), key=lambda x: x[1], reverse=True
        )
    ]

    active_threats = sum(
        cnt for (action, _), cnt in sec_counts.items() if action in ("block", "challenge")
    )
    final_threat_count = active_threats if active_threats > 0 else total_threats

    security = SecurityData(
        total_threats=final_threat_count,
        total_threats_formatted=format_number(final_threat_count),
        breakdown=sec_items,
    )

    return SectionMetrics(
        total_requests=total_req,
        total_bytes=total_bytes,
        cached_requests=cached_req,
        cached_bytes=cached_bytes,
        total_cf_views=total_cf_views,
        total_threats=final_threat_count,
        avg_cache_ratio=avg_cache_ratio,
        total_cf_web_views=web_analytics.total_pageviews,
        total_cf_web_visits=web_analytics.total_visits,
        total_vercel_views=vercel_data.total_pageviews,
        total_vercel_visitors=vercel_data.total_visitors,
        zone_items=zone_items,
        subdomains=subdomains_breakdown,
        countries=countries_breakdown,
        paths=paths_breakdown,
        probes=probes_breakdown,
        status_health=status_health,
        cache_efficiency=cache_efficiency,
        protocols=protocols,
        security=security,
        web_analytics=web_analytics,
        vercel=vercel_data,
        has_pro_referrers_access=has_pro_referrers,
    )
