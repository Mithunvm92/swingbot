"""
Risk Manager Module
=================
Risk management for trading strategies.
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.config import trading
from app.utils.logger import trading_logger


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class RiskLimits:
    """Risk limits configuration"""
    max_risk_per_trade: float = 1.0  # % of capital
    max_daily_loss: float = 2.0  # % of capital
    max_consecutive_losses: int = 3
    max_concurrent_trades: int = 3
    position_size_percent: float = 10.0  # % of capital per trade
    
    def __post_init__(self):
        """Load from config if not set"""
        if self.max_risk_per_trade == 1.0:
            self.max_risk_per_trade = trading.RISK_PER_TRADE_PERCENT
        if self.max_concurrent_trades == 3:
            self.max_concurrent_trades = trading.MAX_SIMULTANEOUS_TRADES
        if self.max_daily_loss == 2.0:
            self.max_daily_loss = trading.DAILY_MAX_LOSS_PERCENT


@dataclass
class TradeRisk:
    """Trade risk information"""
    symbol: str
    quantity: int
    entry_price: float
    stop_loss: float
    target: float
    risk_amount: float
    risk_percent: float
    
    @property
    def reward_risk_ratio(self) -> float:
        """Calculate reward/risk ratio"""
        if self.risk_amount == 0:
            return 0
        reward = (self.target - self.entry_price) * self.quantity
        return abs(reward / self.risk_amount)


# ============================================================================
# RISK MANAGER
# ============================================================================

class RiskManager:
    """
    Risk manager for trading.
    Enforces risk limits and position sizing.
    """
    
    def __init__(self, capital: float, limits: Optional[RiskLimits] = None):
        """
        Initialize risk manager.
        
        Args:
            capital: Trading capital
            limits: Risk limits
        """
        self.capital = capital
        self.limits = limits or RiskLimits()
        
        # Track trades
        self._trades_today: int = 0
        self._losses_today: float = 0.0
        self._consecutive_losses: int = 0
        self._open_positions: int = 0
        self._last_trade_date: Optional[datetime] = None
        self._trade_history: List[dict] = []
    
    def reset_daily(self) -> None:
        """Reset daily counters"""
        today = datetime.now().date()
        
        if self._last_trade_date and self._last_trade_date.date() != today:
            self._trades_today = 0
            self._losses_today = 0.0
            self._last_trade_date = None
            trading_logger.info("Daily counters reset")
    
    def can_trade(
        self,
        symbol: Optional[str] = None,
        check_position: bool = True
    ) -> Tuple[bool, str]:
        """
        Check if can trade.
        
        Args:
            symbol: Symbol to check
            check_position: Check for existing position
        
        Returns:
            Tuple of (can_trade, reason)
        """
        self.reset_daily()
        
        # Check daily loss limit
        if self._losses_today >= self.limits.max_daily_loss:
            return False, f"Daily loss limit reached ({self._losses_today:.2f}%)"
        
        # Check consecutive losses
        if self._consecutive_losses >= self.limits.max_consecutive_losses:
            return False, f"Max consecutive losses reached ({self._consecutive_losses})"
        
        # Check open positions
        if check_position and self._open_positions >= self.limits.max_concurrent_trades:
            return False, f"Max concurrent positions reached ({self._open_positions})"
        
        # Check if already have position in symbol
        if check_position and symbol:
            if self.has_position(symbol):
                return False, f"Position already exists for {symbol}"
        
        return True, "OK"
    
    def calculate_position_size(
        self,
        entry_price: float,
        stop_loss: float
    ) -> Tuple[int, float]:
        """
        Calculate position size based on risk.
        
        Args:
            entry_price: Entry price
            stop_loss: Stop loss price
        
        Returns:
            Tuple of (quantity, total_value)
        """
        # Risk amount in rupees
        risk_amount = self.capital * (self.limits.max_risk_per_trade / 100)
        
        # Risk per share
        risk_per_share = abs(entry_price - stop_loss)
        
        if risk_per_share <= 0:
            return 0, 0
        
        # Calculate quantity
        quantity = int(risk_amount / risk_per_share)
        quantity = max(1, quantity)
        
        # Calculate value
        total_value = quantity * entry_price
        
        # Cap at position size limit
        max_value = self.capital * (self.limits.position_size_percent / 100)
        if total_value > max_value:
            quantity = int(max_value / entry_price)
            quantity = max(1, quantity)
            total_value = quantity * entry_price
        
        # Cap at available capital
        if total_value > self.capital:
            quantity = int(self.capital / entry_price)
            quantity = max(1, quantity)
            total_value = quantity * entry_price
        
        return quantity, total_value
    
    def calculate_stop_loss(
        self,
        entry_price: float,
        quantity: int,
        risk_percent: Optional[float] = None
    ) -> float:
        """
        Calculate stop loss price.
        
        Args:
            entry_price: Entry price
            quantity: Number of shares
            risk_percent: Risk percent (optional)
        
        Returns:
            Stop loss price
        """
        if risk_percent is None:
            risk_percent = trading.STOP_LOSS_PERCENT
        
        return entry_price * (1 - risk_percent / 100)
    
    def calculate_target(
        self,
        entry_price: float,
        quantity: int,
        target_percent: Optional[float] = None,
        reward_risk_ratio: float = 2.0
    ) -> float:
        """
        Calculate target price.
        
        Args:
            entry_price: Entry price
            quantity: Number of shares
            target_percent: Target percent (optional)
            reward_risk_ratio: Reward/risk ratio
        
        Returns:
            Target price
        """
        if target_percent is None:
            target_percent = trading.PROFIT_TARGET_PERCENT
        
        return entry_price * (1 + target_percent / 100)
    
    def record_trade(
        self,
        symbol: str,
        quantity: int,
        entry_price: float,
        exit_price: float,
        trade_type: str
    ) -> None:
        """
        Record a trade for risk tracking.
        
        Args:
            symbol: Trading symbol
            quantity: Number of shares
            entry_price: Entry price
            exit_price: Exit price
            trade_type: Trade type (BUY/SELL)
        """
        pnl = (exit_price - entry_price) * quantity
        pnl_percent = (pnl / (entry_price * quantity)) * 100
        
        self._trade_history.append({
            "symbol": symbol,
            "quantity": quantity,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "pnl": pnl,
            "pnl_percent": pnl_percent,
            "trade_type": trade_type,
            "timestamp": datetime.now()
        })
        
        self._trades_today += 1
        self._last_trade_date = datetime.now()
        
        if pnl < 0:
            self._losses_today += abs(pnl_percent)
            self._consecutive_losses += 1
        else:
            self._consecutive_losses = 0
        
        trading_logger.info(
            f"Trade recorded: {symbol} {trade_type} - P&L: ₹{pnl:.2f} ({pnl_percent:+.2f}%)"
        )
    
    def record_position_open(self, symbol: str) -> None:
        """Record position open"""
        self._open_positions += 1
        trading_logger.info(f"Position opened: {symbol} ({self._open_positions}/{self.limits.max_concurrent_trades})")
    
    def record_position_close(self, symbol: str) -> None:
        """Record position close"""
        self._open_positions = max(0, self._open_positions - 1)
        trading_logger.info(f"Position closed: {symbol} ({self._open_positions}/{self.limits.max_concurrent_trades})")
    
    def has_position(self, symbol: str) -> bool:
        """Check if has open position in symbol"""
        return any(
            t["symbol"] == symbol 
            for t in self._trade_history[-self._open_positions:] 
            if "symbol" in t
        )
    
    def get_daily_pnl(self) -> float:
        """Get today's P&L"""
        today = datetime.now().date()
        
        total_pnl = 0
        for trade in self._trade_history:
            if trade.get("timestamp") and trade["timestamp"].date() == today:
                total_pnl += trade.get("pnl", 0)
        
        return total_pnl
    
    def get_daily_pnl_percent(self) -> float:
        """Get today's P&L percentage"""
        pnl = self.get_daily_pnl()
        return (pnl / self.capital) * 100
    
    def get_open_positions(self) -> int:
        """Get number of open positions"""
        return self._open_positions
    
    def get_risk_metrics(self) -> dict:
        """Get risk metrics"""
        return {
            "capital": self.capital,
            "trades_today": self._trades_today,
            "losses_today": self._losses_today,
            "consecutive_losses": self._consecutive_losses,
            "open_positions": self._open_positions,
            "daily_pnl": self.get_daily_pnl(),
            "daily_pnl_percent": self.get_daily_pnl_percent()
        }
    
    def emergency_stop(self) -> bool:
        """
        Check if emergency stop is needed.
        
        Returns:
            True if should stop trading
        """
        daily_pnl_percent = self.get_daily_pnl_percent()
        
        # Stop if daily loss exceeds limit
        if daily_pnl_percent <= -self.limits.max_daily_loss:
            trading_logger.critical(f"Emergency stop triggered: Daily loss {daily_pnl_percent:.2f}%")
            return True
        
        # Stop if too many consecutive losses
        if self._consecutive_losses >= self.limits.max_consecutive_losses:
            trading_logger.critical(f"Emergency stop triggered: {self._consecutive_losses} consecutive losses")
            return True
        
        return False


