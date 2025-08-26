from fastapi import APIRouter, Depends, HTTPException, Request, Response
from typing import Dict, Any
import logging
from models.user_model import EmailModel, NewPasswordModel, UserModel
from repositorys.user_repo import UserRepository
from services.user_service import UserService
from middleware.auth import require_authentication, get_current_user_optional
from core.exceptions import AuthenticationError, ValidationError

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize services with dependency injection
user_repository = UserRepository()
user_service = UserService(user_repository)


@router.get("/")
async def index():
    """Health check endpoint"""
    return {"status": "ok", "data": "Hello World"}


@router.get("/profile")
async def profile(request: Request):
    """Get user profile with authentication"""
    try:
        user = await require_authentication(request)
        profile = user_service.get_user_profile(user.user.id)
        
        if profile:
            return {"status": "ok", "data": profile}
        else:
            return {"status": "ok", "data": user.user}
    except AuthenticationError as e:
        return {"status": "fail", "data": str(e.detail)}


@router.post("/signup")
async def signup(user: UserModel):
    """Sign up a new user"""
    try:
        result = user_service.sign_up(user)
        return result
    except ValidationError as e:
        return {"status": "fail", "data": str(e.detail)}
    except Exception as e:
        logger.error(f"Signup error: {str(e)}")
        return {"status": "fail", "data": "Registration failed"}


@router.post("/signin")
async def signin(user: UserModel, response: Response):
    """Sign in user"""
    try:
        result = user_service.sign_in(user, response)
        return result
    except AuthenticationError as e:
        return {"status": "fail", "data": str(e.detail)}
    except Exception as e:
        logger.error(f"Signin error: {str(e)}")
        return {"status": "fail", "data": "Authentication failed"}


@router.get("/confirm{token}")
async def confirm(token: str, response: Response):
    """Confirm email with token"""
    try:
        # Parse token parameters
        if "#" not in token:
            raise ValidationError("Invalid token format")
        
        token_part = token.split("#")[1]
        values = dict(item.split("=") for item in token_part.split("&"))
        
        # Set secure cookies
        if "access_token" in values:
            response.set_cookie(
                key="access_token",
                value=values["access_token"],
                httponly=True,
                secure=True,
                samesite="lax"
            )
        
        if "type" in values:
            response.set_cookie(
                key="type",
                value=values["type"],
                httponly=True,
                secure=True,
                samesite="lax"
            )
        
        logger.info("Email confirmation successful")
        return {"status": "ok", "data": values}
    except Exception as e:
        logger.error(f"Email confirmation error: {str(e)}")
        return {"status": "fail", "data": "Invalid confirmation token"}


@router.post("/change-password")
async def change_password(new_password: NewPasswordModel, response: Response):
    """Change user password"""
    try:
        # Validate password confirmation
        if new_password.new_password != new_password.confirm_password:
            return {"status": "fail", "data": "Passwords do not match"}
        
        result = user_service.change_password(new_password.new_password, response)
        return result
    except ValidationError as e:
        return {"status": "fail", "data": str(e.detail)}
    except Exception as e:
        logger.error(f"Password change error: {str(e)}")
        return {"status": "fail", "data": "Password change failed"}


@router.get("/logout")
async def logout(response: Response):
    """Sign out user"""
    try:
        result = user_service.sign_out(response)
        return result
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        return {"status": "fail", "data": "Logout failed"}


@router.post("/reset-password")
async def reset_password(email: EmailModel):
    """Reset password"""
    try:
        result = user_service.reset_password(email)
        return result
    except ValidationError as e:
        return {"status": "fail", "data": str(e.detail)}
    except Exception as e:
        logger.error(f"Password reset error: {str(e)}")
        return {"status": "fail", "data": "Password reset failed"}


@router.get("/me")
async def get_current_user_info(request: Request):
    """Get current user information"""
    try:
        user = await get_current_user_optional(request)
        if user:
            return {"status": "ok", "data": user.user}
        else:
            return {"status": "fail", "data": "Not authenticated"}
    except Exception as e:
        logger.error(f"Get user info error: {str(e)}")
        return {"status": "fail", "data": "Failed to get user information"}
