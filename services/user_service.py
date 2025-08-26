from fastapi import Request, Response
from typing import Dict, Any, Optional
import logging
from models.user_model import EmailModel, UserModel
from repositorys.user_repo import UserRepository
from middleware.auth import auth_middleware
from core.exceptions import AuthenticationError, ValidationError

logger = logging.getLogger(__name__)


class UserService:
    """User service with proper business logic and error handling"""
    
    def __init__(self, user_repository: UserRepository) -> None:
        self.user_repository = user_repository
    
    def sign_up(self, user: UserModel) -> Dict[str, Any]:
        """Sign up a new user with validation"""
        try:
            # Validate email format
            if not self._is_valid_email(user.email):
                raise ValidationError("Invalid email format")
            
            # Validate password strength
            if not self._is_valid_password(user.password):
                raise ValidationError("Password must be at least 8 characters long")
            
            user_data = {"email": user.email, "password": user.password}
            result = self.user_repository.sign_up_user(user_data)
            logger.info(f"User service: Sign up successful for {user.email}")
            return result
        except Exception as e:
            logger.error(f"User service: Sign up failed for {user.email}: {str(e)}")
            raise
    
    def sign_in(self, user: UserModel, response: Response) -> Dict[str, Any]:
        """Sign in user with secure cookie handling"""
        try:
            user_data = {"email": user.email, "password": user.password}
            result = self.user_repository.sign_in_user(user_data)
            
            # Set secure cookies only if authentication was successful
            if result.get("status") == "success" and result.get("data"):
                session_data = result["data"]
                if hasattr(session_data, 'session') and session_data.session:
                    auth_middleware.set_auth_cookies(response, {
                        "access_token": session_data.session.access_token
                    })
                    logger.info(f"User service: Sign in successful for {user.email}")
                else:
                    logger.warning(f"User service: No session data for {user.email}")
            
            return result
        except Exception as e:
            logger.error(f"User service: Sign in failed for {user.email}: {str(e)}")
            raise
    
    def sign_out(self, response: Response) -> Dict[str, str]:
        """Sign out user and clear cookies"""
        try:
            result = self.user_repository.sign_out()
            auth_middleware.clear_auth_cookies(response)
            logger.info("User service: Sign out successful")
            return result
        except Exception as e:
            logger.error(f"User service: Sign out failed: {str(e)}")
            raise
    
    def reset_password(self, email: EmailModel) -> Dict[str, Any]:
        """Reset password with validation"""
        try:
            if not self._is_valid_email(email.email):
                raise ValidationError("Invalid email format")
            
            result = self.user_repository.reset_password(email.email)
            logger.info(f"User service: Password reset initiated for {email.email}")
            return result
        except Exception as e:
            logger.error(f"User service: Password reset failed for {email.email}: {str(e)}")
            raise
    
    def change_password(self, new_password: str, response: Response) -> Dict[str, Any]:
        """Change password with validation"""
        try:
            if not self._is_valid_password(new_password):
                raise ValidationError("Password must be at least 8 characters long")
            
            result = self.user_repository.change_password(new_password)
            auth_middleware.clear_auth_cookies(response)
            logger.info("User service: Password changed successfully")
            return result
        except Exception as e:
            logger.error(f"User service: Password change failed: {str(e)}")
            raise
    
    def get_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user profile"""
        try:
            profile = self.user_repository.get_user_profile(user_id)
            if profile:
                logger.info(f"User service: Profile retrieved for {user_id}")
            return profile
        except Exception as e:
            logger.error(f"User service: Failed to get profile for {user_id}: {str(e)}")
            return None
    
    def update_user_profile(self, user_id: str, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update user profile"""
        try:
            result = self.user_repository.update_user_profile(user_id, profile_data)
            logger.info(f"User service: Profile updated for {user_id}")
            return result
        except Exception as e:
            logger.error(f"User service: Failed to update profile for {user_id}: {str(e)}")
            raise
    
    def _is_valid_email(self, email: str) -> bool:
        """Validate email format"""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    def _is_valid_password(self, password: str) -> bool:
        """Validate password strength"""
        return len(password) >= 8
