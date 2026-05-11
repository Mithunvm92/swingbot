"""
Technical Indicators Module
=========================
Technical analysis indicators for trading strategies.
Uses pandas and ta library for calculations.
"""

import numpy as np
import pandas as pd
from typing import List, Tuple, Optional
from dataclasses import dataclass

from app.utils.logger import trading_logger


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class IndicatorValues:
    """Technical indicator values"""
    name: str
    value: float
    previous: float = 0.0
    signal: str = ""  # "BUY", "SELL", "NEUTRAL"
    
    @property
    def bullish(self) -> bool:
        """Check if indicator is bullish"""
        return self.signal == "BUY"
    
    @property
    def bearish(self) -> bool:
        """Check if indicator is bearish"""
        return self.signal == "SELL"


# ============================================================================
# INDICATOR CALCULATIONS
# ============================================================================

def calculate_sma(data: pd.Series, period: int) -> pd.Series:
    """
    Calculate Simple Moving Average.
    
    Args:
        data: Price series
        period: Period for SMA
    
    Returns:
        SMA series
    """
    return data.rolling(window=period).mean()


def calculate_ema(data: pd.Series, period: int) -> pd.Series:
    """
    Calculate Exponential Moving Average.
    
    Args:
        data: Price series
        period: Period for EMA
    
    Returns:
        EMA series
    """
    return data.ewm(span=period, adjust=False).mean()


def calculate_rsi(data: pd.Series, period: int = 14) -> pd.Series:
    """
    Calculate Relative Strength Index.
    
    Args:
        data: Price series
        period: RSI period (default: 14)
    
    Returns:
        RSI series
    """
    delta = data.diff()
    
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    
    return rsi


def calculate_macd(
    data: pd.Series,
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    Calculate MACD (Moving Average Convergence Divergence).
    
    Args:
        data: Price series
        fast_period: Fast EMA period
        slow_period: Slow EMA period
        signal_period: Signal line period
    
    Returns:
        Tuple of (MACD line, Signal line, Histogram)
    """
    ema_fast = calculate_ema(data, fast_period)
    ema_slow = calculate_ema(data, slow_period)
    
    macd_line = ema_fast - ema_slow
    signal_line = calculate_ema(macd_line, signal_period)
    histogram = macd_line - signal_line
    
    return macd_line, signal_line, histogram


def calculate_bollinger_bands(
    data: pd.Series,
    period: int = 20,
    std_dev: float = 2.0
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    Calculate Bollinger Bands.
    
    Args:
        data: Price series
        period: Period for calculation
        std_dev: Standard deviation multiplier
    
    Returns:
        Tuple of (Upper band, Middle band, Lower band)
    """
    middle = calculate_sma(data, period)
    std = data.rolling(window=period).std()
    
    upper = middle + (std_dev * std)
    lower = middle - (std_dev * std)
    
    return upper, middle, lower


def calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """
    Calculate Average True Range.
    
    Args:
        high: High prices
        low: Low prices
        close: Close prices
        period: ATR period
    
    Returns:
        ATR series
    """
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    
    return atr


def calculate_adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """
    Calculate Average Directional Index.
    
    Args:
        high: High prices
        low: Low prices
        close: Close prices
        period: ADX period
    
    Returns:
        ADX series
    """
    plus_dm = high.diff()
    minus_dm = -low.diff()
    
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm < 0] = 0
    
    atr = calculate_atr(high, low, close, period)
    
    plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr)
    
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    adx = dx.rolling(window=period).mean()
    
    return adx


def calculate_volume_ma(data: pd.Series, period: int = 20) -> pd.Series:
    """
    Calculate Volume Moving Average.
    
    Args:
        data: Volume series
        period: Period for MA
    
    Returns:
        Volume MA series
    """
    return data.rolling(window=period).mean()


def calculate_stochastic(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    k_period: int = 14,
    d_period: int = 3
) -> Tuple[pd.Series, pd.Series]:
    """
    Calculate Stochastic Oscillator.
    
    Args:
        high: High prices
        low: Low prices
        close: Close prices
        k_period: K period
        d_period: D period
    
    Returns:
        Tuple of (%K, %D)
    """
    lowest_low = low.rolling(window=k_period).min()
    highest_high = high.rolling(window=k_period).max()
    
    k = 100 * (close - lowest_low) / (highest_high - lowest_low)
    d = k.rolling(window=d_period).mean()
    
    return k, d


# ============================================================================
# EMA CROSSOVER SIGNALS
# ============================================================================

def detect_ema_crossover(
    data: pd.Series,
    fast_period: int = 20,
    slow_period: int = 50
) -> Tuple[str, float, float]:
    """
    Detect EMA crossover.
    
    Args:
        data: Price series
        fast_period: Fast EMA period
        slow_period: Slow EMA period
    
    Returns:
        Tuple of (signal, fast_ema, slow_ema)
    """
    fast_ema = calculate_ema(data, fast_period).iloc[-1]
    slow_ema = calculate_ema(data, slow_period).iloc[-1]
    
    # Get previous values
    if len(data) >= 2:
        fast_ema_prev = calculate_ema(data[:-1], fast_period).iloc[-1]
        slow_ema_prev = calculate_ema(data[:-1], slow_period).iloc[-1]
    else:
        fast_ema_prev = fast_ema
        slow_ema_prev = slow_ema
    
    # Detect crossover
    if fast_ema_prev < slow_ema_prev and fast_ema > slow_ema:
        return "BUY", fast_ema, slow_ema
    elif fast_ema_prev > slow_ema_prev and fast_ema < slow_ema:
        return "SELL", fast_ema, slow_ema
    else:
        return "NEUTRAL", fast_ema, slow_ema


