from fastapi import Request, HTTPException, status
from typing import Dict, Tuple
import time
import logging
from config.settings import settings

logger = logging.getLogger(__name__)


class RateLimiter:
    """Simple in-memory rate limiter"""
    
    def __init__(self):
        self.requests: Dict[str, list] = {}
        self.cleanup_interval = 60  # Clean up old entries every 60 seconds
        self.last_cleanup = time.time()
    
    def is_allowed(self, client_id: str, max_requests: int = None) -> bool:
        """Check if request is allowed"""
        current_time = time.time()
        
        # Cleanup old entries periodically
        if current_time - self.last_cleanup > self.cleanup_interval:
            self._cleanup_old_entries(current_time)
            self.last_cleanup = current_time
        
        # Get client requests
        if client_id not in self.requests:
            self.requests[client_id] = []
        
        # Remove old requests (older than 1 minute)
        self.requests[client_id] = [
            req_time for req_time in self.requests[client_id]
            if current_time - req_time < 60
        ]
        
        # Check rate limit
        max_requests = max_requests or settings.rate_limit_per_minute
        if len(self.requests[client_id]) >= max_requests:
            return False
        
        # Add current request
        self.requests[client_id].append(current_time)
        return True
    
    def _cleanup_old_entries(self, current_time: float) -> None:
        """Remove old entries to prevent memory leaks"""
        old_entries = []
        for client_id, requests in self.requests.items():
            # Remove entries older than 2 minutes
            self.requests[client_id] = [
                req_time for req_time in requests
                if current_time - req_time < 120
            ]
            if not self.requests[client_id]:
                old_entries.append(client_id)
        
        # Remove empty client entries
        for client_id in old_entries:
            del self.requests[client_id]


# Global rate limiter instance
rate_limiter = RateLimiter()


def get_client_id(request: Request) -> str:
    """Get client identifier for rate limiting"""
    # Use IP address as client identifier
    client_ip = request.client.host if request.client else "unknown"
    
    # For better identification, you could also include user agent
    user_agent = request.headers.get("user-agent", "")
    
    return f"{client_ip}:{user_agent[:50]}"


async def rate_limit_middleware(request: Request, call_next):
    """Rate limiting middleware"""
    client_id = get_client_id(request)
    
    if not rate_limiter.is_allowed(client_id):
        logger.warning(f"Rate limit exceeded for client: {client_id}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please try again later."
        )
    
    response = await call_next(request)
    return response 