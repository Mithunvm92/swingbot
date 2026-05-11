"""
Paper Trading Engine Module
==========================
Simulated trading engine for testing strategies.
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

from app.config import trading
from app.strategy.ema_strategy import EMACrossoverStrategy, Signal
from app.strategy.risk_manager import RiskManager
from app.scanner.scanner import ScanResult
from app.utils.logger import trading_logger, log_trade


# ============================================================================
# PAPER POSITION
# ============================================================================

@dataclass
class PaperPosition:
    """Paper trading position"""
    symbol: str
    quantity: int
    entry_price: float
    entry_time: datetime
    stop_loss: float = 0.0
    target: float = 0.0
    pnl: float = 0.0
    pnl_percent: float = 0.0
    
    @property
    def current_value(self) -> float:
        """Current position value"""
        return self.quantity * self.entry_price
    
    def update_pnl(self, current_price: float) -> None:
        """Update P&L"""
        self.pnl = (current_price - self.entry_price) * self.quantity
        self.pnl_percent = ((current_price - self.entry_price) / self.entry_price) * 100


# ============================================================================
# PAPER TRADING ENGINE
# ============================================================================

class PaperTradingEngine:
    """
    Paper trading engine.
    Simulates order execution without real money.
    """
    
    def __init__(
        self,
        initial_capital: Optional[float] = None,
        strategy: Optional[EMACrossoverStrategy] = None
    ):
        """
        Initialize paper trading engine.
        
        Args:
            initial_capital: Initial capital
            strategy: Trading strategy
        """
        self.initial_capital = initial_capital or trading.INITIAL_CAPITAL
        self.capital = self.initial_capital
        self.strategy = strategy or EMACrossoverStrategy()
        
        # Risk manager
        self.risk_manager = RiskManager(self.capital)
        
        # Positions
        self.positions: Dict[str, PaperPosition] = {}
        self.orders: List[dict] = []
        self.trade_history: List[dict] = []
        
        # Statistics
        self.stats = {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "total_pnl": 0.0
        }
    
    def reset(self) -> None:
        """Reset paper trading state"""
        self.capital = self.initial_capital
        self.positions = {}
        self.orders = []
        self.trade_history = []
        self.stats = {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "total_pnl": 0.0
        }
    
    def can_buy(self, symbol: str, price: float, quantity: int) -> Tuple[bool, str]:
        """
        Check if can execute buy.
        
        Args:
            symbol: Trading symbol
            price: Entry price
            quantity: Number of shares
        
        Returns:
            Tuple of (can_buy, reason)
        """
        # Check capital
        total_cost = price * quantity
        if total_cost > self.capital:
            return False, "Insufficient capital"
        
        # Check risk manager
        can_trade, reason = self.risk_manager.can_trade(symbol)
        if not can_trade:
            return False, reason
        
        # Check existing position
        if symbol in self.positions:
            return False, "Position already exists"
        
        return True, "OK"
    
    def execute_buy(
        self,
        symbol: str,
        price: float,
        quantity: int,
        stop_loss: float = 0.0,
        target: float = 0.0
    ) -> Tuple[bool, str]:
        """
        Execute simulated buy.
        
        Args:
            symbol: Trading symbol
            price: Entry price
            quantity: Number of shares
            stop_loss: Stop loss price
            target: Target price
        
        Returns:
            Tuple of success and message
        """
        can_buy, reason = self.can_buy(symbol, price, quantity)
        
        if not can_buy:
            trading_logger.warning(f"Cannot execute buy: {reason}")
            return False, reason
        
        # Execute buy
        total_cost = price * quantity
        self.capital -= total_cost
        
        # Create position
        self.positions[symbol] = PaperPosition(
            symbol=symbol,
            quantity=quantity,
            entry_price=price,
            entry_time=datetime.now(),
            stop_loss=stop_loss,
            target=target
        )
        
        # Record order
        self.orders.append({
            "order_id": f"PAPER_{len(self.orders) + 1}",
            "symbol": symbol,
            "type": "BUY",
            "quantity": quantity,
            "price": price,
            "status": "FILLED",
            "timestamp": datetime.now()
        })
        
        # Log trade
        log_trade("BUY", symbol, quantity, price, "BUY", "Paper Trading")
        
        trading_logger.info(f"Paper BUY: {symbol} {quantity} @ ₹{price:.2f}")
        
        return True, "BUY executed"
    
    def can_sell(self, symbol: str) -> Tuple[bool, str]:
        """
        Check if can execute sell.
        
        Args:
            symbol: Trading symbol
        
        Returns:
            Tuple of (can_sell, reason)
        """
        if symbol not in self.positions:
            return False, "No position exists"
        
        return True, "OK"
    
    def execute_sell(
        self,
        symbol: str,
        price: float,
        exit_reason: str = ""
    ) -> Tuple[bool, str]:
        """
        Execute simulated sell.
        
        Args:
            symbol: Trading symbol
            price: Exit price
            exit_reason: Exit reason (TARGET, SL, SIGNAL)
        
        Returns:
            Tuple of success and message
        """
        can_sell, reason = self.can_sell(symbol)
        
        if not can_sell:
            return False, reason
        
        position = self.positions[symbol]
        
        # Calculate P&L
        pnl = (price - position.entry_price) * position.quantity
        pnl_percent = ((price - position.entry_price) / position.entry_price) * 100
        
        # Execute sell
        total_proceeds = price * position.quantity
        self.capital += total_proceeds
        
        # Update statistics
        self.stats["total_trades"] += 1
        if pnl > 0:
            self.stats["winning_trades"] += 1
        else:
            self.stats["losing_trades"] += 1
        self.stats["total_pnl"] += pnl
        
        # Record trade
        self.trade_history.append({
            "symbol": symbol,
            "type": "SELL",
            "quantity": position.quantity,
            "entry_price": position.entry_price,
            "exit_price": price,
            "pnl": pnl,
            "pnl_percent": pnl_percent,
            "exit_reason": exit_reason,
            "timestamp": datetime.now()
        })
        
        # Log trade
        if exit_reason == "SL":
            log_trade("SL_HIT", symbol, position.quantity, price, "SELL", f"Paper: {exit_reason}")
        elif exit_reason == "TARGET":
            log_trade("TARGET_HIT", symbol, position.quantity, price, "SELL", f"Paper: {exit_reason}")
        else:
            log_trade("SELL", symbol, position.quantity, price, "SELL", f"Paper: {exit_reason}")
        
        # Remove position
        del self.positions[symbol]
        
        trading_logger.info(f"Paper SELL: {symbol} @ ₹{price:.2f} | P&L: ₹{pnl:.2f} ({pnl_percent:.2f}%)")
        
        return True, f"SELL executed - P&L: ₹{pnl:.2f}"
    
    def check_exits(
        self,
        symbol: str,
        current_price: float
    ) -> Optional[str]:
        """
        Check if should exit position.
        
        Args:
            symbol: Trading symbol
            current_price: Current price
        
        Returns:
            Exit reason if should exit, None otherwise
        """
        if symbol not in self.positions:
            return None
        
        position = self.positions[symbol]
        position.update_pnl(current_price)
        
        # Check stop loss
        if position.pnl_percent <= -trading.STOP_LOSS_PERCENT:
            return "SL"
        
        # Check target
        if position.pnl_percent >= trading.PROFIT_TARGET_PERCENT:
            return "TARGET"
        
        # Check exit through strategy
        should_exit, reason = self.strategy.should_exit(
            symbol=symbol,
            entry_price=position.entry_price,
            current_price=current_price,
            close_prices=[position.entry_price, current_price]
        )
        
        if should_exit:
            return reason
        
        return None
    
    def execute_exit(
        self,
        symbol: str,
        current_price: float
    ) -> Tuple[bool, str]:
        """
        Execute exit if conditions met.
        
        Args:
            symbol: Trading symbol
            current_price: Current price
        
        Returns:
            Tuple of success and message
        """
        exit_reason = self.check_exits(symbol, current_price)
        
        if exit_reason:
            return self.execute_sell(symbol, current_price, exit_reason)
        
        return False, "No exit conditions met"
    
    def process_scan_result(self, result: ScanResult) -> None:
        """
        Process scan result.
        
        Args:
            result: ScanResult object
        """
        if not result.has_signal or not result.quote:
            return
        
        signal = result.signal
        
        # Check if can buy
        can_buy, _ = self.can_buy(
            signal.symbol,
            signal.entry_price,
            int(trading.MAX_CAPITAL_PER_TRADE / signal.entry_price)
        )
        
        if not can_buy:
            return
        
        # Execute buy
        quantity = int(trading.MAX_CAPITAL_PER_TRADE / signal.entry_price)
        quantity = max(1, quantity)
        
        self.execute_buy(
            symbol=signal.symbol,
            price=signal.entry_price,
            quantity=quantity,
            stop_loss=signal.stop_loss,
            target=signal.target_price
        )
    
    def process_quote(self, symbol: str, quote) -> None:
        """
        Process quote for position monitoring.
        
        Args:
            symbol: Trading symbol
            quote: Quote object
        """
        if symbol not in self.positions:
            return
        
        # Check exits
        self.execute_exit(symbol, quote.last_price)
    
    def get_position(self, symbol: str) -> Optional[PaperPosition]:
        """Get position for symbol"""
        return self.positions.get(symbol)
    
    def get_open_positions(self) -> Dict[str, PaperPosition]:
        """Get all open positions"""
        return self.positions.copy()
    
    def get_statistics(self) -> dict:
        """Get trading statistics"""
        stats = self.stats.copy()
        stats["capital"] = self.capital
        stats["open_positions"] = len(self.positions)
        
        if stats["total_trades"] > 0:
            stats["win_rate"] = (stats["winning_trades"] / stats["total_trades"]) * 100
        else:
            stats["win_rate"] = 0
        
        return stats
    
    def get_equity(self) -> float:
        """Get total equity"""
        equity = self.capital
        for position in self.positions.values():
            equity += position.current_value
        return equity
    
    def get_daily_pnl(self) -> float:
        """Get today's P&L"""
        today = datetime.now().date()
        
        daily_pnl = 0
        for trade in self.trade_history:
            if trade["timestamp"].date() == today:
                daily_pnl += trade["pnl"]
        
        return daily_pnl


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def create_paper_engine(capital: float = 100000) -> PaperTradingEngine:
    """
    Create paper trading engine.
    
    Args:
        capital: Initial capital
    
    Returns:
        PaperTradingEngine instance
    """
    return PaperTradingEngine(initial_capital=capital)


__all__ = [
    "PaperPosition",
    "PaperTradingEngine",
    "create_paper_engine"
]