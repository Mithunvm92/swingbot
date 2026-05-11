"""
Zerodha Login Module
==================
Automated Zerodha login with TOTP generation using Playwright.
Handles browser automation, session management, and token generation.
"""

import os
import json
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple
from dataclasses import dataclass, field

from playwright.sync_api import sync_playwright, Browser, Page, TimeoutError as PlaywrightTimeout
import pyotp

from app.config import zerodha
from app.utils.logger import trading_logger
from app.utils.helpers import AuthenticationError, ensure_directory, write_json_file, read_json_file


# ============================================================================
# CONFIGURATION
# ============================================================================

# Token storage path
TOKEN_FILE = Path(__file__).parent.parent.parent.parent / "data" / "zerodha_tokens.json"


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class ZerodhaSession:
    """Represents a Zerodha session with tokens"""
    user_id: str
    api_key: str
    access_token: str
    public_token: str = ""
    login_time: datetime = field(default_factory=datetime.now)
    expires_at: datetime = field(default_factory=lambda: datetime.now() + timedelta(days=1))
    is_valid: bool = True
    
    def is_expired(self) -> bool:
        """Check if session is expired"""
        return datetime.now() >= self.expires_at
    
    def needs_refresh(self) -> bool:
        """Check if session needs refresh"""
        # Refresh if expiring within 2 hours
        return datetime.now() >= self.expires_at - timedelta(hours=2)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "user_id": self.user_id,
            "api_key": self.api_key,
            "access_token": self.access_token,
            "public_token": self.public_token,
            "login_time": self.login_time.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "is_valid": self.is_valid
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "ZerodhaSession":
        """Create from dictionary"""
        return cls(
            user_id=data["user_id"],
            api_key=data["api_key"],
            access_token=data["access_token"],
            public_token=data.get("public_token", ""),
            login_time=datetime.fromisoformat(data["login_time"]),
            expires_at=datetime.fromisoformat(data["expires_at"]),
            is_valid=data.get("is_valid", True)
        )


# ============================================================================
# TOKEN MANAGER
# ============================================================================

class TokenManager:
    """
    Manages Zerodha access tokens securely.
    Handles storage, retrieval, and validation of tokens.
    """
    
    def __init__(self, token_file: Optional[Path] = None):
        """
        Initialize token manager.
        
        Args:
            token_file: Path to token storage file
        """
        self.token_file = token_file or TOKEN_FILE
        ensure_directory(self.token_file.parent)
        self._session: Optional[ZerodhaSession] = None
    
    def save_session(self, session: ZerodhaSession) -> None:
        """
        Save session to file.
        
        Args:
            session: ZerodhaSession to save
        """
        data = session.to_dict()
        write_json_file(self.token_file, data)
        self._session = session
        trading_logger.info(f"Session saved for user {session.user_id}")
    
    def load_session(self) -> Optional[ZerodhaSession]:
        """
        Load session from file.
        
        Returns:
            ZerodhaSession if valid, None otherwise
        """
        if not self.token_file.exists():
            return None
        
        try:
            data = read_json_file(self.token_file)
            session = ZerodhaSession.from_dict(data)
            
            # Check if valid
            if session.is_valid and not session.is_expired():
                self._session = session
                trading_logger.info(f"Session loaded for user {session.user_id}")
                return session
            
            trading_logger.warning("Session expired or invalid")
            return None
        except Exception as e:
            trading_logger.error(f"Error loading session: {e}")
            return None
    
    def get_session(self) -> Optional[ZerodhaSession]:
        """Get current session"""
        if self._session is None:
            return self.load_session()
        return self._session
    
    def clear_session(self) -> None:
        """Clear saved session"""
        if self.token_file.exists():
            self.token_file.unlink()
        self._session = None
        trading_logger.info("Session cleared")
    
    def is_session_valid(self) -> bool:
        """Check if current session is valid"""
        session = self.get_session()
        return session is not None and session.is_valid and not session.is_expired()


# ============================================================================
# ZERODHA LOGIN AUTOMATOR
# ============================================================================

