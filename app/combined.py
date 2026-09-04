"""Application publique réunissant l'interface FastAPI et le serveur MCP."""

from starlette.applications import Starlette
from starlette.routing import Mount

from app.main import app as web_app
from app.mcp_server import mcp


mcp_http_app = mcp.streamable_http_app()

# Les routes MCP restent en premier afin de conserver exactement /mcp.
# Toutes les autres adresses sont ensuite servies par l'application FastAPI.
http_app = Starlette(
    routes=[*mcp_http_app.routes, Mount("/", app=web_app)],
    lifespan=mcp_http_app.router.lifespan_context,
)
