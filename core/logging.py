import logging
import sys
from typing import Dict, Any
from config.settings import settings


def setup_logging() -> None:
    """Setup comprehensive logging configuration"""
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level))
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler for production
    if settings.environment == "production":
        file_handler = logging.FileHandler("app.log")
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    # Suppress noisy loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


class APILogger:
    """Custom logger for API operations"""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
    
    def log_request(self, method: str, path: str, user_id: str = None) -> None:
        """Log API request"""
        user_info = f" (user: {user_id})" if user_id else ""
        self.logger.info(f"API Request: {method} {path}{user_info}")
    
    def log_response(self, method: str, path: str, status_code: int, user_id: str = None) -> None:
        """Log API response"""
        user_info = f" (user: {user_id})" if user_id else ""
        self.logger.info(f"API Response: {method} {path} -> {status_code}{user_info}")
    
    def log_error(self, error: Exception, context: Dict[str, Any] = None) -> None:
        """Log error with context"""
        context_str = f" Context: {context}" if context else ""
        self.logger.error(f"Error: {str(error)}{context_str}")
    
    def log_auth_event(self, event: str, user_id: str = None, success: bool = True) -> None:
        """Log authentication events"""
        status = "success" if success else "failed"
        user_info = f" (user: {user_id})" if user_id else ""
        self.logger.info(f"Auth Event: {event} - {status}{user_info}")


# Initialize logging
setup_logging() 