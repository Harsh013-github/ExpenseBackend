# This is the main entry point for the Finance Tracker Backend API
# It sets up the FastAPI application with all necessary routes and middleware
import os
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from dotenv import load_dotenv
from . import auth, expenses, s3_routes
from .utils import ok, bad
from .sqs import start_worker, stop_worker

# This loads environment variables from the .env file in the parent directory
ROOT_ENV = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=ROOT_ENV, override=True)

# This sets the port and API prefix from environment variables
PORT = int(os.getenv("PORT", 8000))
API_PREFIX = os.getenv("API_PREFIX", "/api")

# This creates the FastAPI application instance with API documentation
# The docs are available at /api/docs (Swagger UI)
app = FastAPI(
    title="Finance Tracker Backend API",
    description="Personal Finance Management with AWS DynamoDB, S3 & Cognito Auth",
    version="1.0.1",
    openapi_url=f"{API_PREFIX}/openapi.json",
    docs_url=f"{API_PREFIX}/docs",
)

# This function customizes the OpenAPI schema to include JWT Bearer authentication
# It ensures all endpoints in the API docs show the authentication requirement
from fastapi.openapi.utils import get_openapi
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT"
        }
    }
    for path in openapi_schema["paths"].values():
        for op in path.values():
            if isinstance(op, dict):
                op["security"] = [{"BearerAuth": []}]
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# This middleware allows cross-origin requests from any domain
# It's essential for the React frontend to communicate with this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# This redirects the root URL to the API documentation page
@app.get("/")
def root_redirect():
    return RedirectResponse(url=f"{API_PREFIX}/docs")

# This endpoint provides an overview of all available API routes
@app.get(f"{API_PREFIX}/")
def index():
    return ok("Finance Tracker Swagger APi", {
        "auth": [f"{API_PREFIX}/auth/signup", f"{API_PREFIX}/auth/login"],
        "expenses": [
            f"{API_PREFIX}/expenses", 
            f"{API_PREFIX}/expenses/{{id}}"
        ],
        "s3": [
            f"{API_PREFIX}/s3/upload",
            f"{API_PREFIX}/s3/files"
        ],
        "docs": f"{API_PREFIX}/docs",
    })

# This registers all route modules with the main FastAPI app
# Each router handles a specific domain (auth, expenses, s3)
app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(expenses.router, prefix=API_PREFIX)
app.include_router(s3_routes.router, prefix=API_PREFIX)

# This function runs when the application starts up
@app.on_event("startup")
async def startup_event():
    pass

# This function runs when the application shuts down gracefully
@app.on_event("shutdown")
async def shutdown_event():
    pass

# This catches any unhandled exceptions and returns a standardized error response
@app.exception_handler(Exception)
async def on_exception(_req: Request, exc: Exception):
    return bad(500, "SERVER_ERROR", "Something went wrong", str(exc))