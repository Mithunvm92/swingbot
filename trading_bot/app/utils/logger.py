"""
Logging Utility Module
=====================
Provides structured logging for the trading system using Loguru.
Includes file rotation, error tracking, and trade logging.
"""

import sys
from pathlib import Path
from typing import Optional
from loguru import logger

from app.config import logging_config, trading


def setup_logging(
    log_file: Optional[Path] = None,
    error_log_file: Optional[Path] = None,
    trade_log_file: Optional[Path] = None,
    level: str = "INFO",
    console_output: bool = True
) -> None:
    """
    Setup logging for the trading bot.
    
    Args:
        log_file: Main log file path
        error_log_file: Error log file path
        trade_log_file: Trade-specific log file path
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        console_output: Whether to output to console
    """
    # Remove default handler
    logger.remove()
    
    # Add console handler if enabled
    if console_output:
        logger.add(
            sys.stdout,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
            level=level,
            colorize=True
        )
    
    # Use configured paths
    if log_file is None:
        log_file = logging_config.LOG_FILE
    if error_log_file is None:
        error_log_file = logging_config.ERROR_LOG_FILE
    if trade_log_file is None:
        trade_log_file = logging_config.TRADE_LOG_FILE
    
    # Add file handlers with rotation
    # Main log file
    logger.add(
        log_file,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level=level,
        rotation=logging_config.ROTATION,
        retention=logging_config.RETENTION,
        compression=logging_config.COMPRESSION,
        enqueue=True  # Thread-safe logging
    )
    
    # Error log file - only ERROR and CRITICAL
    logger.add(
        error_log_file,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="ERROR",
        rotation=logging_config.ROTATION,
        retention=logging_config.RETENTION,
        compression=logging_config.COMPRESSION,
        enqueue=True
    )
    
    # Trade log file - all trade-related logs
    logger.add(
        trade_log_file,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
        level=level,
        rotation=logging_config.ROTATION,
        retention=logging_config.RETENTION,
        compression=logging_config.COMPRESSION,
        enqueue=True
    )


def get_logger(name: str = "trading_bot"):
    """
    Get a configured logger instance.
    
    Args:
        name: Logger name (typically __name__)
    
    Returns:
        Configured logger instance
    """
    return logger.bind(name=name)


# Initialize logging
setup_logging(
    level=logging_config.LEVEL,
    console_output=logging_config.CONSOLE_OUTPUT
)

# ============================================================================
# SPECIALIZED LOGGING FUNCTIONS
# ============================================================================

def log_trade(action: str, stock: str, quantity: int, price: float, 
              order_type: str = "BUY", notes: str = "") -> None:
    """
    Log a trade execution.
    
    Args:
        action: Trade action (BUY, SELL, SL_HIT, TARGET_HIT)
        stock: Stock symbol
        quantity: Number of shares
        price: Execution price
        order_type: Order type (MARKET, LIMIT, SL, SL-M)
        notes: Additional notes
    """
    log = get_logger("trades")
    
    if order_type == "BUY":
        log.info(f"📈 BUY  | {stock:10} | Qty: {quantity:5} | Price: ₹{price:8.2f} | Value: ₹{quantity*price:10,.2f} | {notes}")
    elif order_type == "SELL":
        log.info(f"📉 SELL | {stock:10} | Qty: {quantity:5} | Price: ₹{price:8.2f} | Value: ₹{quantity*price:10,.2f} | {notes}")
    elif action == "SL_HIT":
        log.warning(f"🛑 SL HIT | {stock:10} | Qty: {quantity:5} | Price: ₹{price:8.2f} | {notes}")
    elif action == "TARGET_HIT":
        log.info(f"🎯 TARGET | {stock:10} | Qty: {quantity:5} | Price: ₹{price:8.2f} | {notes}")
    else:
        log.info(f"❓ {action} | {stock:10} | Qty: {quantity:5} | Price: ₹{price:8.2f} | {notes}")


