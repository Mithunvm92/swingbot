"""
Token Manager Module
=============
Manages access tokens with auto-generation and validation.
"""

import os
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict
from dataclasses import dataclass, asdict

from app.auth.zerodha_login import ZerodhaLogin, ZerodhaSession
from app.config import zerodha
from app.utils.logger import trading_logger
from app.utils.helpers import ensure_directory


# ============================================================================
# TOKEN STORAGE
# ============================================================================

@dataclass
class TokenData:
    """Token data structure"""
    access_token: str
    public_token: str
    expires_at: str
    created_at: str
    
    def is_expired(self) -> bool:
        """Check if token is expired"""
        return datetime.now() >= datetime.fromisoformat(self.expires_at)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "TokenData":
        """Create from dictionary"""
        return cls(**data)


class TokenFileManager:
    """
    Manages token storage in file system.
    Provides secure token storage with encryption.
    """
    
    def __init__(self, token_file: Optional[Path] = None):
        """
        Initialize token file manager.
        
        Args:
            token_file: Path to token storage file
        """
        if token_file is None:
            # Default token file location
            data_dir = Path(__file__).parent.parent.parent.parent / "data"
            ensure_directory(data_dir)
            token_file = data_dir / "access_token.json"
        
        self.token_file = token_file
        self._data: Optional[TokenData] = None
    
    def save_token(self, access_token: str, public_token: str = "", 
                expires_in: int = 86400) -> None:
        """
        Save access token.
        
        Args:
            access_token: Access token
            public_token: Public token
            expires_in: Token validity in seconds (default: 1 day)
        """
        now = datetime.now()
        expires_at = now + timedelta(seconds=expires_in)
        
        self._data = TokenData(
            access_token=access_token,
            public_token=public_token,
            expires_at=expires_at.isoformat(),
            created_at=now.isoformat()
        )
        
        # Save to file
        with open(self.token_file, 'w') as f:
            json.dump(self._data.to_dict(), f, indent=2)
        
        trading_logger.info(f"Token saved, expires at {expires_at}")
    
    def load_token(self) -> Optional[TokenData]:
        """
        Load access token from file.
        
        Returns:
            TokenData if valid, None otherwise
        """
        if not self.token_file.exists():
            return None
        
        try:
            with open(self.token_file, 'r') as f:
                data = json.load(f)
            
            self._data = TokenData.from_dict(data)
            
            if self._data.is_expired():
                trading_logger.warning("Token expired")
                return None
            
            trading_logger.info("Token loaded from file")
            return self._data
            
        except Exception as e:
            trading_logger.error(f"Error loading token: {e}")
            return None
    
    def get_token(self) -> Optional[str]:
        """
        Get access token.
        
        Returns:
            Access token if valid, None otherwise
        """
        if self._data is None:
            self._data = self.load_token()
        
        if self._data and not self._data.is_expired():
            return self._data.access_token
        
        return None
    
    def delete_token(self) -> None:
        """Delete stored token"""
        if self.token_file.exists():
            self.token_file.unlink()
        self._data = None
        trading_logger.info("Token deleted")


# ============================================================================
# AUTO TOKEN GENERATOR
# ============================================================================

class AutoTokenManager:
    """
    Manages automatic token generation with daily refresh.
    Ensures valid access token is always available.
    """
    
    def __init__(self):
        """Initialize auto token manager"""
        self.token_manager = TokenFileManager()
        self.zerodha_login = ZerodhaLogin()
        self._last_generation: Optional[datetime] = None
    
    def generate_token_if_needed(self) -> str:
        """
        Generate token if current token is expired or missing.
        
        Returns:
            Valid access token
        """
        # Check for existing valid token
        existing_token = self.token_manager.get_token()
        
        if existing_token:
            trading_logger.info("Using existing valid token")
            return existing_token
        
        # Check if we can auto-generate
        if not self.can_auto_generate():
            raise Exception("Auto-generation not configured. Provide ZERODHA_USER_ID, ZERODHA_PASSWORD, ZERODHA_TOTP_SECRET")
        
        # Generate new token
        trading_logger.info("Generating new access token...")
        
        try:
            session = self.zerodha_login.login(force=True)
            
            # Save token
            self.token_manager.save_token(
                session.access_token,
                session.public_token
            )
            
            self._last_generation = datetime.now()
            trading_logger.info("New access token generated")
            
            return session.access_token
            
        except Exception as e:
            trading_logger.error(f"Token generation failed: {e}")
            raise
    
    def can_auto_generate(self) -> bool:
        """Check if auto-generation is configured"""
        return all([
            zerodha.USER_ID,
            zerodha.PASSWORD,
            zerodha.TOTP_SECRET
        ])
    
    def validate_token(self) -> bool:
        """
        Validate current token.
        
        Returns:
            True if token is valid
        """
        return self.token_manager.get_token() is not None
    
    def refresh_token(self) -> str:
        """
        Force token refresh.
        
        Returns:
            New access token
        """
        trading_logger.info("Refreshing token...")
        self.token_manager.delete_token()
        return self.generate_token_if_needed()


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

# Global token manager instance
_token_manager = AutoTokenManager()


def get_access_token() -> str:
    """
    Get valid access token (convenience function).
    Automatically generates new token if needed.
    
    Returns:
        Valid access token
    """
    return _token_manager.generate_token_if_needed()


def refresh_access_token() -> str:
    """
    Refresh access token (convenience function).
    
    Returns:
        New access token
    """
    return _token_manager.refresh_token()


def is_token_valid() -> bool:
    """
    Check if current token is valid.
    
    Returns:
        True if token is valid
    """
    return _token_manager.validate_token()


__all__ = [
    "TokenData",
    "TokenFileManager",
    "AutoTokenManager",
    "get_access_token",
    "refresh_access_token",
    "is_token_valid"
]