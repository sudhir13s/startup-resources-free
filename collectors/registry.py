"""Collector registry — single source of truth for which collectors run."""

from __future__ import annotations

from collectors.ai_apis.groq import GroqCollector
from collectors.base import CollectorRegistry
from collectors.cloud.render import RenderCollector
from collectors.cloud.vercel import VercelCollector

REGISTRY = CollectorRegistry()
REGISTRY.register(VercelCollector())
REGISTRY.register(RenderCollector())
REGISTRY.register(GroqCollector())
