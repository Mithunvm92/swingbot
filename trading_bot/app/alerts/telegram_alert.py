"""
Telegram Alert Module
====================
Telegram bot alerts for trading signals and notifications.
"""

import requests
from typing import Optional, Dict, List
from dataclasses import dataclass
from datetime import datetime

from app.config import telegram
from app.utils.logger import trading_logger


# ============================================================================
# MESSAGE TYPES
# ============================================================================

class MessageType:
    """Telegram message types"""
    BUY_SIGNAL = "BUY_SIGNAL"
    SELL_SIGNAL = "SELL_SIGNAL"
    ORDER_PLACED = "ORDER_PLACED"
    ORDER_CANCELLED = "ORDER_CANCELLED"
    STOP_LOSS_HIT = "STOP_LOSS_HIT"
    TARGET_HIT = "TARGET_HIT"
    DAILY_SUMMARY = "DAILY_SUMMARY"
    ERROR = "ERROR"
    INFO = "INFO"


# ============================================================================
# MESSAGE TEMPLATES
# ============================================================================

MESSAGE_TEMPLATES = {
    MessageType.BUY_SIGNAL: """
📈 *BUY SIGNAL*
━━━━━━━━━━━━━━━━━━━━
Stock: {symbol}
Entry: ₹{entry}
Stop Loss: ₹{stop_loss}
Target: ₹{target}
Confidence: {confidence}%
Reason: {reason}
""",
    
    MessageType.SELL_SIGNAL: """
📉 *SELL SIGNAL*
━━━━━━━━━━━━━━━━━━━━
Stock: {symbol}
Reason: {reason}
""",
    
    MessageType.ORDER_PLACED: """
✅ *ORDER PLACED*
━━━━━━━━━━━━━━━━━━━━
Stock: {symbol}
Type: {order_type}
Quantity: {quantity}
Price: ₹{price}
Order ID: {order_id}
""",
    
    MessageType.ORDER_CANCELLED: """
❌ *ORDER CANCELLED*
━━━━━━━━━━━━━━━━━━━━
Stock: {symbol}
Order ID: {order_id}
""",
    
    MessageType.STOP_LOSS_HIT: """
🛑 *STOP LOSS HIT*
━━━━━━━━━━━━━━━━━━━━
Stock: {symbol}
Entry: ₹{entry}
Exit: ₹{exit}
P&L: ₹{pnl} ({pnl_percent}%)
""",
    
    MessageType.TARGET_HIT: """
🎯 *TARGET HIT*
━━━━━━━━━━━━━━━━━━━━
Stock: {symbol}
Entry: ₹{entry}
Exit: ₹{exit}
P&L: ₹{pnl} ({pnl_percent}%)
""",
    
    MessageType.DAILY_SUMMARY: """
📊 *DAILY SUMMARY*
━━━━━━━━━━━━━━━━━━━━
Date: {date}
Trades: {trades}
P&L: ₹{pnl} ({pnl_percent}%)
Capital: ₹{capital}
Open Positions: {open_positions}
""",
    
    MessageType.ERROR: """
⚠️ *ERROR*
━━━━━━━━━━━━━━━━━━━━
{error}
""",
    
    MessageType.INFO: """
ℹ️ *INFO*
━━━━━━━━━━━━━━━━━━━━
{message}
"""
}


# ============================================================================
# TELEGRAM BOT
# ============================================================================

