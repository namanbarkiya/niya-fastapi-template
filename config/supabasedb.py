import os
from supabase import create_client, Client
import dotenv
from typing import Optional
import logging

dotenv.load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseManager:
    """Singleton pattern for database connection management"""
    _instance: Optional['DatabaseManager'] = None
    _client: Optional[Client] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def get_client(self) -> Client:
        """Get or create Supabase client with connection pooling"""
        if self._client is None:
            try:
                url: str = os.environ.get("SUPABASE_URL")
                key: str = os.environ.get("SUPABASE_KEY")
                
                if not url or not key:
                    raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in environment variables")
                
                self._client = create_client(url, key)
                logger.info("Supabase client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Supabase client: {str(e)}")
                raise
        return self._client
    
    def reset_client(self):
        """Reset client for testing or reconnection"""
        self._client = None
        logger.info("Supabase client reset")


# Global database manager instance
db_manager = DatabaseManager()


def get_supabase_client() -> Client:
    """Get the Supabase client with proper error handling"""
    try:
        return db_manager.get_client()
    except Exception as e:
        logger.error(f"Database connection error: {str(e)}")
        raise


# Backward compatibility
def supabase_db() -> Client:
    """Legacy function for backward compatibility"""
    return get_supabase_client()
