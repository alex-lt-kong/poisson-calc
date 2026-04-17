"""Application entry point for the Poisson Calculator API.

Creates the FastAPI app, mounts static files, registers CORS middleware,
includes the API router, and serves the frontend at the root path.
"""

import os

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

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
    """Serve the frontend index.html at the root path."""
    index_path = os.path.join(_static_dir, "index.html")
    return FileResponse(index_path)