def calculate_ema_values(
    data: pd.Series,
    fast_period: int = 20,
    slow_period: int = 50
) -> dict:
    """
    Calculate EMA values with signals.
    
    Args:
        data: Price series
        fast_period: Fast EMA period
        slow_period: Slow EMA period
    
    Returns:
        Dictionary with EMA values and signals
    """
    fast_ema = calculate_ema(data, fast_period)
    slow_ema = calculate_ema(data, slow_period)
    
    current_fast = fast_ema.iloc[-1]
    current_slow = slow_ema.iloc[-1]
    
    prev_fast = fast_ema.iloc[-2] if len(fast_ema) >= 2 else current_fast
    prev_slow = slow_ema.iloc[-2] if len(slow_ema) >= 2 else current_slow
    
    # Calculate signal
    if prev_fast < prev_slow and current_fast > current_slow:
        signal = "GOLDEN_CROSS"  # Bullish crossover
    elif prev_fast > prev_slow and current_fast < current_slow:
        signal = "DEATH_CROSS"  # Bearish crossover
    elif current_fast > current_slow:
        signal = "BULLISH"  # Fast above slow
    elif current_fast < current_slow:
        signal = "BEARISH"  # Fast below slow
    else:
        signal = "NEUTRAL"
    
    return {
        "fast_ema": current_fast,
        "slow_ema": current_slow,
        "fast_ema_prev": prev_fast,
        "slow_ema_prev": prev_slow,
        "signal": signal,
        "distance": ((current_fast - current_slow) / current_slow) * 100
    }


# ============================================================================
# TREND ANALYSIS
# ============================================================================

def analyze_trend(data: pd.Series, period: int = 20) -> str:
    """
    Analyze price trend.
    
    Args:
        data: Price series
        period: Period for analysis
    
    Returns:
        Trend direction: "UP", "DOWN", "SIDEWAYS"
    """
    if len(data) < period:
        return "SIDEWAYS"
    
    recent = data.iloc[-period:]
    older = data.iloc[-period*2:-period] if len(data) >= period * 2 else data.iloc[:-period]
    
    if len(older) == 0:
        return "SIDEWAYS"
    
    # Calculate averages
    recent_avg = recent.mean()
    older_avg = older.mean()
    
    # Calculate slope
    from scipy import stats as scipy_stats
    x = np.arange(len(recent))
    slope, _, _, _, _ = scipy_stats.linregress(x, recent.values)
    
    # Determine trend
    percent_change = ((recent_avg - older_avg) / older_avg) * 100
    
    if slope > 0 and percent_change > 1:
        return "UP"
    elif slope < 0 and percent_change < -1:
        return "DOWN"
    else:
        return "SIDEWAYS"


def is_price_above_ema(data: pd.Series, period: int = 20) -> bool:
    """
    Check if current price is above EMA.
    
    Args:
        data: Price series
        period: EMA period
    
    Returns:
        True if price is above EMA
    """
    ema = calculate_ema(data, period).iloc[-1]
    current = data.iloc[-1]
    return current > ema


def is_volume_above_average(volume: pd.Series, period: int = 20) -> bool:
    """
    Check if current volume is above average.
    
    Args:
        volume: Volume series
        period: Period for average
    
    Returns:
        True if volume is above average
    """
    vol_ma = calculate_volume_ma(volume, period)
    current_vol = volume.iloc[-1]
    avg_vol = vol_ma.iloc[-1]
    return current_vol > avg_vol


# ============================================================================
# SUPPORT/RESISTANCE
# ============================================================================

def find_support_resistance(
    data: pd.Series,
    lookback: int = 20
) -> Tuple[List[float], List[float]]:
    """
    Find support and resistance levels.
    
    Args:
        data: Price series
        lookback: Number of candles to look back
    
    Returns:
        Tuple of (support levels, resistance levels)
    """
    recent = data.iloc[-lookback:]
    
    # Identify local minima and maxima
    support = []
    resistance = []
    
    for i in range(1, len(recent) - 1):
        if recent.iloc[i] < recent.iloc[i-1] and recent.iloc[i] < recent.iloc[i+1]:
            support.append(recent.iloc[i])
        elif recent.iloc[i] > recent.iloc[i-1] and recent.iloc[i] > recent.iloc[i+1]:
            resistance.append(recent.iloc[i])
    
    return support, resistance


# ============================================================================
# INDICATOR CALCULATOR CLASS
# ============================================================================

