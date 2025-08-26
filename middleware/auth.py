from fastapi import Request, Response, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Dict, Any
import logging
from config.supabasedb import get_supabase_client
from core.exceptions import AuthenticationError, AuthorizationError

logger = logging.getLogger(__name__)
security = HTTPBearer()


class AuthMiddleware:
    """Authentication middleware with proper token validation"""
    
    def __init__(self):
        self.supabase = get_supabase_client()
    
    async def get_current_user(self, credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
        """Validate JWT token and return user data"""
        try:
            token = credentials.credentials
            user = self.supabase.auth.get_user(token)
            return user
        except Exception as e:
            logger.error(f"Token validation failed: {str(e)}")
            raise AuthenticationError("Invalid authentication token")
    
    async def get_current_user_from_cookie(self, request: Request) -> Optional[Dict[str, Any]]:
        """Get current user from cookie token"""
        try:
            token = request.cookies.get("access_token")
            if not token:
                return None
            
            user = self.supabase.auth.get_user(token)
            return user
        except Exception as e:
            logger.error(f"Cookie token validation failed: {str(e)}")
            return None
    
    def set_auth_cookies(self, response: Response, session_data: Dict[str, Any]) -> None:
        """Set secure authentication cookies"""
        try:
            access_token = session_data.get("access_token")
            if access_token:
                response.set_cookie(
                    key="access_token",
                    value=access_token,
                    httponly=True,
                    secure=True,  # Use HTTPS in production
                    samesite="lax",
                    max_age=3600  # 1 hour
                )
        except Exception as e:
            logger.error(f"Failed to set auth cookies: {str(e)}")
    
    def clear_auth_cookies(self, response: Response) -> None:
        """Clear authentication cookies"""
        response.delete_cookie("access_token")
        response.delete_cookie("type")


# Global auth middleware instance
auth_middleware = AuthMiddleware()


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """Dependency for getting current user from Bearer token"""
    return await auth_middleware.get_current_user(credentials)


async def get_current_user_optional(request: Request) -> Optional[Dict[str, Any]]:
    """Dependency for getting current user from cookie (optional)"""
    return await auth_middleware.get_current_user_from_cookie(request)


async def require_authentication(request: Request) -> Dict[str, Any]:
    """Dependency that requires authentication"""
    user = await auth_middleware.get_current_user_from_cookie(request)
    if not user:
        raise AuthenticationError("Authentication required")
    return user 