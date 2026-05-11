"""
Trading Bot Configuration
==========================
Central configuration management for the swing trading system.
All settings are loaded from environment variables with sensible defaults.
"""

import os
from pathlib import Path
from typing import Optional, List
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ============================================================================
# PROJECT PATHS
# ============================================================================

PROJECT_ROOT = Path(__file__).parent.parent
APP_DIR = PROJECT_ROOT / "app"
LOG_DIR = PROJECT_ROOT / "logs"
REPORT_DIR = PROJECT_ROOT / "reports"
DATA_DIR = PROJECT_ROOT / "data"

# Create directories if they don't exist
LOG_DIR.mkdir(exist_ok=True)
REPORT_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)

# ============================================================================
# ZERODHA BROKER CONFIGURATION
# ============================================================================

class ZerodhaConfig:
    """Zerodha Kite Connect API Configuration"""
    
    # API Credentials - REQUIRED
    API_KEY: str = os.getenv("ZERODHA_API_KEY", "")
    API_SECRET: str = os.getenv("ZERODHA_API_SECRET", "")
    
    # User Credentials - REQUIRED for auto-login
    USER_ID: str = os.getenv("ZERODHA_USER_ID", "")
    PASSWORD: str = os.getenv("ZERODHA_PASSWORD", "")
    TOTP_SECRET: str = os.getenv("ZERODHA_TOTP_SECRET", "")
    
    # Access Token - Generated after login
    # Stored securely in token_manager.py
    ACCESS_TOKEN: Optional[str] = None
    
    # API URLs
    BASE_URL: str = "https://api.kite.trade"
    # Use mock server for testing if needed
    MOCKServer_URL: Optional[str] = os.getenv("ZERODHA_MOCK_URL", None)
    
    # Debug mode
    DEBUG: bool = os.getenv("ZERODHA_DEBUG", "false").lower() == "true"

# ============================================================================
# TRADING CONFIGURATION
# ============================================================================

class TradingConfig:
    """Trading System Configuration"""
    
    # Trading Mode: 'backtest' | 'paper' | 'live'
    MODE: str = os.getenv("TRADING_MODE", "paper")
    
    # Capital Settings
    INITIAL_CAPITAL: float = float(os.getenv("INITIAL_CAPITAL", "100000"))
    MAX_CAPITAL_PER_TRADE: float = float(os.getenv("MAX_CAPITAL_PER_TRADE", "10000"))
    
    # Risk Management
    RISK_PER_TRADE_PERCENT: float = float(os.getenv("RISK_PER_TRADE_PERCENT", "1.0"))
    MAX_SIMULTANEOUS_TRADES: int = int(os.getenv("MAX_SIMULTANEOUS_TRADES", "3"))
    DAILY_MAX_LOSS_PERCENT: float = float(os.getenv("DAILY_MAX_LOSS_PERCENT", "2.0"))
    MAX_CONSECUTIVE_LOSSES: int = int(os.getenv("MAX_CONSECUTIVE_LOSSES", "3"))
    
    # Profit/Loss Targets
    PROFIT_TARGET_PERCENT: float = float(os.getenv("PROFIT_TARGET_PERCENT", "4.0"))
    STOP_LOSS_PERCENT: float = float(os.getenv("STOP_LOSS_PERCENT", "2.0"))
    
    # Trade Settings
    TRADING_COOLDOWN_MINUTES: int = int(os.getenv("TRADING_COOLDOWN_MINUTES", "15"))
    SCAN_INTERVAL_MINUTES: int = int(os.getenv("SCAN_INTERVAL_MINUTES", "15"))
    
    # Market Settings
    # Nifty 50 instruments for market trend analysis
    NIFTY_50_INSTRUMENTS: List[str] = [
        "NIFTYBEES", "BANKNIFTY", "RELIANCE", "INFY", "TCS", 
        "HDFCBANK", "ICICIBANK", "SBIN", "BHARTIARTL"
    ]
    
    # Stock Watchlist for scanning
    DEFAULT_WATCHLIST: List[str] = [
        # Large Cap Nifty 50
        "RELIANCE", "INFY", "TCS", "HDFCBANK", "ICICIBANK",
        "SBIN", "BHARTIARTL", "KOTAKBANK", "AXISBANK", "HINDUNILVR",
        "HDFC", "ADANIPORTS", "ASIANPAINT", "BAJFINANCE", "BPCL",
        "COALINDIA", "DRREDDY", "GRASIM", "HCLTECH", "HEROMOTOCO",
        "HINDZINC", "ITC", "JSWSTEEL", "MARUTI", "NTPC",
        "ONGC", "POWERGRID", "SBILIFE", "SUNPHARMA", "TATASTEEL",
        "TECHM", "TITAN", "ULTRACEMCO", "UPL", "WIPRO",
        # Mid Cap
        "BERGEPAINT", "CADILAHC", "CONCOR", "GLENMARK", "GMRINFRA",
        "IOC", "LICHSUFIN", "MARICO", "MINDTREE", "MOTHERSUM",
        "PETRONET", "PVR", "RAMCOIND", "SUNTV", "TATACONSUM"
    ]
    
    # Order Types
    ORDER_TYPE: str = os.getenv("ORDER_TYPE", "CNC")  # CNC or MIS
    PRODUCT_TYPE: str = os.getenv("PRODUCT_TYPE", "CNC")  # CNC, MIS, NRML

