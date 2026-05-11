"""
Backtesting Engine Module
======================
Professional backtesting engine for strategy testing.
"""

import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import pandas as pd

from app.config import backtest
from app.strategy.ema_strategy import EMACrossoverStrategy, Signal
from app.strategy.indicators import calculate_ema, calculate_ema_values
from app.utils.logger import trading_logger
from app.utils.helpers import ensure_directory


# ============================================================================
# BACKTEST CONFIG
# ============================================================================

@dataclass
class BacktestConfig:
    """Backtesting configuration"""
    initial_capital: float = 100000.0
    start_date: str = "2023-01-01"
    end_date: str = "2024-12-31"
    commission_percent: float = 0.1
    slippage_percent: float = 0.05
    
    def __post_init__(self):
        """Load from config if not set"""
        if self.initial_capital == 100000.0:
            self.initial_capital = backtest.INITIAL_CAPITAL
        if self.start_date == "2023-01-01":
            self.start_date = backtest.START_DATE
        if self.end_date == "2024-12-31":
            self.end_date = backtest.END_DATE


# ============================================================================
# BACKTEST TRADE
# ============================================================================

@dataclass
class BacktestTrade:
    """Backtest trade record"""
    timestamp: datetime
    symbol: str
    trade_type: str  # BUY or SELL
    quantity: int
    price: float
    commission: float
    pnl: float = 0.0
    pnl_percent: float = 0.0
    exit_reason: str = ""


# ============================================================================
# BACKTEST METRICS
# ============================================================================

@dataclass
class BacktestMetrics:
    """Backtest performance metrics"""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    total_pnl: float = 0.0
    total_return: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    cagr: float = 0.0
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "Total Trades": self.total_trades,
            "Win Rate": f"{self.win_rate:.2f}%",
            "Total P&L": f"₹{self.total_pnl:,.2f}",
            "Total Return": f"{self.total_return:.2f}%",
            "Avg Win": f"₹{self.avg_win:,.2f}",
            "Avg Loss": f"₹{self.avg_loss:,.2f}",
            "Max Drawdown": f"{self.max_drawdown:.2f}%",
            "Sharpe Ratio": f"{self.sharpe_ratio:.2f}",
            "CAGR": f"{self.cagr:.2f}%"
        }


# ============================================================================
# BACKTEST ENGINE
# ============================================================================

