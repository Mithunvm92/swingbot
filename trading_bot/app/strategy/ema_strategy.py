"""
EMA Crossover Strategy Module
========================
Trend-following EMA crossover swing trading strategy implementation.
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import pandas as pd

from app.config import trading
from app.strategy.indicators import calculate_ema, calculate_ema_values, is_price_above_ema, is_volume_above_average, analyze_trend
from app.utils.logger import trading_logger, log_signal


# ============================================================================
# SIGNAL TYPES
# ============================================================================

class SignalType:
    """Trading signal types"""
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    NEUTRAL = "NEUTRAL"
    SELL = "SELL"
    STRONG_SELL = "STRONG_SELL"


class Signal:
    """Trading signal"""
    def __init__(
        self,
        symbol: str,
        signal_type: str,
        entry_price: float,
        stop_loss: float,
        target_price: float,
        confidence: float = 0.0,
        reason: str = ""
    ):
        self.symbol = symbol
        self.signal_type = signal_type
        self.entry_price = entry_price
        self.stop_loss = stop_loss
        self.target_price = target_price
        self.confidence = confidence
        self.reason = reason
        self.timestamp = datetime.now()
    
    def __str__(self):
        return (f"{self.signal_type}: {self.symbol} @ ₹{self.entry_price:.2f} "
               f"SL: ₹{self.stop_loss:.2f} Tgt: ₹{self.target_price:.2f}")
    
    def is_buy(self) -> bool:
        """Check if buy signal"""
        return self.signal_type in [SignalType.BUY, SignalType.STRONG_BUY]
    
    def is_sell(self) -> bool:
        """Check if sell signal"""
        return self.signal_type in [SignalType.SELL, SignalType.STRONG_SELL]


# ============================================================================
# EMA CROSSOVER STRATEGY
# ============================================================================

class EMACrossoverStrategy:
    """
    Trend-following EMA crossover strategy.
    
    Buy Conditions:
    1. 20 EMA crosses above 50 EMA
    2. Current candle closes above both EMAs
    3. Current volume > 20-day average volume
    4. Nifty 50 market trend bullish
    5. Avoid duplicate entries
    
    Sell Conditions:
    1. Profit target reaches 3%-5%
    2. Stop loss reaches 2%
    3. 20 EMA crosses below 50 EMA
    """
    
    def __init__(
        self,
        fast_ema_period: int = 20,
        slow_ema_period: int = 50,
        volume_ma_period: int = 20,
        profit_target_percent: float = 4.0,
        stop_loss_percent: float = 2.0,
        market_trend_check: bool = True
    ):
        """
        Initialize strategy.
        
        Args:
            fast_ema_period: Fast EMA period
            slow_ema_period: Slow EMA period
            volume_ma_period: Volume MA period
            profit_target_percent: Profit target percentage
            stop_loss_percent: Stop loss percentage
            market_trend_check: Check market trend
        """
        self.fast_ema_period = fast_ema_period
        self.slow_ema_period = slow_ema_period
        self.volume_ma_period = volume_ma_period
        self.profit_target_percent = profit_target_percent
        self.stop_loss_percent = stop_loss_percent
        self.market_trend_check = market_trend_check
        
        # Load from config
        if profit_target_percent == 0:
            self.profit_target_percent = trading.PROFIT_TARGET_PERCENT
        if stop_loss_percent == 0:
            self.stop_loss_percent = trading.STOP_LOSS_PERCENT
        
        self._last_signals: Dict[str, Signal] = {}
        self._positions: Dict[str, float] = {}  # symbol -> entry price
    
    def set_market_trend_checker(self, checker) -> None:
        """Set market trend checker function"""
        self.market_trend_checker = checker
    
    def analyze(
        self,
        symbol: str,
        close_prices: List[float],
        high_prices: Optional[List[float]] = None,
        low_prices: Optional[List[float]] = None,
        volumes: Optional[List[int]] = None
    ) -> Optional[Signal]:
        """
        Analyze symbol and generate signal.
        
        Args:
            symbol: Trading symbol
            close_prices: Close prices
            high_prices: High prices (optional)
            low_prices: Low prices (optional)
            volumes: Volumes (optional)
        
        Returns:
            Signal if any, None otherwise
        """
        # Convert to Series
        close_series = pd.Series(close_prices)
        
        if len(close_series) < max(self.slow_ema_period + 5, self.volume_ma_period + 5):
            trading_logger.warning(f"Insufficient data for {symbol}")
            return None
        
        # Get EMA values
        ema_values = calculate_ema_values(
            close_series,
            self.fast_ema_period,
            self.slow_ema_period
        )
        
        current_price = close_series.iloc[-1]
        signal_type = SignalType.NEUTRAL
        
        # Check buy conditions
        if ema_values["signal"] == "GOLDEN_CROSS":
            # Check price above EMAs
            if current_price > ema_values["fast_ema"] and current_price > ema_values["slow_ema"]:
                # Check volume
                if volumes and is_volume_above_average(pd.Series(volumes), self.volume_ma_period):
                    # Check market trend
                    if self.market_trend_check:
                        trend = "UP"  # Default bullish if no checker
                        if hasattr(self, 'market_trend_checker'):
                            trend = self.market_trend_checker()
                        
                        if trend == "UP":
                            signal_type = SignalType.STRONG_BUY
                            reason = "EMA Golden Cross + Strong Volume"
                        else:
                            signal_type = SignalType.BUY
                            reason = "EMA Golden Cross"
                    else:
                        signal_type = SignalType.BUY
                        reason = "EMA Golden Cross"
        
        # Check sell conditions
        elif ema_values["signal"] == "DEATH_CROSS":
            signal_type = SignalType.SELL
            reason = "EMA Death Cross"
        
        # Generate signal if not neutral
        if signal_type != SignalType.NEUTRAL:
            # Calculate stop loss and target
            if signal_type in [SignalType.BUY, SignalType.STRONG_BUY]:
                stop_loss = current_price * (1 - self.stop_loss_percent / 100)
                target = current_price * (1 + self.profit_target_percent / 100)
                confidence = self._calculate_confidence(ema_values, close_series, volumes)
                
                signal = Signal(
                    symbol=symbol,
                    signal_type=signal_type,
                    entry_price=current_price,
                    stop_loss=stop_loss,
                    target_price=target,
                    confidence=confidence,
                    reason=reason
                )
                
                self._last_signals[symbol] = signal
                trading_logger.info(f"Generated BUY signal: {signal}")
                
            elif signal_type in [SignalType.SELL]:
                stop_loss = current_price * (1 + self.stop_loss_percent / 100)
                target = current_price * (1 - self.profit_target_percent / 100)
                
                signal = Signal(
                    symbol=symbol,
                    signal_type=signal_type,
                    entry_price=current_price,
                    stop_loss=stop_loss,
                    target_price=target,
                    reason=reason
                )
                
                self._last_signals[symbol] = signal
            
            return signal
        
        return None
    
    def _calculate_confidence(
        self,
        ema_values: dict,
        close_series: pd.Series,
        volumes: Optional[List[int]]
    ) -> float:
        """
        Calculate signal confidence.
        
        Args:
            ema_values: EMA values
            close_series: Close prices
            volumes: Volumes
        
        Returns:
            Confidence (0-100)
        """
        confidence = 50.0  # Base
        
        # EMA distance contribution (0-25)
        distance = abs(ema_values["distance"])
        confidence += min(distance * 5, 25)
        
        # Volume contribution (0-15)
        if volumes and len(volumes) >= self.volume_ma_period:
            vol_ma = sum(volumes[-self.volume_ma_period:]) / self.volume_ma_period
            if volumes[-1] > vol_ma:
                vol_ratio = volumes[-1] / vol_ma
                confidence += min(vol_ratio * 3, 15)
        
        # Recent momentum (0-10)
        if len(close_series) >= 5:
            recent_change = ((close_series.iloc[-1] - close_series.iloc[-5]) / close_series.iloc[-5]) * 100
            confidence += min(max(recent_change, 0), 10)
        
        return min(confidence, 100)
    
    def should_exit(
        self,
        symbol: str,
        entry_price: float,
        current_price: float,
        close_prices: List[float]
    ) -> Tuple[bool, str]:
        """
        Check if should exit position.
        
        Args:
            symbol: Trading symbol
            entry_price: Entry price
            current_price: Current price
            close_prices: Recent close prices
        
        Returns:
            Tuple of (should_exit, reason)
        """
        # Check profit target
        profit_percent = ((current_price - entry_price) / entry_price) * 100
        
        if profit_percent >= self.profit_target_percent:
            return True, f"Target Hit ({profit_percent:.2f}%)"
        
        # Check stop loss
        if profit_percent <= -self.stop_loss_percent:
            return True, f"Stop Loss Hit ({profit_percent:.2f}%)"
        
        # Check EMA death cross
        close_series = pd.Series(close_prices)
        
        if len(close_series) >= self.slow_ema_period:
            ema_values = calculate_ema_values(
                close_series,
                self.fast_ema_period,
                self.slow_ema_period
            )
            
            if ema_values["signal"] == "DEATH_CROSS":
                return True, "EMA Death Cross"
        
        return False, ""
    
    def get_last_signal(self, symbol: str) -> Optional[Signal]:
        """Get last signal for symbol"""
        return self._last_signals.get(symbol)
    
    def has_position(self, symbol: str) -> bool:
        """Check if has position"""
        return symbol in self._positions
    
    def open_position(self, symbol: str, entry_price: float) -> None:
        """Open position"""
        self._positions[symbol] = entry_price
        trading_logger.info(f"Position opened: {symbol} @ ₹{entry_price:.2f}")
    
    def close_position(self, symbol: str) -> None:
        """Close position"""
        if symbol in self._positions:
            del self._positions[symbol]
            trading_logger.info(f"Position closed: {symbol}")
    
    def get_positions(self) -> Dict[str, float]:
        """Get all open positions"""
        return self._positions.copy()


# ============================================================================
# STRATEGY FACTORY
# ============================================================================

def create_strategy(config: dict = None) -> EMACrossoverStrategy:
    """
    Create EMA crossover strategy.
    
    Args:
        config: Optional configuration
    
    Returns:
        EMACrossoverStrategy instance
    """
    if config is None:
        config = {}
    
    return EMACrossoverStrategy(
        fast_ema_period=config.get("fast_ema_period", 20),
        slow_ema_period=config.get("slow_ema_period", 50),
        volume_ma_period=config.get("volume_ma_period", 20),
        profit_target_percent=config.get("profit_target_percent", trading.PROFIT_TARGET_PERCENT),
        stop_loss_percent=config.get("stop_loss_percent", trading.STOP_LOSS_PERCENT),
        market_trend_check=config.get("market_trend_check", True)
    )


__all__ = [
    "SignalType",
    "Signal",
    "EMACrossoverStrategy",
    "create_strategy"
]