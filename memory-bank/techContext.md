# Tech Context — Portfolio Reporter

## Stack
- Python >= 3.9, `requests`, `Jinja2`, `PyYAML`, optional `weasyprint`.
- Package manager: pnpm rule does not apply (no JS tooling in repo);
  verification is `python3 -m unittest discover tests`.
- Entry: `./report.py` / `python3 -m cf_report`.

## Environment constraints
- Secrets in `.env.local` (`CF_API_TOKEN`, `CF_ACCOUNT_ID`, optional
  `VERCEL_TOKEN`, `GEMINI_API_KEY`); never committed.
- Zone/project inventory in `zones.yaml` (gitignored); template in
  `zones.example.yaml`.
- Generated reports (`cloudflare_report_*`, `*.pdf`) are gitignored artifacts.

## Dependencies
- Cloudflare GraphQL + REST APIs; Vercel REST/CLI; Gemini cascade for briefs.
- Verification: `python3 -m unittest discover tests` (covers formatting,
  time windows, RUM matching, aggregation + rendering).
