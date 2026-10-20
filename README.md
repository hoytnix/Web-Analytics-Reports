# Cloudflare & Vercel Portfolio Analytics Reporter (Python v2.0)

A modular, DRY Python analytics reporting package for Cloudflare and Vercel. Integrates:
- **Cloudflare Zone Analytics** (Edge requests, bandwidth, cache efficiency, threats, status codes, protocols, top paths, probes)
- **Cloudflare Web Analytics (RUM)** (Client-side pageviews, visits, traffic sources, referrers, device form factors, browsers)
- **Vercel Web Analytics** (Pageviews, unique visitors, acquisition referrers)

## Package Structure

```
Report/
├── cf_report/
│   ├── __init__.py
│   ├── config.py              # Configurations, zones loader, project maps, cadences
│   ├── models.py              # Strongly-typed dataclasses for metrics & sections
│   ├── utils.py               # Shared formatters (bytes, numbers, percentages, dates)
│   ├── aggregator.py          # Aggregates raw GraphQL/REST outputs into KPIs & breakdowns
│   ├── cloudflare/
│   │   ├── client.py          # Cloudflare API client (GraphQL & REST)
│   │   ├── zone_analytics.py  # GraphQL queries for zone rollups & deep breakdowns
│   │   └── web_analytics.py   # Cloudflare Web Analytics (RUM) telemetry
│   ├── vercel/
│   │   └── client.py          # Vercel Web Analytics (REST API & CLI)
│   ├── renderers/
│   │   ├── cli.py             # Color terminal report renderer
│   │   ├── html.py            # Jinja2-based HTML renderer
│   │   ├── markdown.py        # GitHub Flavored Markdown renderer
│   │   └── pdf.py             # PDF renderer (WeasyPrint / Chromium)
│   ├── templates/
│   │   ├── document.html.j2   # Landscape PDF print layout template
│   │   └── section.html.j2    # Section KPIs & multi-node breakdown template
│   ├── cli.py                 # CLI argument parsing and orchestration
│   └── __main__.py            # python3 -m cf_report entrypoint
├── report.py                  # Standalone executable CLI runner
├── zones.example.yaml         # Configuration template for monitored zones & projects
├── .env.example               # Environment secrets template
└── tests/
    └── test_report.py         # Unit test suite
```

## Setup & Configuration

1. **Configure Environment Secrets:**
   ```bash
   cp .env.example .env.local
   # Edit .env.local and populate CF_API_TOKEN, CF_ACCOUNT_ID, and optional VERCEL_TOKEN
   ```

2. **Configure Zones & Projects:**
   ```bash
   cp zones.example.yaml zones.yaml
   # Edit zones.yaml and populate your Cloudflare Zone IDs and Vercel Project IDs
   ```
   *Note: Both `.env.local` and `zones.yaml` are ignored by Git to keep all credentials and IDs safe.*
```

## Usage

### Basic Commands

```bash
# Run consolidated report (all 5 periods) generating PDF
./report.py

# Run specific cadence
./report.py 24h
./report.py 48h
./report.py 4d
./report.py 7d
./report.py 30d
```

### Output Formats

```bash
# Generate Markdown (.md) report
./report.py 24h --markdown

# Generate specific format (pdf, markdown/md, html, all)
./report.py 7d --format md
./report.py 7d --format all

# Custom output file path
./report.py 24h -o my_report.md
./report.py 24h -o my_report.pdf

# Terminal report only (no PDF generated)
./report.py 24h --no-pdf

# Save HTML report only
./report.py 24h --html-only
```

### CLI Options

| Flag | Description |
| :--- | :--- |
| `target` | Period cadence: `24h`, `48h`, `4d`, `7d`, `30d`, `all` (default: `all`) |
| `-o, --output` | Custom destination file path (`.pdf`, `.md`, or `.html`) |
| `--format` | Output format: `pdf`, `markdown`, `md`, `html`, or `all` |
| `--markdown, --md` | Flag to generate Markdown report |
| `--no-pdf` | Skip PDF rendering and show terminal summary only |
| `--html-only` | Save HTML document without compiling PDF |
| `--no-parallel` | Run zone queries sequentially instead of multithreaded |
| `--cf-token` | Override Cloudflare API token |
| `--cf-account` | Override Cloudflare Account ID |
| `--vercel-token`| Override Vercel API token |
| `--engine` | Force PDF engine (`weasyprint`, `chromium`, `google-chrome`) |

### Running Unit Tests

```bash
python3 -m unittest discover tests
```
