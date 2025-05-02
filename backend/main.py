# --- START OF FILE main.py ---
"""
backend.main
------------

Serves as the main entry point for the MOSS backend FastAPI application.

This module initializes the FastAPI application instance, configures middleware
(like CORS), sets up application-wide logging, defines startup/shutdown event
handlers, includes API routers, and provides basic health check endpoints.
"""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import the main API router aggregate from the v1 API definition.
from backend.api.v1.api import api_router as api_router_v1
# Import the centralized logging configuration function.
from backend.config.logging_config import setup_logging

# --- Initialize Logging ---
# Configure the application's logging system early, before any other parts
# of the application might attempt to log. Specifies the log file for API events.
setup_logging(log_file_name="moss_api.log")

# Obtain the logger instance *after* setup_logging has configured the root logger.
logger = logging.getLogger(__name__)

# --- FastAPI Application Initialization ---
# Instantiate the core FastAPI application.
app = FastAPI(
    title="MOSS - Map of Open Source Science API",
    description="API for ingesting and querying data about open source scientific software and its relationships.",
    version="0.1.0", # Consider linking this to a version managed elsewhere (e.g., pyproject.toml)
    # Additional OpenAPI metadata can be added here (e.g., docs_url, redoc_url)
)

# --- CORS (Cross-Origin Resource Sharing) Middleware ---
# Configure which frontend origins are allowed to interact with the API.
# This is crucial for web applications served from different domains/ports
# than the API.
# Define allowed origins (adjust for development/production environments).
origins = [
    "http://localhost",         # Common local development origin
    "http://localhost:5173",    # Default Vite dev server port
    "http://localhost:3000",    # Default React dev server port
    # Add production frontend URLs here, e.g., "https://moss.example.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,          # List of allowed origins.
    allow_credentials=True,         # Allow cookies to be included in requests.
    allow_methods=["*"],            # Allow all standard HTTP methods (GET, POST, etc.).
    allow_headers=["*"],            # Allow all request headers.
)
# --- End CORS Middleware ---

# --- Application Lifecycle Event Handlers ---

@app.on_event("startup")
async def startup_event():
    """
    Asynchronous actions to perform when the FastAPI application starts.
    """
    # Logging is already configured globally at the module level.
    logger.info("MOSS API application starting up...")
    # Potential future actions: Initialize database connections pools, load caches, etc.

@app.on_event("shutdown")
async def shutdown_event():
    """
    Asynchronous actions to perform when the FastAPI application shuts down gracefully.
    """
    logger.info("MOSS API application shutting down...")
    # Potential future actions: Close database connections, flush logs, etc.

# --- Basic Health Check Endpoint ---

@app.get("/health", tags=["Health"], summary="API Health Status")
async def health_check():
    """
    Provides a basic health check endpoint to verify if the API is running
    and responsive. Typically used by monitoring systems or load balancers.
    """
    logger.debug("Health check endpoint '/health' invoked.")
    return {"status": "ok"}

# --- Include API Routers ---
# Mount the API version 1 router under the '/api/v1' prefix.
# All routes defined in api_router_v1 will be accessible relative to this path.
app.include_router(api_router_v1, prefix="/api/v1")

# --- How to Run ---
# To run the development server:
# uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
#
# --reload: Enables auto-reloading when code changes are detected.
# --host 0.0.0.0: Makes the server accessible on the network (not just localhost).
# --port 8000: Specifies the port to listen on.
# --- END OF FILE main.py ---