# ============================================================================
# DATABASE CONFIGURATION
# ============================================================================

class DatabaseConfig:
    """Database Configuration"""
    
    # Database Type: 'postgresql' | 'sqlite'
    TYPE: str = os.getenv("DATABASE_TYPE", "sqlite")
    
    # PostgreSQL Settings
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", "5432"))
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "tradingbot")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "tradingbot")
    
    # SQLite Settings
    SQLITE_PATH: Path = DATA_DIR / "tradingbot.db"
    
    # Connection String
    @property
    def connection_string(self) -> str:
        """Get database connection string"""
        if self.TYPE == "postgresql":
            return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        return f"sqlite:///{self.SQLITE_PATH}"

# ============================================================================
# TELEGRAM ALERT CONFIGURATION
# ============================================================================

class TelegramConfig:
    """Telegram Alert Configuration"""
    
    # Bot Token - Get from @BotFather on Telegram
    BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    
    # Chat ID - Get from @userinfobot on Telegram
    CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")
    
    # Alert Settings
    ENABLE_BUY_SIGNALS: bool = os.getenv("ENABLE_BUY_SIGNALS", "true").lower() == "true"
    ENABLE_SELL_SIGNALS: bool = os.getenv("ENABLE_SELL_SIGNALS", "true").lower() == "true"
    ENABLE_ORDER_EXECUTIONS: bool = os.getenv("ENABLE_ORDER_EXECUTIONS", "true").lower() == "true"
    ENABLE_DAILY_SUMMARY: bool = os.getenv("ENABLE_DAILY_SUMMARY", "true").lower() == "true"
    ENABLE_ERRORS: bool = os.getenv("ENABLE_ERRORS", "true").lower() == "true"

# ============================================================================
# BACKTESTING CONFIGURATION
# ============================================================================

class BacktestConfig:
    """Backtesting Configuration"""
    
    # Historical Data
    START_DATE: str = os.getenv("BACKTEST_START_DATE", "2023-01-01")
    END_DATE: str = os.getenv("BACKTEST_END_DATE", "2024-12-31")
    
    # Initial Capital for backtest
    INITIAL_CAPITAL: float = float(os.getenv("BACKTEST_INITIAL_CAPITAL", "100000"))
    
    # Commission per trade
    COMMISSION_PERCENT: float = float(os.getenv("BACKTEST_COMMISSION", "0.1"))
    
    # Slippage (price impact)
    SLIPPAGE_PERCENT: float = float(os.getenv("BACKTEST_SLIPPAGE", "0.05"))

# ============================================================================
# SCHEDULER CONFIGURATION
# ============================================================================

class SchedulerConfig:
    """Scheduler Configuration"""
    
    # Market Hours (IST)
    MARKET_OPEN_HOUR: int = int(os.getenv("MARKET_OPEN_HOUR", "9"))
    MARKET_OPEN_MINUTE: int = int(os.getenv("MARKET_OPEN_MINUTE", "15"))
    MARKET_CLOSE_HOUR: int = int(os.getenv("MARKET_CLOSE_HOUR", "15"))
    MARKET_CLOSE_MINUTE: int = int(os.getenv("MARKET_CLOSE_MINUTE", "30"))
    
    # Timezone
    TIMEZONE: str = os.getenv("TIMEZONE", "Asia/Kolkata")
    
    # Auto Login Schedule (run before market open)
    AUTO_LOGIN_HOUR: int = int(os.getenv("AUTO_LOGIN_HOUR", "8"))
    AUTO_LOGIN_MINUTE: int = int(os.getenv("AUTO_LOGIN_MINUTE", "30"))
    
    # Scanner Schedule
    SCAN_INTERVAL_MINUTES: int = int(os.getenv("SCAN_INTERVAL_MINUTES", "15"))

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

