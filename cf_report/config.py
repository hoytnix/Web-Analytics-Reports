"""
Configuration settings, zone lists, external project mappings, and cadence definitions.
Loads environment variables with file precedence (.env.local, .env) before Shell environment.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def _load_env_file(file_path: Path) -> Dict[str, str]:
    """Parse key-value pairs from a simple dotenv file without external dependencies."""
    env_vars: Dict[str, str] = {}
    if not file_path.is_file():
        return env_vars

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip()
                    # Strip surrounding single or double quotes
                    if len(val) >= 2 and (
                        (val[0] == '"' and val[-1] == '"')
                        or (val[0] == "'" and val[-1] == "'")
                    ):
                        val = val[1:-1]
                    if key:
                        env_vars[key] = val
    except Exception:
        pass
    return env_vars


def _init_env() -> Dict[str, str]:
    """
    Search for .env.local and .env files in the project root and current working directory.
    .env.local takes precedence over .env.
    """
    candidates = [
        Path.cwd() / ".env.local",
        Path.cwd() / ".env",
        Path(__file__).resolve().parent.parent / ".env.local",
        Path(__file__).resolve().parent.parent / ".env",
    ]

    merged_file_env: Dict[str, str] = {}
    # Iterate in reverse so higher priority candidate files overwrite lower priority ones
    for p in reversed(candidates):
        if p.exists():
            file_env = _load_env_file(p)
            merged_file_env.update(file_env)

    return merged_file_env


_FILE_ENV = _init_env()


def get_config_var(key: str, default: str = "") -> str:
    """
    Retrieve variable with precedence:
    1. Value defined in .env.local / .env file
    2. Value defined in Shell environment (os.environ)
    3. Fallback default
    """
    file_val = _FILE_ENV.get(key)
    if file_val is not None and file_val.strip() != "":
        return file_val.strip()

    env_val = os.environ.get(key)
    if env_val is not None and env_val.strip() != "":
        return env_val.strip()

    return default


# Cloudflare API Configuration
CF_API_TOKEN = get_config_var("CF_API_TOKEN", "")
CF_ACCOUNT_ID = get_config_var("CF_ACCOUNT_ID", "")

# Vercel Configuration
VERCEL_TOKEN = get_config_var("VERCEL_TOKEN", "")
VERCEL_TEAM_ID = get_config_var("VERCEL_TEAM_ID", "")

def _load_zones_config() -> Tuple[List[Tuple[str, str]], Dict[str, str], Dict[str, str]]:
    """
    Load zone IDs, Vercel project mappings, and Vercel aliases from a YAML config file.
    Searches candidates:
      - ZONES_CONFIG env var (if set)
      - zones.local.yaml / zones.local.yml
      - zones.yaml / zones.yml
      - config.local.yaml / config.local.yml
      - config.yaml / config.yml
    """
    candidates: List[Path] = []
    custom_path = os.environ.get("ZONES_CONFIG") or _FILE_ENV.get("ZONES_CONFIG")
    if custom_path:
        candidates.append(Path(custom_path))

    for name in [
        "zones.local.yaml",
        "zones.local.yml",
        "zones.yaml",
        "zones.yml",
        "config.local.yaml",
        "config.local.yml",
        "config.yaml",
        "config.yml",
    ]:
        candidates.append(Path.cwd() / name)
        candidates.append(Path(__file__).resolve().parent.parent / name)

    config_data: Dict = {}
    for p in candidates:
        if p.is_file():
            try:
                import yaml

                with open(p, "r", encoding="utf-8") as f:
                    loaded = yaml.safe_load(f)
                    if isinstance(loaded, dict):
                        config_data = loaded
                        break
            except Exception:
                pass

    zones_list: List[Tuple[str, str]] = []
    raw_zones = config_data.get("zones", [])
    if isinstance(raw_zones, list):
        for item in raw_zones:
            if isinstance(item, dict):
                zid = str(item.get("id", "")).strip()
                zdom = str(item.get("domain", item.get("name", ""))).strip()
                if zid and zdom:
                    zones_list.append((zid, zdom))
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                zones_list.append((str(item[0]).strip(), str(item[1]).strip()))
            elif isinstance(item, str) and ":" in item:
                parts = item.split(":", 1)
                zones_list.append((parts[0].strip(), parts[1].strip()))
    elif isinstance(raw_zones, dict):
        for k, v in raw_zones.items():
            zones_list.append((str(k).strip(), str(v).strip()))

    vercel_projects: Dict[str, str] = {}
    raw_vp = config_data.get("vercel_projects", {})
    if isinstance(raw_vp, dict):
        for k, v in raw_vp.items():
            vercel_projects[str(k).strip()] = str(v).strip()

    vercel_aliases: Dict[str, str] = {}
    raw_va = config_data.get("vercel_aliases", {})
    if isinstance(raw_va, dict):
        for k, v in raw_va.items():
            vercel_aliases[str(k).strip()] = str(v).strip()

    # Automatically derive aliases from domain slugs if not explicitly given
    for dom, pid in vercel_projects.items():
        slug = dom.split(".")[0]
        if slug and slug not in vercel_aliases:
            vercel_aliases[slug] = pid

    return zones_list, vercel_projects, vercel_aliases


# Monitored Zones: (Zone ID, Zone Domain)
# Vercel Project Mappings (Domain -> Project Identifier)
# Vercel Slug Aliases (Slug -> Project Identifier)
ZONES, VERCEL_PROJECTS, VERCEL_ALIASES = _load_zones_config()

# Country Code to Full Name mapping
COUNTRY_MAP: Dict[str, str] = {
    "US": "United States",
    "IN": "India",
    "DE": "Germany",
    "HK": "Hong Kong",
    "SE": "Sweden",
    "KR": "South Korea",
    "JP": "Japan",
    "CA": "Canada",
    "AU": "Australia",
    "NL": "Netherlands",
    "GB": "United Kingdom",
    "FR": "France",
    "SG": "Singapore",
    "BR": "Brazil",
    "CN": "China",
    "RU": "Russia",
    "IT": "Italy",
    "ES": "Spain",
    "PL": "Poland",
    "UA": "Ukraine",
    "TW": "Taiwan",
    "ID": "Indonesia",
    "VN": "Vietnam",
    "MX": "Mexico",
    "AE": "United Arab Emirates",
    "IE": "Ireland",
    "CH": "Switzerland",
    "ZA": "South Africa",
    "FI": "Finland",
    "NO": "Norway",
    "DK": "Denmark",
    "BE": "Belgium",
    "AT": "Austria",
    "NZ": "New Zealand",
    "IL": "Israel",
}


@dataclass(frozen=True)
class CadenceDefinition:
    key: str
    label: str
    display_label: str
    mode: str  # "hourly" or "daily"
    relative_amount: int
    relative_unit: str  # "hours" or "days"


CADENCE_DEFINITIONS: List[CadenceDefinition] = [
    CadenceDefinition(
        key="24h",
        label="last_24_hours",
        display_label="Last 24 Hours",
        mode="hourly",
        relative_amount=24,
        relative_unit="hours",
    ),
    CadenceDefinition(
        key="48h",
        label="last_48_hours",
        display_label="Last 48 Hours",
        mode="hourly",
        relative_amount=48,
        relative_unit="hours",
    ),
    CadenceDefinition(
        key="4d",
        label="last_4_days",
        display_label="Last 4 Days",
        mode="daily",
        relative_amount=4,
        relative_unit="days",
    ),
    CadenceDefinition(
        key="7d",
        label="last_7_days",
        display_label="Last 7 Days",
        mode="daily",
        relative_amount=7,
        relative_unit="days",
    ),
    CadenceDefinition(
        key="30d",
        label="last_30_days",
        display_label="Last 30 Days",
        mode="daily",
        relative_amount=30,
        relative_unit="days",
    ),
]

TARGET_ALIASES: Dict[str, str] = {
    "24h": "24h",
    "24hours": "24h",
    "day": "24h",
    "daily": "24h",
    "1day": "24h",
    "48h": "48h",
    "48hours": "48h",
    "2day": "48h",
    "2days": "48h",
    "4d": "4d",
    "4day": "4d",
    "4days": "4d",
    "7d": "7d",
    "7day": "7d",
    "7days": "7d",
    "week": "7d",
    "weekly": "7d",
    "30d": "30d",
    "30day": "30d",
    "30days": "30d",
    "month": "30d",
    "monthly": "30d",
    "all": "all",
    "consolidated": "all",
}