class TelegramAlert:
    """
    Telegram alert bot.
    Sends alerts and notifications to configured chat.
    """
    
    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None
    ):
        """
        Initialize Telegram bot.
        
        Args:
            bot_token: Telegram bot token
            chat_id: Telegram chat ID
        """
        self.bot_token = bot_token or telegram.BOT_TOKEN
        self.chat_id = chat_id or telegram.CHAT_ID
        
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}"
        
        # Enable/disable alerts
        self.enable_buy = telegram.ENABLE_BUY_SIGNALS
        self.enable_sell = telegram.ENABLE_SELL_SIGNALS
        self.enable_orders = telegram.ENABLE_ORDER_EXECUTIONS
        self.enable_daily = telegram.ENABLE_DAILY_SUMMARY
        self.enable_errors = telegram.ENABLE_ERRORS
    
    def _send_message(self, text: str, parse_mode: str = "Markdown") -> bool:
        """
        Send message to Telegram.
        
        Args:
            text: Message text
            parse_mode: Parse mode (Markdown, HTML)
        
        Returns:
            True if successful
        """
        if not self.bot_token or not self.chat_id:
            trading_logger.warning("Telegram not configured")
            return False
        
        try:
            url = f"{self.api_url}/sendMessage"
            
            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": parse_mode,
                "disable_web_page_preview": True
            }
            
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                trading_logger.debug(f"Telegram message sent: {text[:50]}...")
                return True
            else:
                trading_logger.error(f"Telegram error: {response.text}")
                return False
                
        except Exception as e:
            trading_logger.error(f"Error sending Telegram message: {e}")
            return False
    
    def send_message(self, message: str) -> bool:
        """
        Send plain message.
        
        Args:
            message: Message text
        
        Returns:
            True if successful
        """
        return self._send_message(message)
    
    def send_buy_signal(
        self,
        symbol: str,
        entry: float,
        stop_loss: float,
        target: float,
        confidence: float = 0,
        reason: str = ""
    ) -> bool:
        """
        Send buy signal alert.
        
        Args:
            symbol: Stock symbol
            entry: Entry price
            stop_loss: Stop loss price
            target: Target price
            confidence: Signal confidence
            reason: Signal reason
        
        Returns:
            True if successful
        """
        if not self.enable_buy:
            return False
        
        text = MESSAGE_TEMPLATES[MessageType.BUY_SIGNAL].format(
            symbol=symbol,
            entry=f"{entry:.2f}",
            stop_loss=f"{stop_loss:.2f}",
            target=f"{target:.2f}",
            confidence=f"{confidence:.1f}",
            reason=reason
        )
        
        return self._send_message(text)
    
    def send_sell_signal(
        self,
        symbol: str,
        reason: str = ""
    ) -> bool:
        """
        Send sell signal alert.
        
        Args:
            symbol: Stock symbol
            reason: Signal reason
        
        Returns:
            True if successful
        """
        if not self.enable_sell:
            return False
        
        text = MESSAGE_TEMPLATES[MessageType.SELL_SIGNAL].format(
            symbol=symbol,
            reason=reason
        )
        
        return self._send_message(text)
    
    def send_order_placed(
        self,
        symbol: str,
        order_type: str,
        quantity: int,
        price: float,
        order_id: str = ""
    ) -> bool:
        """
        Send order placed alert.
        
        Args:
            symbol: Stock symbol
            order_type: Order type (BUY/SELL)
            quantity: Number of shares
            price: Order price
            order_id: Order ID
        
        Returns:
            True if successful
        """
        if not self.enable_orders:
            return False
        
        text = MESSAGE_TEMPLATES[MessageType.ORDER_PLACED].format(
            symbol=symbol,
            order_type=order_type,
            quantity=quantity,
            price=f"{price:.2f}",
            order_id=order_id
        )
        
        return self._send_message(text)
    
    def send_order_cancelled(
        self,
        symbol: str,
        order_id: str
    ) -> bool:
        """
        Send order cancelled alert.
        
        Args:
            symbol: Stock symbol
            order_id: Order ID
        
        Returns:
            True if successful
        """
        if not self.enable_orders:
            return False
        
        text = MESSAGE_TEMPLATES[MessageType.ORDER_CANCELLED].format(
            symbol=symbol,
            order_id=order_id
        )
        
        return self._send_message(text)
    
    def send_stop_loss_hit(
        self,
        symbol: str,
        entry: float,
        exit_price: float,
        pnl: float,
        pnl_percent: float
    ) -> bool:
        """
        Send stop loss hit alert.
        
        Args:
            symbol: Stock symbol
            entry: Entry price
            exit_price: Exit price
            pnl: P&L amount
            pnl_percent: P&L percentage
        
        Returns:
            True if successful
        """
        if not self.enable_orders:
            return False
        
        text = MESSAGE_TEMPLATES[MessageType.STOP_LOSS_HIT].format(
            symbol=symbol,
            entry=f"{entry:.2f}",
            exit=f"{exit_price:.2f}",
            pnl=f"{pnl:.2f}",
            pnl_percent=f"{pnl_percent:.2f}"
        )
        
        return self._send_message(text)
    
    def send_target_hit(
        self,
        symbol: str,
        entry: float,
        exit_price: float,
        pnl: float,
        pnl_percent: float
    ) -> bool:
        """
        Send target hit alert.
        
        Args:
            symbol: Stock symbol
            entry: Entry price
            exit_price: Exit price
            pnl: P&L amount
            pnl_percent: P&L percentage
        
        Returns:
            True if successful
        """
        if not self.enable_orders:
            return False
        
        text = MESSAGE_TEMPLATES[MessageType.TARGET_HIT].format(
            symbol=symbol,
            entry=f"{entry:.2f}",
            exit=f"{exit_price:.2f}",
            pnl=f"{pnl:.2f}",
            pnl_percent=f"{pnl_percent:.2f}"
        )
        
        return self._send_message(text)
    
    def send_daily_summary(
        self,
        date: str,
        trades: int,
        pnl: float,
        pnl_percent: float,
        capital: float,
        open_positions: int
    ) -> bool:
        """
        Send daily summary.
        
        Args:
            date: Trading date
            trades: Number of trades
            pnl: Total P&L
            pnl_percent: P&L percentage
            capital: Current capital
            open_positions: Number of open positions
        
        Returns:
            True if successful
        """
        if not self.enable_daily:
            return False
        
        text = MESSAGE_TEMPLATES[MessageType.DAILY_SUMMARY].format(
            date=date,
            trades=trades,
            pnl=f"{pnl:.2f}",
            pnl_percent=f"{pnl_percent:.2f}",
            capital=f"{capital:.2f}",
            open_positions=open_positions
        )
        
        return self._send_message(text)
    
    def send_error(self, error: str) -> bool:
        """
        Send error alert.
        
        Args:
            error: Error message
        
        Returns:
            True if successful
        """
        if not self.enable_errors:
            return False
        
        text = MESSAGE_TEMPLATES[MessageType.ERROR].format(
            error=error
        )
        
        return self._send_message(text)
    
    def send_info(self, message: str) -> bool:
        """
        Send info message.
        
        Args:
            message: Info message
        
        Returns:
            True if successful
        """
        text = MESSAGE_TEMPLATES[MessageType.INFO].format(
            message=message
        )
        
        return self._send_message(text)
    
    def test_connection(self) -> bool:
        """
        Test bot connection.
        
        Returns:
            True if connected
        """
        try:
            url = f"{self.api_url}/getMe"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    trading_logger.info(f"Telegram bot connected: {data.get('result', {}).get('username')}")
                    return True
            
            return False
            
        except Exception as e:
            trading_logger.error(f"Telegram connection test failed: {e}")
            return False


