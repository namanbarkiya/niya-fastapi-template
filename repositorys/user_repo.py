from fastapi import Response
from typing import Dict, Any, Optional
import logging
from config.supabasedb import get_supabase_client
from core.exceptions import handle_supabase_error, AuthenticationError, ValidationError

logger = logging.getLogger(__name__)


class UserRepository:
    """User repository with proper error handling and connection pooling"""
    
    def __init__(self):
        self.supabase = get_supabase_client()
    
    def sign_up_user(self, user_data: Dict[str, str]) -> Dict[str, Any]:
        """Sign up a new user with proper error handling"""
        try:
            user_new = self.supabase.auth.sign_up({
                "email": user_data["email"],
                "password": user_data["password"]
            })
            logger.info(f"User signed up successfully: {user_data['email']}")
            return {"status": "success", "data": user_new}
        except Exception as e:
            logger.error(f"Sign up failed for {user_data['email']}: {str(e)}")
            raise handle_supabase_error(e)
    
    def sign_in_user(self, user_data: Dict[str, str]) -> Dict[str, Any]:
        """Sign in user with proper error handling"""
        try:
            user_sign = self.supabase.auth.sign_in_with_password({
                "email": user_data["email"],
                "password": user_data["password"]
            })
            logger.info(f"User signed in successfully: {user_data['email']}")
            return {"status": "success", "data": user_sign}
        except Exception as e:
            logger.error(f"Sign in failed for {user_data['email']}: {str(e)}")
            raise handle_supabase_error(e)
    
    def sign_out(self) -> Dict[str, str]:
        """Sign out user with proper error handling"""
        try:
            self.supabase.auth.sign_out()
            logger.info("User signed out successfully")
            return {"status": "success", "message": "Sign out successfully"}
        except Exception as e:
            logger.error(f"Sign out failed: {str(e)}")
            raise handle_supabase_error(e)
    
    def reset_password(self, email: str) -> Dict[str, Any]:
        """Reset password with proper error handling"""
        try:
            reset_result = self.supabase.auth.reset_password_email(email)
            logger.info(f"Password reset email sent to: {email}")
            return {"status": "success", "data": reset_result}
        except Exception as e:
            logger.error(f"Password reset failed for {email}: {str(e)}")
            raise handle_supabase_error(e)
    
    def change_password(self, new_password: str) -> Dict[str, Any]:
        """Change user password with proper error handling"""
        try:
            password_update = self.supabase.auth.update_user({
                "password": new_password
            })
            logger.info("Password changed successfully")
            return {"status": "success", "data": password_update}
        except Exception as e:
            logger.error(f"Password change failed: {str(e)}")
            raise handle_supabase_error(e)
    
    def get_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user profile from database"""
        try:
            result = self.supabase.table("users").select("*").eq("id", user_id).single().execute()
            return result.data if result.data else None
        except Exception as e:
            logger.error(f"Failed to get user profile for {user_id}: {str(e)}")
            return None
    
    def update_user_profile(self, user_id: str, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update user profile"""
        try:
            result = self.supabase.table("users").update(profile_data).eq("id", user_id).execute()
            logger.info(f"User profile updated for {user_id}")
            return {"status": "success", "data": result.data}
        except Exception as e:
            logger.error(f"Failed to update user profile for {user_id}: {str(e)}")
            raise handle_supabase_error(e)
