# Product Context — Portfolio Reporter

## Problem domain
One consolidated analytics report across all portfolio domains, covering edge
traffic (Cloudflare), real-user traffic (Cloudflare RUM), and Vercel web
analytics, with an AI executive brief on top.

## User flows
1. Configure secrets in `.env.local` and zones/projects in `zones.yaml`.
2. Run `./report.py [24h|48h|4d|7d|30d|all] [--format pdf|md|html|all]`.
3. Read terminal summary; open generated PDF/Markdown/HTML report.

## UX goals
- Single command produces the full portfolio picture.
- New portfolio domains are added in `zones.yaml` only; no code changes needed.
- Non-Vercel domains (e.g. Cloudflare Workers apps) work as zones-only entries
  with no `vercel_projects` / `vercel_aliases` mapping.
