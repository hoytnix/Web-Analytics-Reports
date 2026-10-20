"""
PDF Renderer supporting in-process WeasyPrint and headless Chromium/Chrome fallbacks.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def render_pdf(
    html_content: str,
    output_pdf_path: str | Path,
    prefer_engine: Optional[str] = None,
) -> bool:
    """
    Render HTML content string to a PDF file.
    Tries in-process WeasyPrint first, then headless Chromium/Chrome as fallback.
    """
    out_path = Path(output_pdf_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"  \033[1m==> Rendering PDF ({out_path.name})...\033[0m")

    # 1. Try in-process WeasyPrint Python module
    if prefer_engine in (None, "weasyprint"):
        try:
            import weasyprint

            weasyprint.HTML(string=html_content).write_pdf(str(out_path))
            print(f"  \033[32m==> Finished: {out_path.name}\033[0m")
            return True
        except ImportError:
            logger.debug("weasyprint python package not importable.")
        except Exception as e:
            logger.warning(f"In-process WeasyPrint failed: {e}. Trying fallback engines.")

    # 2. If in-process failed or another engine requested, write to temp file
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(html_content)
        tmp_html = f.name

    try:
        # Check available CLI binaries
        if (prefer_engine == "weasyprint" or prefer_engine is None) and shutil.which("weasyprint"):
            res = subprocess.run(["weasyprint", tmp_html, str(out_path)], capture_output=True)
            if res.returncode == 0:
                print(f"  \033[32m==> Finished: {out_path.name}\033[0m")
                return True

        chrome_bin = None
        for candidate in ("chromium", "google-chrome", "chromium-browser"):
            if shutil.which(candidate):
                chrome_bin = candidate
                break

        if chrome_bin:
            cmd = [
                chrome_bin,
                "--headless",
                "--no-sandbox",
                "--disable-gpu",
                "--run-all-compositor-stages-before-draw",
                f"--print-to-pdf={out_path}",
                tmp_html,
            ]
            res = subprocess.run(cmd, capture_output=True)
            if res.returncode == 0:
                print(f"  \033[32m==> Finished: {out_path.name}\033[0m")
                return True

        logger.error("No working PDF rendering engine could generate the PDF.")
        return False
    finally:
        try:
            os.remove(tmp_html)
        except OSError:
            pass
