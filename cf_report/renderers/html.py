"""
HTML Report generator using Jinja2 templates.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List

import jinja2

from ..models import ReportSection
from ..utils import format_bytes, format_number

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


def get_jinja_env() -> jinja2.Environment:
    """Create and configure Jinja2 environment."""
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=jinja2.select_autoescape(["html", "xml"]),
    )
    env.filters["bytesfmt"] = format_bytes
    env.filters["numfmt"] = format_number
    return env


def render_html_section(section: ReportSection, env: jinja2.Environment | None = None) -> str:
    """Render a single section to an HTML string."""
    env = env or get_jinja_env()
    template = env.get_template("section.html.j2")
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    return template.render(section=section, generated_at=generated_at)


def render_full_html_document(
    doc_title: str,
    sections: List[ReportSection],
) -> str:
    """Render full HTML document containing one or more report sections."""
    env = get_jinja_env()
    doc_template = env.get_template("document.html.j2")
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    rendered_sections = [render_html_section(s, env) for s in sections]

    return doc_template.render(
        doc_title=doc_title,
        generated_at=generated_at,
        sections=rendered_sections,
    )
