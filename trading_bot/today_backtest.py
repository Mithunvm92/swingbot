#!/usr/bin/env python3
"""
Today's Backtest - With historical data
"""
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.config import trading
from app.scanner.scanner import StockScanner, ScannerConfig
from app.broker.zerodha_client import ZerodhaClient

# Use 'day' candle for backtesting (works even when market closed)
BACKTEST_INTERVAL = "day"

print("=" * 60)
print(f"TODAY'S BACKTEST - Using {BACKTEST_INTERVAL} candles")
print("=" * 60)

scanner = StockScanner(config=ScannerConfig())
client = ZerodhaClient()

results = []
for symbol in scanner.config.symbols[:20]:
    try:
        df = client.get_historical(symbol, BACKTEST_INTERVAL, 30)
        if len(df) < 20:
            continue
        
        # Calculate EMAs on historical data
        df['ema20'] = df['close'].ewm(span=20).mean()
        df['ema50'] = df['close'].ewm(span=50).mean()
        
        # Check crossover
        if df['ema20'].iloc[-1] > df['ema50'].iloc[-1]:
            if df['ema20'].iloc[-2] <= df['ema50'].iloc[-2]:
                results.append({"symbol": symbol, "signal": "BUY", "price": df['close'].iloc[-1]})
    except Exception as e:
        pass

print(f"
Scanned {len(scanner.config.symbols)} stocks")
print("-" * 60)
if results:
    for r in results:
        print(f"  {r['symbol']}: {r['signal']} @ ₹{r['price']:.2f}")
else:
    print("  No BUY signals")
print("=" * 60)