class BacktestEngine:
    """
    Backtesting engine for EMA crossover strategy.
    Simulates trading with historical data.
    """
    
    def __init__(
        self,
        strategy: Optional[EMACrossoverStrategy] = None,
        config: Optional[BacktestConfig] = None
    ):
        """
        Initialize backtest engine.
        
        Args:
            strategy: Trading strategy
            config: Backtest configuration
        """
        self.strategy = strategy or EMACrossoverStrategy()
        self.config = config or BacktestConfig()
        
        self.capital = self.config.initial_capital
        self.initial_capital = self.config.initial_capital
        
        # Trade history
        self.trades: List[BacktestTrade] = []
        self.positions: Dict[str, dict] = {}  # symbol -> position data
        self.equity_curve: List[dict] = []
        
        # Metrics
        self.metrics = BacktestMetrics()
    
    def reset(self) -> None:
        """Reset backtest state"""
        self.capital = self.config.initial_capital
        self.initial_capital = self.config.initial_capital
        self.trades = []
        self.positions = {}
        self.equity_curve = []
        self.metrics = BacktestMetrics()
    
    def execute_buy(
        self,
        timestamp: datetime,
        symbol: str,
        price: float,
        quantity: int
    ) -> bool:
        """
        Execute buy in backtest.
        
        Args:
            timestamp: Trade timestamp
            symbol: Trading symbol
            price: Entry price
            quantity: Number of shares
        
        Returns:
            True if executed
        """
        # Apply slippage
        entry_price = price * (1 + self.config.slippage_percent / 100)
        
        # Calculate commission
        commission = entry_price * quantity * (self.config.commission_percent / 100)
        
        # Check capital
        total_cost = entry_price * quantity + commission
        if total_cost > self.capital:
            trading_logger.warning(f"Insufficient capital for {symbol}")
            return False
        
        # Execute buy
        self.capital -= total_cost
        
        # Record trade
        trade = BacktestTrade(
            timestamp=timestamp,
            symbol=symbol,
            trade_type="BUY",
            quantity=quantity,
            price=entry_price,
            commission=commission
        )
        self.trades.append(trade)
        
        # Record position
        self.positions[symbol] = {
            "entry_price": entry_price,
            "quantity": quantity,
            "entry_time": timestamp,
            "commission": commission
        }
        
        trading_logger.debug(f"Backtest BUY: {symbol} {quantity} @ ₹{entry_price:.2f}")
        return True
    
    def execute_sell(
        self,
        timestamp: datetime,
        symbol: str,
        price: float,
        exit_reason: str = ""
    ) -> bool:
        """
        Execute sell in backtest.
        
        Args:
            timestamp: Trade timestamp
            symbol: Trading symbol
            price: Exit price
            exit_reason: Exit reason (TARGET, SL, SIGNAL)
        
        Returns:
            True if executed
        """
        if symbol not in self.positions:
            return False
        
        # Apply slippage
        exit_price = price * (1 - self.config.slippage_percent / 100)
        
        position = self.positions[symbol]
        quantity = position["quantity"]
        entry_price = position["entry_price"]
        
        # Calculate P&L
        pnl = (exit_price - entry_price) * quantity
        pnl_percent = (pnl / (entry_price * quantity)) * 100
        
        # Add commission (both entry and exit)
        total_commission = position["commission"] + (exit_price * quantity * self.config.commission_percent / 100)
        pnl -= total_commission
        
        # Execute sell
        gross_proceeds = exit_price * quantity
        self.capital += gross_proceeds
        
        # Record trade
        trade = BacktestTrade(
            timestamp=timestamp,
            symbol=symbol,
            trade_type="SELL",
            quantity=quantity,
            price=exit_price,
            commission=total_commission,
            pnl=pnl,
            pnl_percent=pnl_percent,
            exit_reason=exit_reason
        )
        self.trades.append(trade)
        
        # Remove position
        del self.positions[symbol]
        
        trading_logger.debug(f"Backtest SELL: {symbol} {quantity} @ ₹{exit_price:.2f} | P&L: ₹{pnl:.2f} ({pnl_percent:.2f}%)")
        return True
    
    def check_exits(
        self,
        timestamp: datetime,
        symbol: str,
        current_price: float
    ) -> List[str]:
        """
        Check if should exit position.
        
        Args:
            timestamp: Current timestamp
            symbol: Trading symbol
            current_price: Current price
        
        Returns:
            List of exit reasons (empty if none)
        """
        if symbol not in self.positions:
            return []
        
        position = self.positions[symbol]
        entry_price = position["entry_price"]
        
        exits = []
        
        # Check stop loss (2%)
        if current_price <= entry_price * 0.98:
            exits.append("SL")
        
        # Check target (3-5%)
        if current_price >= entry_price * 1.05:
            exits.append("TARGET")
        
        return exits
    
    def run_backtest(
        self,
        data: Dict[str, pd.DataFrame],
        verbose: bool = True
    ) -> BacktestMetrics:
        """
        Run backtest on historical data.
        
        Args:
            data: Dictionary of symbol -> DataFrame with OHLCV data
            verbose: Print progress
        
        Returns:
            BacktestMetrics
        """
        if verbose:
            trading_logger.info(f"Starting backtest from {self.config.start_date} to {self.config.end_date}")
        
        # Process each symbol
        for symbol, df in data.items():
            if verbose:
                trading_logger.info(f"Backtesting {symbol}...")
            
            # Ensure required columns
            if "close" not in df.columns:
                continue
            
            # Convert dates
            df = df.copy()
            df["date"] = pd.to_datetime(df["date"])
            
            # Filter by date range
            df = df[
                (df["date"] >= self.config.start_date) &
                (df["date"] <= self.config.end_date)
            ]
            
            if len(df) < 60:
                continue
            
            # Run strategy on each candle
            close_prices = df["close"].tolist()
            high_prices = df["high"].tolist() if "high" in df.columns else close_prices
            low_prices = df["low"].tolist() if "low" in df.columns else close_prices
            volumes = df["volume"].tolist() if "volume" in df.columns else [0] * len(df)
            
            # Analyze each candle
            for i in range(50, len(close_prices)):
                timestamp = df["date"].iloc[i]
                current_price = close_prices[i]
                
                # Check exits first
                exits = self.check_exits(timestamp, symbol, current_price)
                
                for exit_reason in exits:
                    self.execute_sell(timestamp, symbol, current_price, exit_reason)
                
                # Skip if already in position
                if symbol in self.positions:
                    continue
                
                # Check for buy signal
                signal = self.strategy.analyze(
                    symbol=symbol,
                    close_prices=close_prices[:i+1],
                    high_prices=high_prices[:i+1],
                    low_prices=low_prices[:i+1],
                    volumes=volumes[:i+1]
                )
                
                if signal and signal.is_buy():
                    # Calculate position size
                    quantity = int(self.capital * 0.1 / current_price)
                    quantity = max(1, quantity)
                    
                    if self.execute_buy(timestamp, symbol, current_price, quantity):
                        # Open position in strategy
                        self.strategy.open_position(symbol, current_price)
        
        # Close any remaining positions at end
        if len(df) > 0:
            for symbol in list(self.positions.keys()):
                self.execute_sell(
                    df["date"].iloc[-1],
                    symbol,
                    close_prices[-1],
                    "END"
                )
        
        # Calculate metrics
        self.calculate_metrics()
        
        if verbose:
            self.print_metrics()
        
        return self.metrics
    
    def calculate_metrics(self) -> BacktestMetrics:
        """Calculate performance metrics"""
        # Filter completed trades
        closed_trades = [t for t in self.trades if t.trade_type == "SELL"]
        
        if not closed_trades:
            self.metrics = BacktestMetrics()
            return self.metrics
        
        # Basic metrics
        self.metrics.total_trades = len(closed_trades)
        self.metrics.winning_trades = sum(1 for t in closed_trades if t.pnl > 0)
        self.metrics.losing_trades = sum(1 for t in closed_trades if t.pnl <= 0)
        
        if self.metrics.total_trades > 0:
            self.metrics.win_rate = (self.metrics.winning_trades / self.metrics.total_trades) * 100
        
        self.metrics.total_pnl = sum(t.pnl for t in closed_trades)
        self.metrics.total_return = (self.metrics.total_pnl / self.initial_capital) * 100
        
        # Win/Loss
        wins = [t.pnl for t in closed_trades if t.pnl > 0]
        losses = [t.pnl for t in closed_trades if t.pnl <= 0]
        
        if wins:
            self.metrics.avg_win = sum(wins) / len(wins)
        if losses:
            self.metrics.avg_loss = sum(losses) / len(losses)
        
        # Drawdown
        equity = self.initial_capital
        max_equity = self.initial_capital
        self.metrics.max_drawdown = 0
        
        for trade in closed_trades:
            equity += trade.pnl
            if equity > max_equity:
                max_equity = equity
            drawdown = (max_equity - equity) / max_equity * 100
            if drawdown > self.metrics.max_drawdown:
                self.metrics.max_drawdown = drawdown
        
        # Sharpe Ratio (simplified)
        if len(closed_trades) > 1:
            returns = [t.pnl_percent for t in closed_trades]
            import numpy as np
            std_return = np.std(returns)
            if std_return > 0:
                self.metrics.sharpe_ratio = (np.mean(returns) / std_return) * np.sqrt(252)
        
        # CAGR
        days = (datetime.now() - datetime.strptime(self.config.start_date, "%Y-%m-%d")).days
        if days > 0:
            years = days / 365
            if years > 0:
                self.metrics.cagr = ((self.capital / self.initial_capital) ** (1/years) - 1) * 100
        
        return self.metrics
    
    def print_metrics(self) -> None:
        """Print backtest metrics"""
        print("\n" + "=" * 60)
        print("BACKTEST RESULTS")
        print("=" * 60)
        print(f"Total Trades: {self.metrics.total_trades}")
        print(f"Win Rate: {self.metrics.win_rate:.2f}%")
        print(f"Total P&L: ₹{self.metrics.total_pnl:,.2f}")
        print(f"Total Return: {self.metrics.total_return:.2f}%")
        print(f"Average Win: ₹{self.metrics.avg_win:,.2f}")
        print(f"Average Loss: ₹{self.metrics.avg_loss:,.2f}")
        print(f"Max Drawdown: {self.metrics.max_drawdown:.2f}%")
        print(f"Sharpe Ratio: {self.metrics.sharpe_ratio:.2f}")
        print(f"CAGR: {self.metrics.cagr:.2f}%")
        print(f"Final Capital: ₹{self.capital:,.2f}")
        print("=" * 60)
    
    def export_trades(self, file_path: Path) -> None:
        """Export trades to CSV"""
        if not self.trades:
            return
        
        ensure_directory(file_path.parent)
        
        data = []
        for trade in self.trades:
            data.append({
                "timestamp": trade.timestamp,
                "symbol": trade.symbol,
                "type": trade.trade_type,
                "quantity": trade.quantity,
                "price": trade.price,
                "commission": trade.commission,
                "pnl": trade.pnl,
                "pnl_percent": trade.pnl_percent,
                "exit_reason": trade.exit_reason
            })
        
        df = pd.DataFrame(data)
        df.to_csv(file_path, index=False)
        
        trading_logger.info(f"Trades exported to {file_path}")
    
    def export_equity_curve(self, file_path: Path) -> None:
        """Export equity curve to CSV"""
        if not self.equity_curve:
            return
        
        ensure_directory(file_path.parent)
        
        df = pd.DataFrame(self.equity_curve)
        df.to_csv(file_path, index=False)
        
        trading_logger.info(f"Equity curve exported to {file_path}")


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def run_backtest(
    data: Dict[str, pd.DataFrame],
    initial_capital: float = 100000,
    start_date: str = "2023-01-01",
    end_date: str = "2024-12-31"
) -> BacktestMetrics:
    """
    Run backtest (convenience function).
    
    Args:
        data: Dictionary of symbol -> DataFrame
        initial_capital: Initial capital
        start_date: Start date
        end_date: End date
    
    Returns:
        BacktestMetrics
    """
    config = BacktestConfig(
        initial_capital=initial_capital,
        start_date=start_date,
        end_date=end_date
    )
    
    engine = BacktestEngine(config=config)
    return engine.run_backtest(data)


__all__ = [
    "BacktestConfig",
    "BacktestTrade",
    "BacktestMetrics",
    "BacktestEngine",
    "run_backtest"
]