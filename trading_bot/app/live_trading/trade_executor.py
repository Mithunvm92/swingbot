"""
Live Trading Engine Module
=========================
Live trading execution with Zerodha.
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import time

from app.config import trading
from app.broker.zerodha_client import ZerodhaClient, Position, Order
from app.strategy.ema_strategy import EMACrossoverStrategy, Signal
from app.strategy.risk_manager import RiskManager
from app.scanner.scanner import ScanResult
from app.alerts.telegram_alert import get_telegram_bot, get_notifier
from app.database.database import get_trade_repository, Trade, TradeType, OrderStatus
from app.utils.logger import trading_logger, log_trade


# ============================================================================
# LIVE TRADING ENGINE
# ============================================================================

class LiveTradingEngine:
    """
    Live trading engine.
    Executes real trades on Zerodha.
    """
    
    def __init__(
        self,
        initial_capital: Optional[float] = None,
        client: Optional[ZerodhaClient] = None,
        strategy: Optional[EMACrossoverStrategy] = None
    ):
        """
        Initialize live trading engine.
        
        Args:
            initial_capital: Initial capital
            client: ZerodhaClient instance
            strategy: Trading strategy
        """
        self.initial_capital = initial_capital or trading.INITIAL_CAPITAL
        self.client = client or ZerodhaClient()
        self.strategy = strategy or EMACrossoverStrategy()
        
        # Risk manager
        self.risk_manager = RiskManager(self.initial_capital)
        
        # Notifications
        self.notifier = get_notifier()
        
        # Position tracking
        self.positions: Dict[str, dict] = {}
        
        # Order tracking
        self.pending_orders: Dict[str, str] = {}  # order_id -> symbol
        
        # Trading statistics
        self.stats = {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "total_pnl": 0.0
        }
        
        # Kill switch
        self._kill_switch = False
    
    def enable_kill_switch(self) -> None:
        """Enable kill switch (stop all trading)"""
        self._kill_switch = True
        trading_logger.critical("Kill switch ENABLED - All trading stopped")
    
    def disable_kill_switch(self) -> None:
        """Disable kill switch"""
        self._kill_switch = False
        trading_logger.info("Kill switch DISABLED")
    
    def is_kill_switch_active(self) -> bool:
        """Check if kill switch is active"""
        return self._kill_switch
    
    def get_balance(self) -> float:
        """Get available balance"""
        return self.client.get_balance()
    
    def can_trade(self, symbol: str) -> Tuple[bool, str]:
        """
        Check if can trade.
        
        Args:
            symbol: Trading symbol
        
        Returns:
            Tuple of (can_trade, reason)
        """
        if self.is_kill_switch_active():
            return False, "Kill switch is active"
        
        # Check risk manager
        can_trade, reason = self.risk_manager.can_trade(symbol)
        if not can_trade:
            return False, reason
        
        # Check existing position
        if self.has_position(symbol):
            return False, "Position already exists"
        
        balance = self.get_balance()
        if balance < trading.MAX_CAPITAL_PER_TRADE:
            return False, "Insufficient balance"
        
        return True, "OK"
    
    def place_buy_order(
        self,
        symbol: str,
        quantity: int,
        price: float = 0.0,
        order_type: str = "MARKET"
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Place buy order.
        
        Args:
            symbol: Trading symbol
            quantity: Number of shares
            price: Limit price (0 for market)
            order_type: Order type
        
        Returns:
            Tuple of (success, message, order_id)
        """
        can_trade, reason = self.can_trade(symbol)
        
        if not can_trade:
            return False, reason, None
        
        try:
            # Place order
            order_id = self.client.buy_order(
                symbol=symbol,
                quantity=quantity,
                price=price,
                order_type=order_type
            )
            
            # Track position
            self.positions[symbol] = {
                "order_id": order_id,
                "quantity": quantity,
                "entry_price": price,
                "entry_time": datetime.now()
            }
            
            # Record in database
            trade_repo = get_trade_repository()
            trade = Trade(
                symbol=symbol,
                trade_type=TradeType.BUY,
                quantity=quantity,
                entry_price=price,
                order_id=order_id,
                status=OrderStatus.PENDING,
                entry_time=datetime.now()
            )
            trade_repo.create(trade)
            
            # Send notification
            self.notifier.notify_order(Order(
                order_id=order_id,
                trading_symbol=symbol,
                transaction_type="BUY",
                quantity=quantity,
                average_price=price,
                order_type=order_type,
                product=trading.ORDER_TYPE,
                status="PENDING"
            ))
            
            log_trade("BUY", symbol, quantity, price, "LIVE", f"Order: {order_id}")
            
            return True, f"Order placed: {order_id}", order_id
            
        except Exception as e:
            error_msg = f"Order failed: {e}"
            trading_logger.error(error_msg)
            self.notifier.send_error(error_msg)
            return False, error_msg, None
    
    def place_sell_order(
        self,
        symbol: str,
        quantity: int,
        price: float = 0.0,
        order_type: str = "MARKET"
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Place sell order.
        
        Args:
            symbol: Trading symbol
            quantity: Number of shares
            price: Limit price (0 for market)
            order_type: Order type
        
        Returns:
            Tuple of (success, message, order_id)
        """
        # Check if position exists
        position = self.client.get_position(symbol)
        
        if not position or position.quantity == 0:
            return False, "No position to sell", None
        
        try:
            # Place order
            order_id = self.client.sell_order(
                symbol=symbol,
                quantity=quantity,
                price=price,
                order_type=order_type
            )
            
            # Track pending order
            self.pending_orders[order_id] = symbol
            
            # Update database
            trade_repo = get_trade_repository()
            trades = trade_repo.get_by_symbol(symbol, OrderStatus.PENDING)
            
            entry_price = position.average_price
            pnl = (price - entry_price) * quantity if price > 0 else 0
            pnl_percent = ((price - entry_price) / entry_price) * 100 if price > 0 else 0
            
            for trade in trades:
                trade.status = OrderStatus.COMPLETE
                trade.exit_price = price
                trade.pnl = pnl
                trade.pnl_percent = pnl_percent
                trade.exit_time = datetime.now()
                trade_repo.update(trade)
            
            # Update statistics
            self.stats["total_trades"] += 1
            if pnl > 0:
                self.stats["winning_trades"] += 1
            else:
                self.stats["losing_trades"] += 1
            self.stats["total_pnl"] += pnl
            
            # Notification
            if pnl <= 0:
                self.notifier.notify_exit(
                    symbol=symbol,
                    entry=entry_price,
                    exit_price=price,
                    pnl=pnl,
                    pnl_percent=pnl_percent,
                    exit_type="SL" if pnl < 0 else "TARGET"
                )
            
            log_trade("SELL", symbol, quantity, price, "LIVE", f"Order: {order_id}")
            
            return True, f"Order placed: {order_id}", order_id
            
        except Exception as e:
            error_msg = f"Order failed: {e}"
            trading_logger.error(error_msg)
            self.notifier.send_error(error_msg)
            return False, error_msg, None
    
    def has_position(self, symbol: str) -> bool:
        """Check if has open position"""
        position = self.client.get_position(symbol)
        return position is not None and position.quantity > 0
    
    def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for symbol"""
        return self.client.get_position(symbol)
    
    def get_all_positions(self) -> List[Position]:
        """Get all open positions"""
        return self.client.get_open_positions()
    
    def place_stoploss_order(
        self,
        symbol: str,
        quantity: int,
        trigger_price: float
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Place stop loss order (GTT).
        
        Args:
            symbol: Trading symbol
            quantity: Number of shares
            trigger_price: Trigger price
        
        Returns:
            Tuple of (success, message, trigger_id)
        """
        position = self.get_position(symbol)
        
        if not position:
            return False, "No position to place SL", None
        
        try:
            # Get current price
            quote = self.client.get_quote(symbol)
            current_price = quote.last_price
            
            # Place GTT order
            trigger_id = self.client.place_gtt_order(
                symbol=symbol,
                transaction_type="SELL",
                quantity=quantity,
                trigger_price=trigger_price,
                last_price=current_price,
                order_type="MARKET"
            )
            
            trading_logger.info(f"GTT placed: {symbol} @ ₹{trigger_price}")
            
            return True, f"GTT placed: {trigger_id}", trigger_id
            
        except Exception as e:
            error_msg = f"GTT placement failed: {e}"
            trading_logger.error(error_msg)
            return False, error_msg, None
    
    def execute_buy_from_signal(
        self,
        signal: Signal,
        quantity: int
    ) -> Tuple[bool, str]:
        """
        Execute buy from signal.
        
        Args:
            signal: Signal object
            quantity: Number of shares
        
        Returns:
            Tuple of success and message
        """
        success, msg, order_id = self.place_buy_order(
            symbol=signal.symbol,
            quantity=quantity,
            price=0,  # Market order
            order_type="MARKET"
        )
        
        if success:
            # Open strategy position
            self.strategy.open_position(signal.symbol, signal.entry_price)
            
            # Record in risk manager
            self.risk_manager.record_position_open(signal.symbol)
            
            # Send signal notification
            self.notifier.telegram.send_buy_signal(
                symbol=signal.symbol,
                entry=signal.entry_price,
                stop_loss=signal.stop_loss,
                target=signal.target_price,
                confidence=signal.confidence,
                reason=signal.reason
            )
        
        return success, msg
    
    def execute_exit(
        self,
        symbol: str,
        exit_reason: str = ""
    ) -> Tuple[bool, str]:
        """
        Execute position exit.
        
        Args:
            symbol: Trading symbol
            exit_reason: Exit reason
        
        Returns:
            Tuple of success and message
        """
        position = self.get_position(symbol)
        
        if not position:
            return False, "No position"
        
        success, msg, _ = self.place_sell_order(
            symbol=symbol,
            quantity=abs(position.quantity),
            price=0,  # Market order
            order_type="MARKET"
        )
        
        if success:
            # Close strategy position
            self.strategy.close_position(symbol)
            
            # Record in risk manager
            self.risk_manager.record_position_close(symbol)
            
            # Record P&L
            entry_price = position.average_price
            current_price = position.last_price
            pnl = (current_price - entry_price) * position.quantity
            self.risk_manager.record_trade(
                symbol=symbol,
                quantity=position.quantity,
                entry_price=entry_price,
                exit_price=current_price,
                trade_type="SELL"
            )
        
        return success, msg
    
    def process_scan_result(self, result: ScanResult) -> None:
        """
        Process scan result for live trading.
        
        Args:
            result: ScanResult object
        """
        if not result.has_signal or not result.quote:
            return
        
        signal = result.signal
        
        # Calculate position size
        risk_manager = self.risk_manager
        quantity, _ = risk_manager.calculate_position_size(
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss
        )
        
        if quantity == 0:
            trading_logger.warning(f"Cannot calculate position size for {signal.symbol}")
            return
        
        # Execute buy
        self.execute_buy_from_signal(signal, quantity)
    
    def monitor_positions(self) -> None:
        """Monitor and exit positions if needed"""
        for position in self.get_all_positions():
            # Check exits through strategy
            should_exit, reason = self.strategy.should_exit(
                symbol=position.trading_symbol,
                entry_price=position.average_price,
                current_price=position.last_price,
                close_prices=[position.average_price, position.last_price]
            )
            
            if should_exit:
                self.execute_exit(position.trading_symbol, reason)
    
    def get_statistics(self) -> dict:
        """Get trading statistics"""
        stats = self.stats.copy()
        
        # Add live positions
        positions = self.get_all_positions()
        stats["open_positions"] = len(positions)
        stats["capital"] = self.get_balance()
        
        return stats


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def create_live_engine(capital: float = 100000) -> LiveTradingEngine:
    """
    Create live trading engine.
    
    Args:
        capital: Initial capital
    
    Returns:
        LiveTradingEngine instance
    """
    return LiveTradingEngine(initial_capital=capital)


__all__ = [
    "LiveTradingEngine",
    "create_live_engine"
]