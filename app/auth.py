# This module handles all authentication-related operations using AWS Cognito
# It provides signup, login, and token verification functionality
import os
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from .utils import ok, bad
from .cognito_client import get_cognito_client

# This sets up JWT Bearer token authentication for protected routes
security = HTTPBearer()
router = APIRouter(prefix="/auth", tags=["Auth"])
# This checks if AWS Cognito credentials are properly configured
COGNITO_CONFIGURED = (
    os.getenv('AWS_COGNITO_USER_POOL_ID') is not None and
    os.getenv('AWS_COGNITO_CLIENT_ID') is not None
)

# This defines the data structure for user signup requests
class SignupBody(BaseModel):
    email: str
    password: str
    name: str

# This defines the data structure for user login requests
class LoginBody(BaseModel):
    email: str
    password: str

# This dependency function verifies JWT tokens and extracts user information
# It's used to protect routes that require authentication
def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not COGNITO_CONFIGURED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service not configured"
        )
    
    try:
        cognito = get_cognito_client()
        result = cognito.verify_token(credentials.credentials)
        
        if not result['valid']:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=result.get('message', 'Invalid token'),
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        return result['user']
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"}
        )

# This endpoint handles user registration with email, password, and name
# It creates a new user in AWS Cognito and auto-confirms them
@router.post("/signup")
def signup(body: SignupBody):
    if not COGNITO_CONFIGURED:
        return bad(503, "SERVICE_UNAVAILABLE", "Authentication service not configured")
    
    try:
        cognito = get_cognito_client()
        result = cognito.sign_up(
            email=body.email,
            password=body.password,
            name=body.name,
            role="USER"
        )
        
        if result['success']:
            return ok(result['message'], {
                "token": result.get('token'),
                "user": result['user'],
                "requires_confirmation": result.get('requires_confirmation', False)
            })
        else:
            return bad(400, result.get('error', 'SIGNUP_FAILED'), result['message'])
            
    except Exception as e:
        return bad(500, "SIGNUP_EXCEPTION", "Unexpected error during signup", str(e))

# This endpoint authenticates users and returns JWT tokens for session management
# Tokens expire after 1 hour and include user information
@router.post("/login") 
def login(body: LoginBody):
    if not COGNITO_CONFIGURED:
        return bad(503, "SERVICE_UNAVAILABLE", "Authentication service not configured")
    
    try:
        cognito = get_cognito_client()
        result = cognito.login(body.email, body.password)
        
        if result['success']:
            return ok(result['message'], {
                "token": result['token'],
                "refresh_token": result.get('refresh_token'),
                "expires_in": result.get('expires_in'),
                "user": result['user']
            })
        else:
            return bad(401, result.get('error', 'LOGIN_FAILED'), result['message'])
                
    except Exception as e:
        return bad(500, "LOGIN_EXCEPTION", "Unexpected error during login", str(e))