class ZerodhaLogin:
    """
    Automated Zerodha login using Playwright.
    Handles browser automation, TOTP generation, and token generation.
    """
    
    def __init__(self):
        """Initialize Zerodha login automation"""
        self.api_key = zerodha.API_KEY
        self.api_secret = zerodha.API_SECRET
        self.user_id = zerodha.USER_ID
        self.password = zerodha.PASSWORD
        self.totp_secret = zerodha.TOTP_SECRET
        self.base_url = zerodha.BASE_URL
        self.debug = zerodha.DEBUG
        
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.token_manager = TokenManager()
        
        # Login URLs
        self.login_url = "https://kite.zerodha.com/"
        self.connect_login_url = f"https://kite.zerodha.com/connect/login?api_key={self.api_key}"
    
    def _generate_totp(self) -> str:
        """
        Generate TOTP using pyotp.
        
        Returns:
            6-digit TOTP code
        """
        if not self.totp_secret:
            raise AuthenticationError("TOTP secret not configured")
        
        totp = pyotp.TOTP(self.totp_secret)
        code = totp.now()
        
        if self.debug:
            trading_logger.debug(f"Generated TOTP: {code}")
        
        return code
    
    def _init_browser(self) -> None:
        """Initialize Playwright browser"""
        trading_logger.info("Initializing browser...")
        
        playwright = sync_playwright().start()
        self.browser = playwright.chromium.launch(
            headless=False,  # Headless mode for automation
            args=['--disable-blink-features=AutomationControlled']
        )
        self.context = self.browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0"
        )
        self.page = self.context.new_page()
        
        trading_logger.info("Browser initialized")
    
    def _close_browser(self) -> None:
        """Close browser"""
        if self.browser:
            try:
                self.browser.close()
            except Exception as e:
                trading_logger.error(f"Error closing browser: {e}")
            self.browser = None
            self.page = None
    
    def _request_access_token(self) -> str:
        """
        Request access token using browser automation.
        
        Returns:
            Request token from login
        """
        try:
            # Navigate to login page
            self.page.goto(self.connect_login_url, wait_until="networkidle")
            
            # Wait for page to load
            time.sleep(2)
            
            # Enter user ID
            trading_logger.info(f"Entering user ID: {self.user_id}")
            self.page.wait_for_load_state(); self.page.wait_for_selector("input[name="user_id"]"); self.page.fill('input[name="user_id"]', self.user_id)
            self.page.click('button[type="submit"]')
            
            time.sleep(1)
            
            # Enter password
            trading_logger.info("Entering password")
            self.page.wait_for_load_state(); self.page.wait_for_selector("input[name="user_id"]"); self.page.fill('input[name="password"]', self.password)
            self.page.click('button[type="submit"]')
            
            time.sleep(2)
            
            # Enter TOTP
            totp_code = self._generate_totp()
            trading_logger.info("Entering TOTP")
            self.page.wait_for_load_state(); self.page.wait_for_selector("input[name="user_id"]"); self.page.fill('input[name="totp"]', totp_code)
            self.page.click('button[type="submit"]')
            
            time.sleep(3)
            
            # Get request token from URL
            current_url = self.page.url
            trading_logger.debug(f"Current URL: {current_url}")
            
            if "request_token" in current_url:
                # Extract request token from URL
                from urllib.parse import urlparse, parse_qs
                parsed = urlparse(current_url)
                params = parse_qs(parsed.query)
                request_token = params["request_token"][0]
                trading_logger.info("Request token obtained")
                return request_token
            elif "access_token" in current_url:
                # Direct access token (rare case)
                from urllib.parse import urlparse, parse_qs
                parsed = urlparse(current_url)
                params = parse_qs(parsed.query)
                return params["access_token"][0]
            else:
                # Check if already logged in
                try:
                    self.page.wait_for_url("**/dashboard", timeout=5000)
                    trading_logger.warning("Already logged in, need to get request token")
                    # Navigate to connect API to get new token
                    self.page.goto(self.connect_login_url)
                    time.sleep(2)
                    current_url = self.page.url
                    if "request_token" in current_url:
                        from urllib.parse import urlparse, parse_qs
                        parsed = urlparse(current_url)
                        params = parse_qs(parsed.query)
                        return params["request_token"][0]
                except PlaywrightTimeout:
                    pass
                
                raise AuthenticationError("Failed to get request token")
                
        except Exception as e:
            trading_logger.error(f"Error during login: {e}")
            raise AuthenticationError(f"Login failed: {str(e)}")
    
    def _generate_access_token(self, request_token: str) -> Tuple[str, str]:
        """
        Generate access token using request token.
        
        Args:
            request_token: Request token obtained from login
        
        Returns:
            Tuple of (access_token, public_token)
        """
        try:
            import requests
            
            # API endpoint for token generation
            url = f"{self.base_url}/api/token/generate"
            
            params = {
                "api_key": self.api_key,
                "request_token": request_token,
                "secret": self.api_secret
            }
            
            response = requests.post(url, data=params, timeout=30)
            data = response.json()
            
            if response.status_code == 200 and data.get("status") == "success":
                access_token = data["data"]["access_token"]
                public_token = data["data"].get("public_token", "")
                trading_logger.info("Access token generated successfully")
                return access_token, public_token
            else:
                error_msg = data.get("message", "Unknown error")
                raise AuthenticationError(f"Failed to generate access token: {error_msg}")
                
        except Exception as e:
            trading_logger.error(f"Error generating access token: {e}")
            raise AuthenticationError(f"Access token generation failed: {str(e)}")
    
    def login(self, force: bool = False) -> ZerodhaSession:
        """
        Perform complete login flow.
        
        Args:
            force: Force new login even if valid session exists
        
        Returns:
            ZerodhaSession object
        """
        # Check for existing valid session
        if not force:
            existing_session = self.token_manager.get_session()
            if existing_session and existing_session.is_valid and not existing_session.is_expired():
                trading_logger.info("Using existing valid session")
                return existing_session
        
        # Check if auto-login is configured
        if not all([self.api_key, self.user_id, self.password, self.totp_secret]):
            raise AuthenticationError("Auto-login not fully configured. Provide USER_ID, PASSWORD, and TOTP_SECRET")
        
        try:
            # Initialize browser
            self._init_browser()
            
            # Get request token
            request_token = self._request_access_token()
            
            # Generate access token
            access_token, public_token = self._generate_access_token(request_token)
            
            # Create session
            session = ZerodhaSession(
                user_id=self.user_id,
                api_key=self.api_key,
                access_token=access_token,
                public_token=public_token,
                login_time=datetime.now(),
                expires_at=datetime.now() + timedelta(days=1)
            )
            
            # Save session
            self.token_manager.save_session(session)
            
            trading_logger.info("Login successful")
            return session
            
        finally:
            # Close browser
            self._close_browser()
    
    def refresh_session(self) -> ZerodhaSession:
        """
        Refresh existing session.
        
        Returns:
            New ZerodhaSession
        """
        trading_logger.info("Refreshing session...")
        return self.login(force=True)
    
    def validate_session(self) -> bool:
        """
        Validate current session.
        
        Returns:
            True if session is valid
        """
        return self.token_manager.is_session_valid()
    
    def get_access_token(self) -> str:
        """
        Get current access token.
        
        Returns:
            Access token string
        
        Raises:
            AuthenticationError: If no valid session
        """
        session = self.token_manager.get_session()
        
        if session is None or session.is_expired():
            if all([self.api_key, self.user_id, self.password, self.totp_secret]):
                session = self.login()
            else:
                raise AuthenticationError("No valid session and auto-login not configured")
        
        return session.access_token


