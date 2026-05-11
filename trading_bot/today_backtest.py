#!/usr/bin/env python3
"""
Today's Backtest - Scan all stocks for today's signals
Run: python3 today_backtest.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os; from dotenv import load_dotenv; load_dotenv(); os.environ.setdefault("SCAN_TIMEFRAME", "15minute"); from app.config import trading
from app.scanner.scanner import StockScanner, ScannerConfig
from datetime import datetime

# Get today's date
today = datetime.now().strftime("%Y-%m-%d")

print("=" * 60)
print(f"TODAY'S BACKTEST SCAN - {today}")
import os; from dotenv import load_dotenv; load_dotenv(); os.environ.setdefault("SCAN_TIMEFRAME", "15minute"); from app.config import trading; print(f"Timeframe: {trading.SCAN_TIMEFRAME}")
print("=" * 60)

# Initialize scanner
scanner = StockScanner(config=ScannerConfig())

results = []
errors = []

print(f"\nScanning {len(scanner.config.symbols)} stocks...")

for symbol in scanner.config.symbols:
    try:
        result = scanner.scan_symbol(symbol)
        if result.signal:
            price = result.quote.last_price if result.quote else 0
            results.append({
                "symbol": symbol,
                "signal": result.signal.signal_type,
                "confidence": result.signal.confidence,
                "price": price
            })
    except Exception as e:
        errors.append(f"{symbol}: {e}")

# Sort by confidence
results.sort(key=lambda x: x["confidence"], reverse=True)

print("\n" + "-" * 60)
print("SIGNALS DETECTED")
print("-" * 60)

if results:
    for r in results:
        print(f"  {r['symbol']:12} | {r['signal']:4} | ₹{r['price']:8.2f} | {r['confidence']:5.1f}%")
else:
    print("  No signals detected in current 4-hour timeframe")

print("\n" + "-" * 60)
print(f"Total: {len(results)} signals | {len(errors)} errors")
print("=" * 60)