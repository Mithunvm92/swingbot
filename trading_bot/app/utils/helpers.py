"""
Helper Utilities
================
Common utility functions for the trading system.
"""

import os
import json
from datetime import datetime, time
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import hashlib

from app.config import scheduler


# ============================================================================
# FILE UTILITIES
# ============================================================================

def ensure_directory(path: Path) -> Path:
    """
    Ensure a directory exists, creating it if necessary.
    
    Args:
        path: Directory path
    
    Returns:
        Path object
    """
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_json_file(file_path: Path) -> Dict:
    """
    Read a JSON file.
    
    Args:
        file_path: Path to JSON file
    
    Returns:
        Dictionary contents
    """
    with open(file_path, 'r') as f:
        return json.load(f)


def write_json_file(file_path: Path, data: Dict) -> None:
    """
    Write data to a JSON file.
    
    Args:
        file_path: Path to JSON file
        data: Data to write
    """
    ensure_directory(file_path.parent)
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=4)


def read_text_file(file_path: Path) -> str:
    """
    Read a text file.
    
    Args:
        file_path: Path to text file
    
    Returns:
        File contents as string
    """
    with open(file_path, 'r') as f:
        return f.read()


def write_text_file(file_path: Path, content: str) -> None:
    """
    Write content to a text file.
    
    Args:
        file_path: Path to text file
        content: Content to write
    """
    ensure_directory(file_path.parent)
    with open(file_path, 'w') as f:
        f.write(content)


# ============================================================================
# DATE/TIME UTILITIES
# ============================================================================

def get_current_time() -> datetime:
    """Get current datetime in IST"""
    return datetime.now()


def get_current_date() -> str:
    """Get current date as string (YYYY-MM-DD)"""
    return datetime.now().strftime("%Y-%m-%d")


def get_current_timeIST() -> str:
    """Get current time as string (HH:MM:SS)"""
    return datetime.now().strftime("%H:%M:%S")


