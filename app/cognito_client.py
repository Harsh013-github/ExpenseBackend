# It handles signup, login, token verification, and user management
import boto3
import os
import jwt
import requests
import json
from datetime import datetime, timezone
from typing import Dict, Optional, Any
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()

# This class encapsulates all AWS Cognito operations for user authentication
class CognitoClient:
    def __init__(self):
        self.region = os.getenv('AWS_COGNITO_REGION', 'us-east-1')
        self.user_pool_id = os.getenv('AWS_COGNITO_USER_POOL_ID')
        self.client_id = os.getenv('AWS_COGNITO_CLIENT_ID')
        
        if not all([self.user_pool_id, self.client_id]):
            raise ValueError("Cognito configuration missing. Run setup_cognito.py first.")
        
        self.cognito = boto3.client(
            'cognito-idp',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=self.region
        )
        
        self._jwks = None
    
    # This retrieves the JSON Web Key Set from Cognito for token verification
    def get_jwks(self):
        if self._jwks is None:
            jwks_url = f"https://cognito-idp.{self.region}.amazonaws.com/{self.user_pool_id}/.well-known/jwks.json"
            response = requests.get(jwks_url)
            self._jwks = response.json()
        return self._jwks
    
    # This creates a new user in Cognito and auto-confirms them without email verification
    def sign_up(self, email: str, password: str, name: str, role: str = "USER") -> Dict[str, Any]:
        try:
            response = self.cognito.sign_up(
                ClientId=self.client_id,
                Username=email,
                Password=password,
                UserAttributes=[
                    {'Name': 'email', 'Value': email},
                    {'Name': 'name', 'Value': name}
                ]
            )
            
            # Auto-confirm user (skip email verification)
            self.cognito.admin_confirm_sign_up(
                UserPoolId=self.user_pool_id,
                Username=email
            )

            login_result = self.login(email, password)
            
            return {
                'success': True,
                'message': 'User created and confirmed successfully',
                'user_id': response['UserSub'],
                'token': login_result.get('token'),
                'refresh_token': login_result.get('refresh_token'),
                'expires_in': login_result.get('expires_in'),
                'requires_confirmation': False,
                'user': login_result.get('user', {
                    'user_id': response['UserSub'],
                    'email': email,
                    'name': name,
                    'role': role,
                    'created_at': datetime.now(timezone.utc).isoformat()
                })
            }
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'UsernameExistsException':
                return {
                    'success': False,
                    'error': 'USER_EXISTS',
                    'message': 'User already exists'
                }
            else:
                return {
                    'success': False,
                    'error': error_code,
                    'message': str(e)
                }
        except Exception as e:
            return {
                'success': False,
                'error': 'SIGNUP_ERROR',
                'message': str(e)
            }
    
    # This authenticates a user and returns JWT tokens for session management
    def login(self, email: str, password: str) -> Dict[str, Any]:
        try:
            users = self.cognito.list_users(
                UserPoolId=self.user_pool_id,
                Filter=f'email = "{email}"',
                Limit=1
            )
            
            if not users['Users']:
                return {
                    'success': False,
                    'error': 'UserNotFoundException',
                    'message': 'User not found'
                }
            
            username = users['Users'][0]['Username']
            
            response = self.cognito.initiate_auth(
                ClientId=self.client_id,
                AuthFlow='USER_PASSWORD_AUTH',
                AuthParameters={
                    'USERNAME': username,
                    'PASSWORD': password
                }
            )
            
            tokens = response['AuthenticationResult']
            access_token = tokens['AccessToken']
            id_token = tokens['IdToken']
            refresh_token = tokens['RefreshToken']
            
            user_info = jwt.decode(id_token, options={"verify_signature": False})
            
            return {
                'success': True,
                'message': 'Login successful',
                'token': access_token,
                'id_token': id_token,
                'refresh_token': refresh_token,
                'expires_in': tokens['ExpiresIn'],
                'user': {
                    'id': user_info.get('sub'),
                    'email': user_info.get('email'),
                    'name': user_info.get('name'),
                    'role': user_info.get('custom:role', 'USER')
                }
            }
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NotAuthorizedException':
                return {
                    'success': False,
                    'error': 'INVALID_CREDENTIALS',
                    'message': 'Invalid email or password'
                }
            elif error_code == 'UserNotFoundException':
                return {
                    'success': False,
                    'error': 'USER_NOT_FOUND',
                    'message': 'User not found'
                }
            else:
                return {
                    'success': False,
                    'error': error_code,
                    'message': str(e)
                }
        except Exception as e:
            return {
                'success': False,
                'error': 'LOGIN_ERROR',
                'message': str(e)
            }
    
    # This verifies a JWT token's signature and extracts user information
    # Used to authenticate requests to protected endpoints
    def verify_token(self, token: str) -> Dict[str, Any]:
        try:
            header = jwt.get_unverified_header(token)
            kid = header['kid']
            
            jwks = self.get_jwks()
            key = None
            for jwk in jwks['keys']:
                if jwk['kid'] == kid:
                    key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(jwk))
                    break
            
            if not key:
                return {
                    'valid': False,
                    'error': 'KEY_NOT_FOUND',
                    'message': 'Unable to find appropriate key'
                }
            
            payload = jwt.decode(
                token,
                key,
                algorithms=['RS256'],
                issuer=f'https://cognito-idp.{self.region}.amazonaws.com/{self.user_pool_id}',
                options={"verify_aud": False}
            )
            
            if payload.get('client_id') != self.client_id:
                return {
                    'valid': False,
                    'error': 'INVALID_CLIENT',
                    'message': 'Token was not issued for this client'
                }
            
            try:
                user_response = self.cognito.get_user(AccessToken=token)
                user_attributes = {attr['Name']: attr['Value'] for attr in user_response['UserAttributes']}
                
                return {
                    'valid': True,
                    'user': {
                        'user_id': payload.get('sub'),
                        'id': payload.get('sub'),
                        'email': user_attributes.get('email'),
                        'name': user_attributes.get('name'),
                        'role': user_attributes.get('custom:role', 'USER'),
                        'username': payload.get('username')
                    },
                    'token_use': payload.get('token_use'),
                    'expires': payload.get('exp')
                }
            except Exception as user_error:
                return {
                    'valid': True,
                    'user': {
                        'user_id': payload.get('sub'),
                        'id': payload.get('sub'),
                        'username': payload.get('username'),
                        'role': 'USER'
                    },
                    'token_use': payload.get('token_use'),
                    'expires': payload.get('exp')
                }
            
        except jwt.ExpiredSignatureError:
            return {
                'valid': False,
                'error': 'TOKEN_EXPIRED',
                'message': 'Token has expired'
            }
        except jwt.InvalidTokenError as e:
            return {
                'valid': False,
                'error': 'INVALID_TOKEN',
                'message': str(e)
            }
        except Exception as e:
            return {
                'valid': False,
                'error': 'VERIFICATION_ERROR',
                'message': str(e)
            }
    
    def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        try:
            response = self.cognito.admin_initiate_auth(
                UserPoolId=self.user_pool_id,
                ClientId=self.client_id,
                AuthFlow='REFRESH_TOKEN_AUTH',
                AuthParameters={
                    'REFRESH_TOKEN': refresh_token
                }
            )
            
            tokens = response['AuthenticationResult']
            
            return {
                'success': True,
                'access_token': tokens['AccessToken'],
                'id_token': tokens['IdToken'],
                'expires_in': tokens['ExpiresIn']
            }
            
        except ClientError as e:
            return {
                'success': False,
                'error': e.response['Error']['Code'],
                'message': str(e)
            }
    
    def forgot_password(self, email: str) -> Dict[str, Any]:
        try:
            self.cognito.admin_reset_user_password(
                UserPoolId=self.user_pool_id,
                Username=email
            )
            
            return {
                'success': True,
                'message': 'Password reset email sent'
            }
            
        except ClientError as e:
            return {
                'success': False,
                'error': e.response['Error']['Code'],
                'message': str(e)
            }
    
    def get_user(self, access_token: str) -> Dict[str, Any]:
        try:
            response = self.cognito.get_user(AccessToken=access_token)
            
            attributes = {}
            for attr in response['UserAttributes']:
                attributes[attr['Name']] = attr['Value']
            
            return {
                'success': True,
                'user': {
                    'id': response['Username'],
                    'email': attributes.get('email'),
                    'name': attributes.get('name'),
                    'role': attributes.get('custom:role', 'USER'),
                    'email_verified': attributes.get('email_verified') == 'true'
                }
            }
            
        except ClientError as e:
            return {
                'success': False,
                'error': e.response['Error']['Code'],
                'message': str(e)
            }

_cognito_client = None

def get_cognito_client() -> CognitoClient:
    global _cognito_client
    if _cognito_client is None:
        _cognito_client = CognitoClient()
    return _cognito_client