# This file contains utility functions used throughout the backend
# It provides standardized response formats and helper functions
import os
import re
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

load_dotenv()

# This function creates a standardized success response with data
def ok(message: str = "OK", data=None, status_code: int = 200):
    return JSONResponse({
        "success": True, 
        "message": message, 
        "data": data
    }, status_code=status_code)

# This function creates a standardized error response with error details
def bad(status_code: int, code: str, message: str, details=None):
    return JSONResponse({
        "success": False, 
        "error": {
            "code": code, 
            "message": message, 
            "details": details
        }
    }, status_code=status_code)

# This function safely retrieves environment variables with optional defaults
def get_env_var(key: str, default: str = None, required: bool = False):
    value = os.getenv(key, default)
    if required and not value:
        raise ValueError(f"Required environment variable {key} is not set")
    return value

# This function validates email format using regex pattern
def validate_email(email: str) -> bool:
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None