class LoggingConfig:
    """Logging Configuration"""
    
    # Log Level: 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL'
    LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Log Files
    LOG_FILE: Path = LOG_DIR / "trading_bot.log"
    ERROR_LOG_FILE: Path = LOG_DIR / "errors.log"
    TRADE_LOG_FILE: Path = LOG_DIR / "trades.log"
    
    # Log Rotation
    ROTATION: str = "100 MB"  # Rotate after 100 MB
    RETENTION: str = "30 days"  # Keep for 30 days
    COMPRESSION: str = "zip"  # Compress after rotation
    
    # Console Output
    CONSOLE_OUTPUT: bool = os.getenv("CONSOLE_OUTPUT", "true").lower() == "true"

# ============================================================================
# GLOBAL CONFIG OBJECT
# ============================================================================

# Initialize all configurations
zerodha = ZerodhaConfig()
trading = TradingConfig()
database = DatabaseConfig()
telegram = TelegramConfig()
backtest = BacktestConfig()
scheduler = SchedulerConfig()
logging_config = LoggingConfig()

# ============================================================================
# VALIDATION FUNCTIONS
# ============================================================================

def validate_config() -> List[str]:
    """
    Validate required configuration settings.
    
    Returns:
        List of validation error messages (empty if valid)
    """
    errors = []
    
    # Check required Zerodha settings
    if not zerodha.API_KEY:
        errors.append("ZERODHA_API_KEY is required")
    if not zerodha.API_SECRET:
        errors.append("ZERODHA_API_SECRET is required")
    
    # Check required Telegram settings for alerts
    if not telegram.BOT_TOKEN:
        errors.append("TELEGRAM_BOT_TOKEN is required for alerts")
    if not telegram.CHAT_ID:
        errors.append("TELEGRAM_CHAT_ID is required for alerts")
    
    # Validate trading mode
    if trading.MODE not in ['backtest', 'paper', 'live']:
        errors.append(f"Invalid TRADING_MODE: {trading.MODE}. Must be 'backtest', 'paper', or 'live'")
    
    # Validate database config
    if database.TYPE not in ['postgresql', 'sqlite']:
        errors.append(f"Invalid DATABASE_TYPE: {database.TYPE}. Must be 'postgresql' or 'sqlite'")
    
    return errors


def get_required_env_vars() -> List[str]:
    """
    Get list of required environment variables.
    
    Returns:
        List of required environment variable names
    """
    required = [
        "ZERODHA_API_KEY",
        "ZERODHA_API_SECRET",
    ]
    
    # Auto-login requires additional credentials
    if os.getenv("ZERODHA_AUTO_LOGIN", "false").lower() == "true":
        required.extend([
            "ZERODHA_USER_ID",
            "ZERODHA_PASSWORD",
            "ZERODHA_TOTP_SECRET",
        ])
    
    # Telegram alerts require bot token and chat ID
    if os.getenv("ENABLE_TELEGRAM_ALERTS", "true").lower() == "true":
        required.extend([
            "TELEGRAM_BOT_TOKEN",
            "TELEGRAM_CHAT_ID",
        ])
    
    return required


# ============================================================================
# MAIN CONFIGURATION SUMMARY
# ============================================================================

def print_config_summary():
    """Print configuration summary for debugging"""
    print("=" * 60)
    print("SWING TRADING BOT CONFIGURATION")
    print("=" * 60)
    print(f"Mode: {trading.MODE}")
    print(f"Trading Capital: ₹{trading.INITIAL_CAPITAL:,.2f}")
    print(f"Risk per Trade: {trading.RISK_PER_TRADE_PERCENT}%")
    print(f"Profit Target: {trading.PROFIT_TARGET_PERCENT}%")
    print(f"Stop Loss: {trading.STOP_LOSS_PERCENT}%")
    print(f"Database: {database.TYPE}")
    print(f"Zerodha API Key: {'Configured' if zerodha.API_KEY else 'NOT SET'}")
    print(f"Telegram Alerts: {'Configured' if telegram.BOT_TOKEN else 'NOT SET'}")
    print("=" * 60)


if __name__ == "__main__":
    print_config_summary()
    
    # Validate and report errors
    errors = validate_config()
    if errors:
        print("\n⚠️ Configuration Errors:")
        for error in errors:
            print(f"  - {error}")
    else:
        print("\n✅ Configuration is valid!")