# ============================================================================
# POSITION SIZING
# ============================================================================

def calculate_position_size(
    capital: float,
    entry_price: float,
    stop_loss: float,
    risk_percent: float,
    max_position_percent: float = 10.0
) -> Tuple[int, float]:
    """
    Calculate position size (standalone function).
    
    Args:
        capital: Available capital
        entry_price: Entry price
        stop_loss: Stop loss price
        risk_percent: Risk per trade percentage
        max_position_percent: Maximum position size percentage
    
    Returns:
        Tuple of (quantity, total_value)
    """
    # Risk amount
    risk_amount = capital * (risk_percent / 100)
    
    # Risk per share
    risk_per_share = abs(entry_price - stop_loss)
    
    if risk_per_share <= 0:
        return 0, 0
    
    # Calculate quantity
    quantity = int(risk_amount / risk_per_share)
    quantity = max(1, quantity)
    
    # Calculate value
    total_value = quantity * entry_price
    
    # Cap at max position
    max_value = capital * (max_position_percent / 100)
    if total_value > max_value:
        quantity = int(max_value / entry_price)
        quantity = max(1, quantity)
        total_value = quantity * entry_price
    
    # Cap at capital
    if total_value > capital:
        quantity = int(capital / entry_price)
        quantity = max(1, quantity)
        total_value = quantity * entry_price
    
    return quantity, total_value


