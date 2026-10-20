"""
Gemini AI integration package for Cloudflare & Vercel analytics reporting.
"""

from .client import DEFAULT_MODELS_CASCADE, GeminiClient

__all__ = ["GeminiClient", "DEFAULT_MODELS_CASCADE"]
