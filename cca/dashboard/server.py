"""
Simple HTTP server to serve the dashboard static files.
"""

import asyncio
import os
from pathlib import Path

try:
    from aiohttp import web
except ImportError:
    web = None

import structlog

logger = structlog.get_logger(__name__)


async def handle_index(request):
    """Serve the index.html."""
    static_dir = Path(__file__).parent / "static"
    return web.FileResponse(static_dir / "index.html")


def start_dashboard(port: int = 8080):
    """
    Start the dashboard server. Requires aiohttp to be installed.
    """
    if web is None:
        logger.error("aiohttp is required to run the dashboard server. Run `pip install aiohttp`.")
        return

    static_dir = Path(__file__).parent / "static"
    if not static_dir.exists():
        logger.error(f"Static directory not found at {static_dir}")
        return

    app = web.Application()
    app.router.add_get("/", handle_index)
    app.router.add_static("/static/", path=static_dir, name="static")

    logger.info("dashboard_server.starting", port=port)
    web.run_app(app, port=port, print=None)


if __name__ == "__main__":
    start_dashboard()