# ============================================================================
# COOLDOWN TRACKER
# ============================================================================

class CooldownTracker:
    """Tracks trading cooldowns"""
    
    def __init__(self, cooldown_minutes: int = 15):
        """
        Initialize cooldown tracker.
        
        Args:
            cooldown_minutes: Cooldown period in minutes
        """
        self.cooldown_minutes = cooldown_minutes
        self._last_trades: Dict[str, datetime] = {}
    
    def can_trade(self, symbol: str) -> bool:
        """Check if can trade symbol"""
        if symbol not in self._last_trades:
            return True
        
        last_trade = self._last_trades[symbol]
        elapsed = datetime.now() - last_trade
        
        return elapsed.total_seconds() >= self.cooldown_minutes * 60
    
    def record_trade(self, symbol: str) -> None:
        """Record trade"""
        self._last_trades[symbol] = datetime.now()
    
    def get_cooldown_remaining(self, symbol: str) -> float:
        """Get cooldown remaining in minutes"""
        if symbol not in self._last_trades:
            return 0
        
        last_trade = self._last_trades[symbol]
        elapsed = datetime.now() - last_trade
        remaining = (self.cooldown_minutes * 60) - elapsed.total_seconds()
        
        return max(0, remaining / 60)


# ============================================================================
# MAIN RISK MANAGER
# ============================================================================

# Global risk manager instance
_risk_manager: Optional[RiskManager] = None


def get_risk_manager(capital: Optional[float] = None) -> RiskManager:
    """
    Get risk manager instance.
    
    Args:
        capital: Trading capital
    
    Returns:
        RiskManager instance
    """
    global _risk_manager
    
    if _risk_manager is None:
        if capital is None:
            capital = trading.INITIAL_CAPITAL
        _risk_manager = RiskManager(capital)
    
    return _risk_manager


def reset_risk_manager() -> None:
    """Reset risk manager"""
    global _risk_manager
    _risk_manager = None


__all__ = [
    "RiskLimits",
    "TradeRisk",
    "RiskManager",
    "calculate_position_size",
    "CooldownTracker",
    "get_risk_manager",
    "reset_risk_manager"
]