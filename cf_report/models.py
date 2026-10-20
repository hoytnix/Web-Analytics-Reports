"""
Domain and analytical data models for Cloudflare & Vercel reporting.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class TimeWindow:
    mode: str  # "hourly" or "daily"
    start_iso: str
    end_iso: str
    display_range: str
    from_epoch_ms: int
    to_epoch_ms: int
    since_date: str = ""
    until_date: str = ""
    since_dt: str = ""
    until_dt: str = ""


@dataclass
class ZoneRollup:
    requests: int = 0
    bytes: int = 0
    cached_requests: int = 0
    cached_bytes: int = 0
    threats: int = 0
    page_views: int = 0


@dataclass
class BreakdownItem:
    key: str
    label: str = ""
    count: int = 0
    bytes: int = 0
    share_pct: str = "0.0%"
    count_formatted: str = "0"
    bytes_formatted: str = "0 B"


@dataclass
class ProbeItem:
    path: str
    status: int
    count: int
    count_formatted: str = "0"


@dataclass
class StatusHealthGroup:
    count: int = 0
    count_formatted: str = "0"
    share_pct: str = "0.0%"


@dataclass
class StatusHealth:
    s2xx: StatusHealthGroup = field(default_factory=StatusHealthGroup)
    s3xx: StatusHealthGroup = field(default_factory=StatusHealthGroup)
    s4xx: StatusHealthGroup = field(default_factory=StatusHealthGroup)
    s5xx: StatusHealthGroup = field(default_factory=StatusHealthGroup)
    origin_error_rate: str = "0.0%"
    is_healthy: bool = True


@dataclass
class CacheEfficiency:
    req_hit_ratio: str = "0.0%"
    bytes_hit_ratio: str = "0.0%"
    saved_bytes: str = "0 B"
    breakdown: List[BreakdownItem] = field(default_factory=list)


@dataclass
class ProtocolsData:
    h3_adoption: str = "0.0%"
    tls13_adoption: str = "0.0%"
    http_breakdown: List[BreakdownItem] = field(default_factory=list)
    ssl_breakdown: List[BreakdownItem] = field(default_factory=list)


@dataclass
class SecurityItem:
    action: str
    source: str
    count: int
    count_formatted: str = "0"


@dataclass
class SecurityData:
    total_threats: int = 0
    total_threats_formatted: str = "0"
    breakdown: List[SecurityItem] = field(default_factory=list)


@dataclass
class CloudflareWebAnalyticsData:
    total_pageviews: int = 0
    total_visits: int = 0
    by_host: Dict[str, Dict[str, int]] = field(default_factory=dict)
    top_referrers: List[BreakdownItem] = field(default_factory=list)
    top_paths: List[BreakdownItem] = field(default_factory=list)
    top_countries: List[BreakdownItem] = field(default_factory=list)
    top_browsers: List[BreakdownItem] = field(default_factory=list)
    top_devices: List[BreakdownItem] = field(default_factory=list)


@dataclass
class VercelData:
    total_pageviews: int = 0
    total_visitors: int = 0
    by_project: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    referrers: List[BreakdownItem] = field(default_factory=list)
    is_configured: bool = False


@dataclass
class ZoneReportItem:
    zone_id: str
    zone_name: str
    requests: int = 0
    hit_ratio: str = "0.0%"
    bytes: int = 0
    cached_bytes: int = 0
    cf_views: int = 0
    cf_threats: int = 0
    # Cloudflare Web Analytics (RUM) integration:
    cf_web_views: Optional[int] = None
    cf_web_visits: Optional[int] = None
    # Vercel Analytics integration:
    vercel_views: Optional[int] = None
    vercel_visitors: Optional[int] = None


@dataclass
class SectionMetrics:
    total_requests: int
    total_bytes: int
    cached_requests: int
    cached_bytes: int
    total_cf_views: int
    total_threats: int
    avg_cache_ratio: str
    # Cloudflare Web Analytics aggregates:
    total_cf_web_views: int
    total_cf_web_visits: int
    # Vercel aggregates:
    total_vercel_views: int
    total_vercel_visitors: int
    # Monitored zones rows:
    zone_items: List[ZoneReportItem]
    # Deep breakdowns:
    subdomains: List[BreakdownItem]
    countries: List[BreakdownItem]
    paths: List[BreakdownItem]
    probes: List[ProbeItem]
    status_health: StatusHealth
    cache_efficiency: CacheEfficiency
    protocols: ProtocolsData
    security: SecurityData
    web_analytics: CloudflareWebAnalyticsData
    vercel: VercelData
    has_pro_referrers_access: bool = False


@dataclass
class ReportSection:
    cadence_key: str
    label: str
    display_label: str
    window: TimeWindow
    metrics: SectionMetrics
