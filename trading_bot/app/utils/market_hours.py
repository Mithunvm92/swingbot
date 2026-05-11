"""
Market Hours Module
=================
Market hours utilities for Indian stock markets.
"""

from datetime import time, datetime
from typing import Tuple
from pytz import timezone

from app.config import scheduler


# ============================================================================
# INDIAN MARKET HOURS
# ============================================================================

# NSE/BSE Market Hours (IST)
MARKET_OPEN = time(9, 15)   # 9:15 AM
MARKET_CLOSE = time(15, 30)  # 3:30 PM
PRE_MARKET_OPEN = time(9, 0)
POST_MARKET_CLOSE = time(15, 45)

# Market segments
EQUITY_MARKET_OPEN = time(9, 15)
EQUITY_MARKET_CLOSE = time(15, 30)
FNO_MARKET_OPEN = time(9, 15)
FNO_MARKET_CLOSE = time(15, 30)
CURRENCY_MARKET_OPEN = time(9, 00)
CURRENCY_MARKET_CLOSE = time(17, 00)
COMMODITY_MARKET_OPEN = time(9, 00)
COMMODITY_MARKET_CLOSE = time(23, 30)


# ============================================================================
# TIMEZONE
# ============================================================================

IST = timezone("Asia/Kolkata")


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_current_time_ist() -> datetime:
    """Get current time in IST"""
    return datetime.now(IST)


def is_trading_day(dt: datetime = None) -> bool:
    """
    Check if a given date is a trading day.
    
    Args:
        dt: Datetime to check (default: now)
    
    Returns:
        True if trading day (weekday and not a market holiday)
    """
    if dt is None:
        dt = get_current_time_ist()
    
    # Check weekday (Monday = 0, Sunday = 6)
    if dt.weekday() >= 5:
        return False
    
    return True


def is_market_open(dt: datetime = None) -> bool:
    """
    Check if market is currently open.
    
    Args:
        dt: Datetime to check (default: now)
    
    Returns:
        True if market is open
    """
    if dt is None:
        dt = get_current_time_ist()
    
    # Check if trading day
    if not is_trading_day(dt):
        return False
    
    current_time = dt.time()
    
    # Check market hours
    return MARKET_OPEN <= current_time <= MARKET_CLOSE


def is_pre_market(dt: datetime = None) -> bool:
    """
    Check if in pre-market session.
    
    Args:
        dt: Datetime to check (default: now)
    
    Returns:
        True if in pre-market
    """
    if dt is None:
        dt = get_current_time_ist()
    
    if not is_trading_day(dt):
        return False
    
    current_time = dt.time()
    
    return PRE_MARKET_OPEN <= current_time < MARKET_OPEN


def is_post_market(dt: datetime = None) -> bool:
    """
    Check if in post-market session.
    
    Args:
        dt: Datetime to check (default: now)
    
    Returns:
        True if in post-market
    """
    if dt is None:
        dt = get_current_time_ist()
    
    if not is_trading_day(dt):
        return False
    
    current_time = dt.time()
    
    return MARKET_CLOSE < current_time <= POST_MARKET_CLOSE


def time_to_market_open(dt: datetime = None) -> float:
    """
    Get seconds until market opens.
    
    Args:
        dt: Reference datetime (default: now)
    
    Returns:
        Seconds until market open (0 if already open)
    """
    if dt is None:
        dt = get_current_time_ist()
    
    if is_market_open(dt):
        return 0
    
    # Calculate next market open
    current_date = dt.date()
    open_datetime = datetime.combine(current_date, MARKET_OPEN)
    open_datetime = IST.localize(open_datetime)
    
    if dt.time() > MARKET_OPEN:
        # Tomorrow
        from datetime import timedelta
        open_datetime += timedelta(days=1)
        
        # Skip weekends
        while open_datetime.weekday() >= 5:
            open_datetime += timedelta(days=1)
    
    return (open_datetime - dt).total_seconds()


def time_to_market_close(dt: datetime = None) -> float:
    """
    Get seconds until market closes.
    
    Args:
        dt: Reference datetime (default: now)
    
    Returns:
        Seconds until market close (0 if already closed)
    """
    if dt is None:
        dt = get_current_time_ist()
    
    if not is_market_open(dt):
        return 0
    
    current_date = dt.date()
    close_datetime = datetime.combine(current_date, MARKET_CLOSE)
    close_datetime = IST.localize(close_datetime)
    
    if dt.time() > MARKET_CLOSE:
        return 0
    
    return (close_datetime - dt).total_seconds()


def get_market_session(dt: datetime = None) -> str:
    """
    Get current market session.
    
    Args:
        dt: Datetime to check (default: now)
    
    Returns:
        Session name: 'CLOSED', 'PRE_OPEN', 'OPEN', 'POST_CLOSE'
    """
    if dt is None:
        dt = get_current_time_ist()
    
    if not is_trading_day(dt):
        return "CLOSED"
    
    current_time = dt.time()
    
    if current_time < PRE_MARKET_OPEN:
        return "CLOSED"
    elif current_time < MARKET_OPEN:
        return "PRE_OPEN"
    elif current_time <= MARKET_CLOSE:
        return "OPEN"
    elif current_time <= POST_MARKET_CLOSE:
        return "POST_CLOSE"
    else:
        return "CLOSED"


def get_next_trading_day(dt: datetime = None) -> datetime:
    """
    Get the next trading day.
    
    Args:
        dt: Reference datetime (default: now)
    
    Returns:
        Next trading day
    """
    if dt is None:
        dt = get_current_time_ist()
    
    from datetime import timedelta
    
    next_day = dt + timedelta(days=1)
    
    while not is_trading_day(next_day):
        next_day += timedelta(days=1)
    
    return next_day


def get_market_status(dt: datetime = None) -> dict:
    """
    Get market status information.
    
    Args:
        dt: Datetime to check (default: now)
    
    Returns:
        Dictionary with market status info
    """
    if dt is None:
        dt = get_current_time_ist()
    
    return {
        "is_trading_day": is_trading_day(dt),
        "is_open": is_market_open(dt),
        "session": get_market_session(dt),
        "time_to_open": time_to_market_open(dt),
        "time_to_close": time_to_market_close(dt),
        "current_time": dt.isoformat()
    }


__all__ = [
    "MARKET_OPEN",
    "MARKET_CLOSE",
    "IST",
    "get_current_time_ist",
    "is_trading_day",
    "is_market_open",
    "is_pre_market",
    "is_post_market",
    "time_to_market_open",
    "time_to_market_close",
    "get_market_session",
    "get_next_trading_day",
    "get_market_status"
]