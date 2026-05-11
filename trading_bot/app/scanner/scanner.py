"""
Stock Scanner Module
==================
Scanner for detecting trading signals in watchlist stocks.
"""

from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

from app.config import trading
from app.broker.zerodha_client import ZerodhaClient, Quote
from app.strategy.ema_strategy import EMACrossoverStrategy, Signal
from app.strategy.risk_manager import RiskManager, CooldownTracker
from app.utils.logger import trading_logger
from app.utils.helpers import is_market_open


# ============================================================================
# SCANNER CONFIG
# ============================================================================

@dataclass
class ScannerConfig:
    """Scanner configuration"""
    symbols: List[str] = field(default_factory=lambda: trading.DEFAULT_WATCHLIST)
    scan_interval: int = 15  # minutes
    intervals: List[str] = field(default_factory=lambda: ["15minute", "60minute"])  # Multiple timeframes
    min_confidence: float = 50.0  # minimum confidence for signals
    check_volume: bool = True
    check_market_trend: bool = True


# ============================================================================
# SCAN RESULT
# ============================================================================

@dataclass
class ScanResult:
    """Scan result for a single symbol"""
    symbol: str
    signal: Optional[Signal]
    quote: Optional[Quote]
    indicators: dict
    timestamp: datetime = field(default_factory=datetime.now)
    
    @property
    def has_signal(self) -> bool:
        """Check if has trading signal"""
        return self.signal is not None and self.signal.is_buy()
    
    @property
    def is_bullish(self) -> bool:
        """Check if bullish"""
        if self.indicators.get("ema_signal") in ["GOLDEN_CROSS", "BULLISH"]:
            return True
        return False


# ============================================================================
# SCANNER
# ============================================================================

