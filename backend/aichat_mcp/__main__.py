"""Run the AIChat MCP server.

    stdio (default; the AI app starts this process):
        uv --directory <repo>/backend run python -m aichat_mcp
        env: AICHAT_API_URL=http://localhost:8002/api/v1 (optional)

    standalone HTTP (normally not needed: the API server already serves MCP at /mcp):
        uv run python -m aichat_mcp --http --port 8003

No API key is configured here: each agent asks its user for its key and calls the connect tool.
"""
import argparse
import os

from aichat_mcp.client import DEFAULT_API_URL
from aichat_mcp.server import build_server


def main() -> None:
    parser = argparse.ArgumentParser(prog="aichat_mcp", description="AIChat MCP server")
    parser.add_argument("--http", action="store_true", help="serve Streamable HTTP instead of stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8003)
    args = parser.parse_args()

    server = build_server(os.environ.get("AICHAT_API_URL", DEFAULT_API_URL))
    if args.http:
        server.run("streamable-http", host=args.host, port=args.port, stateless_http=True)
    else:
        server.run("stdio")


if __name__ == "__main__":
    main()