def format_datetime(dt: datetime, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    Format datetime to string.
    
    Args:
        dt: Datetime object
        fmt: Format string
    
    Returns:
        Formatted datetime string
    """
    return dt.strftime(fmt)


def parse_datetime(date_str: str, fmt: str = "%Y-%m-%d %H:%M:%S") -> datetime:
    """
    Parse datetime from string.
    
    Args:
        date_str: Date string
        fmt: Format string
    
    Returns:
        Datetime object
    """
    return datetime.strptime(date_str, fmt)


def is_market_open() -> bool:
    """
    Check if market is currently open.
    
    Returns:
        True if market is open
    """
    now = datetime.now()
    
    # Check if weekend
    if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
        return False
    
    # Market hours in IST (9:15 AM - 3:30 PM)
    market_start = time(scheduler.MARKET_OPEN_HOUR, scheduler.MARKET_OPEN_MINUTE)
    market_end = time(scheduler.MARKET_CLOSE_HOUR, scheduler.MARKET_CLOSE_MINUTE)
    
    current_time = now.time()
    
    return market_start <= current_time <= market_end


def is_trading_day() -> bool:
    """
    Check if today is a trading day (not weekend).
    
    Returns:
        True if trading day
    """
    return datetime.now().weekday() < 5


def get_market_open_time() -> time:
    """Get market open time"""
    return time(scheduler.MARKET_OPEN_HOUR, scheduler.MARKET_OPEN_MINUTE)


def get_market_close_time() -> time:
    """Get market close time"""
    return time(scheduler.MARKET_CLOSE_HOUR, scheduler.MARKET_CLOSE_MINUTE)


def time_until_market_open() -> float:
    """
    Calculate time until market opens (in seconds).
    
    Returns:
        Seconds until market open, or 0 if already open
    """
    now = datetime.now()
    current_time = now.time()
    open_time = get_market_open_time()
    
    if current_time < open_time:
        # Today - calculate seconds until open
        open_dt = datetime.combine(now.date(), open_time)
        return (open_dt - now).total_seconds()
    else:
        # Next trading day
        next_day = now.replace(hour=0, minute=0, second=0)
        days_ahead = 1 if now.weekday() < 4 else (7 - now.weekday())
        next_open = next_day.replace(hour=scheduler.MARKET_OPEN_HOUR, 
                                   minute=scheduler.MARKET_OPEN_MINUTE)
        next_open = next_open.replace(day=now.day + days_ahead)
        return (next_open - now).total_seconds()


# ============================================================================
# CALCULATION UTILITIES
# ============================================================================

def calculate_pnl(
    buy_price: float,
    sell_price: float,
    quantity: int
) -> Tuple[float, float]:
    """
    Calculate profit/loss from a trade.
    
    Args:
        buy_price: Buy price
        sell_price: Sell price
        quantity: Number of shares
    
    Returns:
        Tuple of (pnl_amount, pnl_percent)
    """
    pnl_amount = (sell_price - buy_price) * quantity
    pnl_percent = ((sell_price - buy_price) / buy_price) * 100
    return pnl_amount, pnl_percent


def calculate_position_size(
    capital: float,
    risk_percent: float,
    entry_price: float,
    stop_loss: float
) -> Tuple[int, float]:
    """
    Calculate position size based on risk management rules.
    
    Args:
        capital: Available capital
        risk_percent: Risk per trade percentage (e.g., 1 for 1%)
        entry_price: Entry price
        stop_loss: Stop loss price
    
    Returns:
        Tuple of (quantity, total_capital_needed)
    """
    # Calculate risk amount in rupees
    risk_amount = capital * (risk_percent / 100)
    
    # Risk per share = entry - stop_loss
    risk_per_share = abs(entry_price - stop_loss)
    
    if risk_per_share <= 0:
        return 0, 0
    
    # Calculate quantity
    quantity = int(risk_amount / risk_per_share)
    
    # Ensure quantity is at least 1
    quantity = max(1, quantity)
    
    # Calculate total capital needed
    total_capital_needed = quantity * entry_price
    
    # Adjust if exceeds available capital
    if total_capital_needed > capital:
        quantity = int(capital / entry_price)
        quantity = max(1, quantity)
        total_capital_needed = quantity * entry_price
    
    return quantity, total_capital_needed


def calculate_stop_loss(price: float, percent: float) -> float:
    """
    Calculate stop loss price.
    
    Args:
        price: Current price
        percent: Stop loss percentage (e.g., 2 for 2%)
    
    Returns:
        Stop loss price
    """
    return price * (1 - percent / 100)


def calculate_target(price: float, percent: float) -> float:
    """
    Calculate target price.
    
    Args:
        price: Current price
        percent: Target percentage (e.g., 4 for 4%)
    
    Returns:
        Target price
    """
    return price * (1 + percent / 100)


def calculate_commission(amount: float, percent: float = 0.1) -> float:
    """
    Calculate brokerage commission.
    
    Args:
        amount: Trade amount
        percent: Commission percentage (default: 0.1%)
    
    Returns:
        Commission amount
    """
    return amount * (percent / 100)


# ============================================================================
# DATA UTILITIES
# ============================================================================

def sanitize_symbol(symbol: str) -> str:
    """
    Sanitize stock symbol for display.
    
    Args:
        symbol: Raw stock symbol
    
    Returns:
        Sanitized symbol
    """
    return symbol.strip().upper().replace(' ', '')


def format_price(price: float) -> str:
    """
    Format price for display.
    
    Args:
        price: Price value
    
    Returns:
        Formatted price string
    """
    return f"₹{price:,.2f}"


def format_percent(percent: float) -> str:
    """
    Format percentage for display.
    
    Args:
        percent: Percentage value
    
    Returns:
        Formatted percentage string
    """
    sign = "+" if percent >= 0 else ""
    return f"{sign}{percent:.2f}%"


def format_quantity(quantity: int) -> str:
    """
    Format quantity with commas.
    
    Args:
        quantity: Quantity value
    
    Returns:
        Formatted quantity string
    """
    return f"{quantity:,}"


def truncate_string(s: str, max_length: int = 50) -> str:
    """
    Truncate string to maximum length.
    
    Args:
        s: String to truncate
        max_length: Maximum length
    
    Returns:
        Truncated string
    """
    if len(s) <= max_length:
        return s
    return s[:max_length-3] + "..."


# ============================================================================
# SECURITY UTILITIES
# ============================================================================

def hash_string(s: str, salt: str = "") -> str:
    """
    Hash a string with salt.
    
    Args:
        s: String to hash
        salt: Salt value
    
    Returns:
        Hashed string
    """
    return hashlib.sha256(f"{s}{salt}".encode()).hexdigest()


def generate_token(length: int = 32) -> str:
    """
    Generate a random token.
    
    Args:
        length: Token length
    
    Returns:
        Random token
    """
    random_bytes = os.urandom(length)
    return random_bytes.hex()


# ============================================================================
# EXCEPTION CLASSES
# ============================================================================

class TradingError(Exception):
    """Base exception for trading errors"""
    pass


class AuthenticationError(TradingError):
    """Exception for authentication errors"""
    pass


class OrderError(TradingError):
    """Exception for order execution errors"""
    pass


class DataError(TradingError):
    """Exception for data errors"""
    pass


class ConfigurationError(TradingError):
    """Exception for configuration errors"""
    pass


class RiskLimitError(TradingError):
    """Exception for risk limit breaches"""
    pass


# ============================================================================
# VALIDATION UTILITIES
# ============================================================================

def validate_price(price: float) -> bool:
    """Validate price is positive"""
    return price > 0


def validate_quantity(quantity: int) -> bool:
    """Validate quantity is positive"""
    return quantity > 0


def validate_percent(percent: float) -> bool:
    """Validate percentage is in valid range"""
    return 0 < percent < 100


def validate_capital(capital: float) -> bool:
    """Validate capital is positive"""
    return capital > 0


__all__ = [
    "ensure_directory",
    "read_json_file",
    "write_json_file",
    "read_text_file",
    "write_text_file",
    "get_current_time",
    "get_current_date",
    "get_current_timeIST",
    "format_datetime",
    "parse_datetime",
    "is_market_open",
    "is_trading_day",
    "get_market_open_time",
    "get_market_close_time",
    "time_until_market_open",
    "calculate_pnl",
    "calculate_position_size",
    "calculate_stop_loss",
    "calculate_target",
    "calculate_commission",
    "sanitize_symbol",
    "format_price",
    "format_percent",
    "format_quantity",
    "truncate_string",
    "hash_string",
    "generate_token",
    "TradingError",
    "AuthenticationError",
    "OrderError",
    "DataError",
    "ConfigurationError",
    "RiskLimitError",
    "validate_price",
    "validate_quantity",
    "validate_percent",
    "validate_capital"
]