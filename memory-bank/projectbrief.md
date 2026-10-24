# Project Brief — Cloudflare & Vercel Portfolio Analytics Reporter

## Core goals
Modular Python analytics reporting package for a Cloudflare + Vercel domain portfolio.
Integrates Cloudflare zone analytics, Cloudflare Web Analytics (RUM), Vercel web
analytics, and AI-powered executive briefs (Gemini cascade).

## Scope
- `cf_report/` package: config, models, utils, aggregator, cloudflare clients,
  vercel client, renderers (CLI/HTML/Markdown/PDF), CLI entrypoint.
- `zones.yaml` (gitignored): Cloudflare zone IDs + domains, Vercel project
  mappings, Vercel slug aliases.
- Output: terminal summary plus PDF / Markdown / HTML reports.

## Foundation
- Python >= 3.9, dependencies: requests, Jinja2, PyYAML (optional: weasyprint).
- Tests: `python3 -m unittest discover tests`.
- Reports are generated artifacts (`cloudflare_report_*`), kept out of git.
