# System Patterns — Portfolio Reporter

## Architecture
- `cf_report/config.py`: loads `.env.local`/`.env`, loads zones config from
  `zones.yaml` (or `ZONES_CONFIG` override). Exposes `ZONES`,
  `VERCEL_PROJECTS`, `VERCEL_ALIASES`, `CADENCE_DEFINITIONS`.
- `cf_report/cloudflare/`: GraphQL zone analytics + RUM web analytics.
- `cf_report/vercel/client.py`: Vercel analytics; skipped per-domain when no
  project mapping exists (`VercelData(is_configured=False)`).
- `cf_report/aggregator.py`: merges raw zone/RUM/Vercel outputs into KPIs.
- `cf_report/renderers/`: cli, markdown, html, pdf outputs.

## Key patterns
- Zones-only entries (no Vercel mapping) are first-class: Cloudflare analytics
  still collected; Vercel section reports unconfigured for that domain.
- `zones.yaml` entries are alphabetically ordered by domain.
- `vercel_aliases` auto-derives `domain.split('.')[0]` slugs; explicit aliases
  (e.g. `purplecanary`) are additive.
- `zones.yaml` and `.env.local` are gitignored secrets; `zones.example.yaml`
  is the committed template (not auto-updated per domain addition).