class IndicatorCalculator:
    """
    Comprehensive indicator calculator.
    Calculates all indicators for a given dataset.
    """
    
    def __init__(self):
        """Initialize calculator"""
        self.data: Optional[pd.DataFrame] = None
    
    def set_data(
        self,
        close: List[float],
        high: Optional[List[float]] = None,
        low: Optional[List[float]] = None,
        volume: Optional[List[int]] = None
    ) -> None:
        """
        Set price data.
        
        Args:
            close: Close prices
            high: High prices (optional)
            low: Low prices (optional)
            volume: Volume (optional)
        """
        self.data = pd.DataFrame({
            "close": close,
            "high": high or close,
            "low": low or close,
            "volume": volume or [0] * len(close)
        })
    
    def get_ema_20(self) -> float:
        """Get 20-period EMA"""
        return calculate_ema(self.data["close"], 20).iloc[-1]
    
    def get_ema_50(self) -> float:
        """Get 50-period EMA"""
        return calculate_ema(self.data["close"], 50).iloc[-1]
    
    def get_rsi(self, period: int = 14) -> float:
        """Get RSI"""
        return calculate_rsi(self.data["close"], period).iloc[-1]
    
    def get_macd(self) -> Tuple[float, float, float]:
        """Get MACD values"""
        macd, signal, hist = calculate_macd(self.data["close"])
        return macd.iloc[-1], signal.iloc[-1], hist.iloc[-1]
    
    def get_bollinger(self) -> Tuple[float, float, float]:
        """Get Bollinger Bands"""
        upper, middle, lower = calculate_bollinger_bands(self.data["close"])
        return upper.iloc[-1], middle.iloc[-1], lower.iloc[-1]
    
    def get_atr(self, period: int = 14) -> float:
        """Get ATR"""
        return calculate_atr(
            self.data["high"],
            self.data["low"],
            self.data["close"],
            period
        ).iloc[-1]
    
    def get_volume_ma(self, period: int = 20) -> float:
        """Get Volume MA"""
        return calculate_volume_ma(self.data["volume"], period).iloc[-1]
    
    def analyze_all(self) -> dict:
        """
        Calculate all indicators.
        
        Returns:
            Dictionary of all indicator values
        """
        close = self.data["close"]
        high = self.data["high"]
        low = self.data["low"]
        volume = self.data["volume"]
        
        # EMA
        ema_20 = calculate_ema(close, 20).iloc[-1]
        ema_50 = calculate_ema(close, 50).iloc[-1]
        ema_20_prev = calculate_ema(close[:-1], 20).iloc[-1] if len(close) > 1 else ema_20
        ema_50_prev = calculate_ema(close[:-1], 50).iloc[-1] if len(close) > 1 else ema_50
        
        if ema_20_prev < ema_50_prev and ema_20 > ema_50:
            ema_signal = "GOLDEN_CROSS"
        elif ema_20_prev > ema_50_prev and ema_20 < ema_50:
            ema_signal = "DEATH_CROSS"
        elif ema_20 > ema_50:
            ema_signal = "BULLISH"
        elif ema_20 < ema_50:
            ema_signal = "BEARISH"
        else:
            ema_signal = "NEUTRAL"
        
        # RSI
        rsi = calculate_rsi(close, 14).iloc[-1]
        
        # MACD
        macd_line, signal_line, histogram = calculate_macd(close)
        macd = macd_line.iloc[-1]
        macd_signal = signal_line.iloc[-1]
        macd_hist = histogram.iloc[-1]
        
        # Bollinger
        bb_upper, bb_middle, bb_lower = calculate_bollinger_bands(close)
        
        # ATR
        atr = calculate_atr(high, low, close, 14).iloc[-1]
        
        # Volume
        vol_ma = calculate_volume_ma(volume, 20).iloc[-1]
        current_vol = volume.iloc[-1]
        
        # Support/Resistance
        support, resistance = find_support_resistance(close)
        
        return {
            "ema_20": ema_20,
            "ema_50": ema_50,
            "ema_signal": ema_signal,
            "rsi": rsi,
            "macd": macd,
            "macd_signal": macd_signal,
            "macd_hist": macd_hist,
            "bb_upper": bb_upper.iloc[-1],
            "bb_middle": bb_middle.iloc[-1],
            "bb_lower": bb_lower.iloc[-1],
            "atr": atr,
            "volume": current_vol,
            "volume_ma": vol_ma,
            "volume_ratio": current_vol / vol_ma if vol_ma > 0 else 0,
            "support": support[-3:] if support else [],
            "resistance": resistance[-3:] if resistance else [],
            "close": close.iloc[-1],
            "high": high.iloc[-1],
            "low": low.iloc[-1]
        }


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

__all__ = [
    "IndicatorValues",
    "calculate_sma",
    "calculate_ema",
    "calculate_rsi",
    "calculate_macd",
    "calculate_bollinger_bands",
    "calculate_atr",
    "calculate_adx",
    "calculate_volume_ma",
    "calculate_stochastic",
    "detect_ema_crossover",
    "calculate_ema_values",
    "analyze_trend",
    "is_price_above_ema",
    "is_volume_above_average",
    "find_support_resistance",
    "IndicatorCalculator"
]