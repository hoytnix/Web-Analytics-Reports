"""
Renderers package: terminal CLI output, HTML generation, Markdown generation, and PDF rendering.
"""

from .cli import render_cli_section
from .html import render_full_html_document, render_html_section
from .markdown import render_full_markdown_document, render_markdown_section
from .pdf import render_pdf

__all__ = [
    "render_cli_section",
    "render_html_section",
    "render_full_html_document",
    "render_markdown_section",
    "render_full_markdown_document",
    "render_pdf",
]