# ============================================================================
# NOTIFIER
# ============================================================================

class TradingNotifier:
    """Trading notifications manager"""
    
    def __init__(self):
        """Initialize notifier"""
        self.telegram = TelegramAlert()
    
    def notify_signal(self, signal) -> bool:
        """
        Notify signal.
        
        Args:
            signal: Signal object
        
        Returns:
            True if successful
        """
        if signal.is_buy():
            return self.telegram.send_buy_signal(
                symbol=signal.symbol,
                entry=signal.entry_price,
                stop_loss=signal.stop_loss,
                target=signal.target_price,
                confidence=signal.confidence,
                reason=signal.reason
            )
        else:
            return self.telegram.send_sell_signal(
                symbol=signal.symbol,
                reason=signal.reason
            )
    
    def notify_order(self, order) -> bool:
        """
        Notify order execution.
        
        Args:
            order: Order object
        
        Returns:
            True if successful
        """
        return self.telegram.send_order_placed(
            symbol=order.trading_symbol,
            order_type=order.transaction_type,
            quantity=order.quantity,
            price=order.average_price,
            order_id=order.order_id
        )
    
    def notify_exit(
        self,
        symbol: str,
        entry: float,
        exit_price: float,
        pnl: float,
        pnl_percent: float,
        exit_type: str
    ) -> bool:
        """
        Notify position exit.
        
        Args:
            symbol: Stock symbol
            entry: Entry price
            exit_price: Exit price
            pnl: P&L amount
            pnl_percent: P&L percentage
            exit_type: Exit type (SL or TARGET)
        
        Returns:
            True if successful
        """
        if exit_type == "SL":
            return self.telegram.send_stop_loss_hit(
                symbol=symbol,
                entry=entry,
                exit_price=exit_price,
                pnl=pnl,
                pnl_percent=pnl_percent
            )
        else:
            return self.telegram.send_target_hit(
                symbol=symbol,
                entry=entry,
                exit_price=exit_price,
                pnl=pnl,
                pnl_percent=pnl_percent
            )


# ============================================================================
# INITIALIZATION
# ============================================================================

def get_telegram_bot() -> TelegramAlert:
    """
    Get Telegram bot instance.
    
    Returns:
        TelegramAlert instance
    """
    return TelegramAlert()


def get_notifier() -> TradingNotifier:
    """
    Get trading notifier instance.
    
    Returns:
        TradingNotifier instance
    """
    return TradingNotifier()


__all__ = [
    "MessageType",
    "MESSAGE_TEMPLATES",
    "TelegramAlert",
    "TradingNotifier",
    "get_telegram_bot",
    "get_notifier"
]