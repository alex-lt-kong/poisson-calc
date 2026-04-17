"""Application entry point for the Poisson Calculator API.

Creates the FastAPI app, mounts static files, registers CORS middleware,
includes the API router, and serves the frontend at the root path.

Run directly:
    python -m app.main
    python -m app.main --config /path/to/config.json
"""

import json
import os

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.auth import token_store
from app.routes import router, validation_exception_handler

app = FastAPI(title="Poisson Calculator", version="1.0.0")

# Register custom validation error handler
app.add_exception_handler(RequestValidationError, validation_exception_handler)

# CORS middleware — permissive settings for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router)

# Mount static files directory
_static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
app.mount("/static", StaticFiles(directory=_static_dir), name="static")


@app.get("/", include_in_schema=False)
async def root() -> FileResponse:
    """Redirect or show a simple landing page."""
    index_path = os.path.join(_static_dir, "index.html")
    return FileResponse(index_path)


@app.get("/{token}", include_in_schema=False)
async def token_root(token: str) -> FileResponse:
    """Serve the frontend if the token in the URL is valid."""
    token_store.reload_if_modified()
    if not token_store.is_valid(token):
        raise HTTPException(status_code=401, detail="Invalid token")
    index_path = os.path.join(_static_dir, "index.html")
    return FileResponse(index_path)


def _load_server_config(config_path: str) -> dict:
    """Read server.host and server.port from the JSON config file."""
    defaults = {"host": "0.0.0.0", "port": 8000}
    try:
        with open(config_path, "r") as fh:
            data = json.load(fh)
        server = data.get("server", {})
        return {
            "host": server.get("host", defaults["host"]),
            "port": int(server.get("port", defaults["port"])),
        }
    except (OSError, json.JSONDecodeError, ValueError):
        return defaults


if __name__ == "__main__":
    import argparse

    import uvicorn

    parser = argparse.ArgumentParser(description="Poisson Calculator API")
    parser.add_argument(
        "--config",
        default=os.environ.get("CONFIG_FILE_PATH", "config.json"),
        help="Path to config.json (default: config.json)",
    )
    args = parser.parse_args()

    server_cfg = _load_server_config(args.config)
    print(f"Starting server on {server_cfg['host']}:{server_cfg['port']}")
    uvicorn.run(app, host=server_cfg["host"], port=server_cfg["port"])