class StockScanner:
    """
    Stock scanner for detecting trading opportunities.
    Scans watchlist stocks for EMA crossover signals.
    """
    
    def __init__(
        self,
        client: Optional[ZerodhaClient] = None,
        config: Optional[ScannerConfig] = None
    ):
        """
        Initialize scanner.
        
        Args:
            client: ZerodhaClient instance (optional for paper mode)
            config: Scanner configuration
        """
        self.client = client
        self.config = config or ScannerConfig()
        
        # Initialize components
        self.strategy = EMACrossoverStrategy()
        self.risk_manager = None  # Set externally
        self.cooldown = CooldownTracker(trading.TRADING_COOLDOWN_MINUTES)
        
        # Results history
        self._results: Dict[str, ScanResult] = {}
        self._last_scan: Optional[datetime] = None
    
    def set_risk_manager(self, risk_manager: RiskManager) -> None:
        """Set risk manager"""
        self.risk_manager = risk_manager
    
    def set_market_trend_checker(self, checker: Callable) -> None:
        """Set market trend checker"""
        self.strategy.set_market_trend_checker(checker)
    
    def scan_symbol(self, symbol: str) -> ScanResult:
        """
        Scan a single symbol.
        
        Args:
            symbol: Trading symbol
        
        Returns:
            ScanResult
        """
        # Check if client is available
        if self.client is None:
            return ScanResult(
                symbol=symbol,
                signal=None,
                quote=None,
                indicators={"error": "Broker not configured"}
            )
        
        try:
            # Get quote
            quote = self.client.get_quote(symbol)
            
            # Get historical data
            from datetime import timedelta
            to_date = datetime.now()
            from_date = to_date - timedelta(days=60)
            
            candles = self.client.get_ohlc(
                symbol=symbol,
                interval="60minute",
                from_date=from_date,
                to_date=to_date
            )
            
            if len(candles) < 50:
                trading_logger.warning(f"Insufficient data for {symbol}")
                return ScanResult(
                    symbol=symbol,
                    signal=None,
                    quote=quote,
                    indicators={"error": "Insufficient data"}
                )
            
            # Extract data
            close_prices = [c.close for c in candles]
            high_prices = [c.high for c in candles]
            low_prices = [c.low for c in candles]
            volumes = [c.volume for c in candles]
            
            # Analyze with strategy
            signal = self.strategy.analyze(
                symbol=symbol,
                close_prices=close_prices,
                high_prices=high_prices,
                low_prices=low_prices,
                volumes=volumes
            )
            
            # Get indicators
            from app.strategy.indicators import IndicatorCalculator
            calc = IndicatorCalculator()
            calc.set_data(close_prices, high_prices, low_prices, volumes)
            indicators = calc.analyze_all()
            
            # Filter by confidence
            if signal and signal.confidence < self.config.min_confidence:
                signal = None
            
            result = ScanResult(
                symbol=symbol,
                signal=signal,
                quote=quote,
                indicators=indicators
            )
            
            self._results[symbol] = result
            return result
            
        except Exception as e:
            trading_logger.error(f"Error scanning {symbol}: {e}")
            return ScanResult(
                symbol=symbol,
                signal=None,
                quote=None,
                indicators={"error": str(e)}
            )
    
    def scan_all(self) -> List[ScanResult]:
        """
        Scan all symbols in watchlist.
        
        Returns:
            List of ScanResults
        """
        if not is_market_open():
            trading_logger.warning("Market is closed, skipping scan")
            return []
        
        trading_logger.info(f"Scanning {len(self.config.symbols)} symbols...")
        
        results = []
        
        # Scan in parallel for speed
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(self.scan_symbol, symbol): symbol
                for symbol in self.config.symbols
            }
            
            for future in as_completed(futures):
                symbol = futures[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    trading_logger.error(f"Error in scan: {e}")
        
        self._last_scan = datetime.now()
        
        # Get buy signals
        buy_signals = [r for r in results if r.has_signal]
        
        trading_logger.info(
            f"Scan complete: {len(buy_signals)} BUY signals from {len(results)} stocks"
        )
        
        return results
    
    def get_buy_signals(self) -> List[ScanResult]:
        """
        Get all buy signals from last scan.
        
        Returns:
            List of ScanResults with buy signals
        """
        return [r for r in self._results.values() if r.has_signal]
    
    def get_sell_signals(self) -> List[ScanResult]:
        """
        Get all sell signals from last scan.
        
        Returns:
            List of ScanResults with sell signals
        """
        return [r for r in self._results.values() if r.signal and r.signal.is_sell()]
    
    def get_results(self) -> Dict[str, ScanResult]:
        """Get all scan results"""
        return self._results.copy()
    
    def get_last_result(self, symbol: str) -> Optional[ScanResult]:
        """Get last scan result for symbol"""
        return self._results.get(symbol)
    
    def filter_signals(
        self,
        results: List[ScanResult],
        min_confidence: float = 0,
        require_volume: bool = True
    ) -> List[ScanResult]:
        """
        Filter signals based on criteria.
        
        Args:
            results: Scan results
            min_confidence: Minimum confidence
            require_volume: Require volume above average
        
        Returns:
            Filtered results
        """
        filtered = []
        
        for result in results:
            if not result.has_signal:
                continue
            
            # Check confidence
            if result.signal and result.signal.confidence < min_confidence:
                continue
            
            # Check volume
            if require_volume:
                if result.indicators.get("volume_ratio", 0) < 1.0:
                    continue
            
            filtered.append(result)
        
        return filtered
    
    def can_trade(self, symbol: str) -> bool:
        """
        Check if can trade symbol.
        
        Args:
            symbol: Trading symbol
        
        Returns:
            True if can trade
        """
        # Check risk manager
        if self.risk_manager:
            can_trade, reason = self.risk_manager.can_trade(symbol)
            if not can_trade:
                trading_logger.warning(f"Cannot trade {symbol}: {reason}")
                return False
        
        # Check cooldown
        if not self.cooldown.can_trade(symbol):
            remaining = self.cooldown.get_cooldown_remaining(symbol)
            trading_logger.warning(f"{symbol} in cooldown: {remaining:.1f} min remaining")
            return False
        
        return True


# ============================================================================
# WATCHLIST MANAGER
# ============================================================================

class WatchlistManager:
    """Manages stock watchlists"""
    
    def __init__(self):
        """Initialize watchlist manager"""
        self._watchlists: Dict[str, List[str]] = {
            "default": trading.DEFAULT_WATCHLIST.copy(),
            "nifty50": trading.NIFTY_50_INSTRUMENTS.copy()
        }
        self._current_list = "default"
    
    def get_watchlist(self, name: Optional[str] = None) -> List[str]:
        """Get watchlist by name"""
        name = name or self._current_list
        return self._watchlists.get(name, self._watchlists["default"])
    
    def set_watchlist(self, name: str, symbols: List[str]) -> None:
        """Set watchlist"""
        self._watchlists[name] = symbols.copy()
    
    def add_symbol(self, symbol: str, watchlist: Optional[str] = None) -> None:
        """Add symbol to watchlist"""
        name = watchlist or self._current_list
        if name not in self._watchlists:
            self._watchlists[name] = []
        if symbol not in self._watchlists[name]:
            self._watchlists[name].append(symbol)
    
    def remove_symbol(self, symbol: str, watchlist: Optional[str] = None) -> None:
        """Remove symbol from watchlist"""
        name = watchlist or self._current_list
        if name in self._watchlists and symbol in self._watchlists[name]:
            self._watchlists[name].remove(symbol)
    
    def switch_watchlist(self, name: str) -> None:
        """Switch current watchlist"""
        if name in self._watchlists:
            self._current_list = name
    
    def get_all_watchlists(self) -> Dict[str, List[str]]:
        """Get all watchlists"""
        return self._watchlists.copy()


# ============================================================================
# SCANNER FACTORY
# ============================================================================

def create_scanner(config: dict = None) -> StockScanner:
    """
    Create stock scanner.
    
    Args:
        config: Optional configuration
    
    Returns:
        StockScanner instance
    """
    if config is None:
        config = {}
    
    scanner_config = ScannerConfig(
        symbols=config.get("symbols", trading.DEFAULT_WATCHLIST),
        scan_interval=config.get("scan_interval", trading.SCAN_INTERVAL_MINUTES),
        min_confidence=config.get("min_confidence", 50.0),
        check_volume=config.get("check_volume", True),
        check_market_trend=config.get("check_market_trend", True)
    )
    
    return StockScanner(config=scanner_config)


__all__ = [
    "ScannerConfig",
    "ScanResult",
    "StockScanner",
    "WatchlistManager",
    "create_scanner"
]