# ============================================================================
# SESSION VALIDATOR
# ============================================================================

class SessionValidator:
    """
    Validates Zerodha session periodically.
    Ensures session is active and refreshes if needed.
    """
    
    def __init__(self, login: Optional[ZerodhaLogin] = None):
        """
        Initialize session validator.
        
        Args:
            login: ZerodhaLogin instance
        """
        self.login = login or ZerodhaLogin()
        self.last_validation = None
        self.validation_interval = 3600  # 1 hour
    
    def validate(self, force_refresh: bool = False) -> bool:
        """
        Validate session.
        
        Args:
            force_refresh: Force session refresh
        
        Returns:
            True if session is valid
        """
        now = datetime.now()
        
        # Check if recently validated
        if (self.last_validation and 
            (now - self.last_validation).total_seconds() < self.validation_interval and 
            not force_refresh):
            return self.login.validate_session()
        
        # Validate session
        if force_refresh or not self.login.validate_session():
            try:
                self.login.refresh_session()
            except AuthenticationError as e:
                trading_logger.error(f"Session validation failed: {e}")
                return False
        
        self.last_validation = now
        return True


# ============================================================================
# MAIN FUNCTION
# ============================================================================

def get_zerodha_session(force_login: bool = False) -> ZerodhaSession:
    """
    Get Zerodha session (convenience function).
    
    Args:
        force_login: Force new login
    
    Returns:
        ZerodhaSession
    """
    login = ZerodhaLogin()
    return login.login(force=force_login)


def get_access_token() -> str:
    """
    Get Zerodha access token (convenience function).
    
    Returns:
        Access token string
    """
    login = ZerodhaLogin()
    return login.get_access_token()


__all__ = [
    "ZerodhaSession",
    "TokenManager",
    "ZerodhaLogin",
    "SessionValidator",
    "get_zerodha_session",
    "get_access_token",
    "TOKEN_FILE"
]