def log_signal(signal_type: str, stock: str, entry: float, 
               stop_loss: float, target: float, reason: str = "") -> None:
    """
    Log a trading signal.
    
    Args:
        signal_type: Signal type (BUY, SELL, STRONG_BUY, SELL)
        stock: Stock symbol
        entry: Entry price
        stop_loss: Stop loss price
        target: Target price
        reason: Signal reason
    """
    log = get_logger("signals")
    
    if signal_type in ["BUY", "STRONG_BUY"]:
        log.info(f"🔔 {signal_type:12} | {stock:10} | Entry: ₹{entry:8.2f} | SL: ₹{stop_loss:7.2f} | Target: ₹{target:8.2f} | {reason}")
    else:
        log.info(f"🔔 {signal_type:12} | {stock:10} | {reason}")


def log_position(stock: str, quantity: int, avg_price: float, 
                 current_price: float, pnl: float) -> None:
    """
    Log position status.
    
    Args:
        stock: Stock symbol
        quantity: Number of shares
        avg_price: Average buy price
        current_price: Current market price
        pnl: Profit/Loss in rupees
    """
    log = get_logger("positions")
    
    pnl_percent = ((current_price - avg_price) / avg_price) * 100
    
    if pnl >= 0:
        log.info(f"📊 POS  | {stock:10} | Qty: {quantity:5} | Avg: ₹{avg_price:7.2f} | Curr: ₹{current_price:7.2f} | P&L: ₹{pnl:8,.2f} ({pnl_percent:+.2f}%)")
    else:
        log.warning(f"📊 POS  | {stock:10} | Qty: {quantity:5} | Avg: ₹{avg_price:7.2f} | Curr: ₹{current_price:7.2f} | P&L: ₹{pnl:8,.2f} ({pnl_percent:+.2f}%)")


def log_daily_summary(
    date: str,
    trades_count: int,
    pnl: float,
    capital: float,
    open_positions: int
) -> None:
    """
    Log daily summary.
    
    Args:
        date: Trading date
        trades_count: Number of trades executed
        pnl: Total P&L for the day
        capital: Current capital
        open_positions: Number of open positions
    """
    log = get_logger("daily")
    
    pnl_percent = (pnl / (capital - pnl)) * 100
    daily_return = (pnl / capital) * 100
    
    log.info("=" * 60)
    log.info(f"📅 DAILY SUMMARY - {date}")
    log.info("=" * 60)
    log.info(f"Trades Executed: {trades_count}")
    log.info(f"Open Positions: {open_positions}")
    log.info(f"Day P&L: ₹{pnl:,.2f} ({pnl_percent:+.2f}%)")
    log.info(f"Daily Return: {daily_return:+.2f}%")
    log.info(f"Current Capital: ₹{capital:,.2f}")
    log.info("=" * 60)


def log_error(error: Exception, context: str = "") -> None:
    """
    Log an error with context.
    
    Args:
        error: Exception object
        context: Context string describing where the error occurred
    """
    log = get_logger("errors")
    
    if context:
        log.error(f"❌ Error in {context}: {type(error).__name__}: {str(error)}")
    else:
        log.error(f"❌ Error: {type(error).__name__}: {str(error)}")


def log_market_status(status: str, details: str = "") -> None:
    """
    Log market status changes.
    
    Args:
        status: Market status (OPEN, CLOSED, PRE_OPEN, POST_CLOSE)
        details: Additional details
    """
    log = get_logger("market")
    
    if status == "OPEN":
        log.info(f"🟢 Market OPEN - {details}")
    elif status == "CLOSED":
        log.info(f"🔴 Market CLOSED - {details}")
    elif status == "PRE_OPEN":
        log.info(f"🟡 Pre-Open - {details}")
    elif status == "POST_CLOSE":
        log.info(f"🟠 Post-Close - {details}")
    else:
        log.info(f"⚪ {status} - {details}")


# ============================================================================
# TRADING BOT LOGGER
# ============================================================================

# Main application logger
trading_logger = get_logger("trading_bot")

__all__ = [
    "logger",
    "get_logger",
    "setup_logging",
    "log_trade",
    "log_signal",
    "log_position",
    "log_daily_summary",
    "log_error",
    "log_market_status",
    "trading_logger"
]