# Swing Trading Bot

## Automated Swing Trading System for Indian Stock Markets

A production-ready, modular algorithmic trading platform for Indian stock markets using Zerodha Kite Connect API. Features backtesting, paper trading, live trading, and Telegram alerts.

## Table of Contents

1. [Features](#features)
2. [Project Structure](#project-structure)
3. [Prerequisites](#prerequisites)
4. [Installation](#installation)
5. [Configuration](#configuration)
6. [Zerodha Setup](#zerodha-setup)
7. [Telegram Bot Setup](#telegram-bot-setup)
8. [Usage](#usage)
9. [Strategy](#strategy)
10. [Risk Management](#risk-management)
11. [Deployment](#deployment)
12. [Troubleshooting](#troubleshooting)

## Features

- **Backtesting**: Test strategies on historical data with realistic simulation
- **Paper Trading**: Test strategies with simulated money
- **Live Trading**: Execute real trades on Zerodha
- **Telegram Alerts**: Get notified of signals, orders, and daily summaries
- **Automated Login**: Auto TOTP generation with Playwright
- **Risk Management**: Position sizing, stop loss, and daily limits
- **Modular Design**: Easy to extend and customize

## Project Structure

```
trading_bot/
├── app/
│   ├── auth/           # Authentication & token management
│   ├── broker/         # Broker connection (Zerodha)
│   ├── strategy/       # Trading strategies
│   ├── scanner/        # Stock scanner
│   ├── backtesting/    # Backtesting engine
│   ├── paper_trading/  # Paper trading engine
│   ├── live_trading/  # Live trading engine
│   ├── alerts/        # Telegram alerts
│   ├── database/      # Database layer
│   ├── scheduler/      # Task scheduler
│   ├── utils/         # Utilities
│   └── config.py       # Configuration
├── logs/              # Log files
├── reports/           # Backtest reports
├── tests/             # Tests
├── data/              # Data & tokens
├── main.py            # Entry point
├── requirements.txt    # Dependencies
└── .env.example      # Configuration template
```

## Prerequisites

- Python 3.12+
- Zerodha Account (Kite Connect)
- Telegram Account

## Installation

### 1. Clone and Navigate

```bash
git clone <repository-url>
cd trading_bot
```

### 2. Create Virtual Environment

```bash
# Linux/Mac
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Install Playwright

```bash
playwright install chromium
```

### 5. Configure Environment

```bash
cp .env.example .env
# Edit .env with your credentials
```

## Configuration

All settings are in `.env`:

### Broker Settings
- `ZERODHA_API_KEY` - Get from https://developers.kite.trade
- `ZERODHA_API_SECRET` - Get from developer portal
- `ZERODHA_USER_ID` - Your Zerodha user ID
- `ZERODHA_PASSWORD` - Your Zerodha password
- `ZERODHA_TOTP_SECRET` - TOTP secret (see below)

### Trading Settings
- `TRADING_MODE` - 'backtest', 'paper', or 'live'
- `INITIAL_CAPITAL` - Starting capital (₹100000 default)
- `RISK_PER_TRADE_PERCENT` - 1% default

### Alerts
- `TELEGRAM_BOT_TOKEN` - From @BotFather
- `TELEGRAM_CHAT_ID` - From @userinfobot

## Zerodha Setup

### 1. Get API Key

1. Go to https://developers.kite.trade
2. Create app with 'Kite Connect' product
3. Note the API Key and Secret

### 2. Enable TOTP

1. Login to Kite
2. Go to Settings → Security
3. Enable Two-Factor Authentication
4. Generate TOTP secret
5. Copy the 32-character secret to `ZERODHA_TOTP_SECRET`

### 3. Auto-Login

The bot can auto-generate daily access tokens:
- Set `ZERODHA_AUTO_LOGIN=true`
- Enter credentials in `.env`

## Telegram Bot Setup

### 1. Create Bot

1. Open @BotFather on Telegram
2. Send `/newbot`
3. Follow instructions
4. Copy bot token to `TELEGRAM_BOT_TOKEN`

### 2. Get Chat ID

1. Open @userinfobot on Telegram
2. Send `/start`
3. Copy your chat ID to `TELEGRAM_CHAT_ID`

### 3. Test

```bash
python -c "from app.alerts.telegram_alert import get_telegram_bot; get_telegram_bot().test_connection()"
```

## Usage

### Start Trading

```bash
python main.py
```

### Run Backtest

```python
from app.backtesting.backtester import BacktestEngine
from app.strategy.ema_strategy import EMACrossoverStrategy
import pandas as pd

# Load your historical data
data = {
    'RELIANCE': pd.read_csv('reliance.csv'),
    'INFY': pd.read_csv('infy.csv'),
    # ... more symbols
}

# Run backtest
engine = BacktestEngine()
metrics = engine.run_backtest(data)

# Export results
engine.export_trades('reports/trade_history.csv')
```

### Paper Trading

Set in `.env`:
```
TRADING_MODE=paper
```

Then run `python main.py`

### Live Trading

Set in `.env`:
```
TRADING_MODE=live
```

Then run `python main.py`

## Strategy

### EMA Crossover Strategy

**Buy Conditions:**
1. 20 EMA crosses above 50 EMA (Golden Cross)
2. Price closes above both EMAs
3. Volume > 20-day average
4. Market trend bullish (Nifty 50)

**Sell Conditions:**
1. Profit target 3-5%
2. Stop loss 2%
3. 20 EMA crosses below 50 EMA (Death Cross)

## Risk Management

- **Per Trade Risk**: 1% max
- **Max Concurrent Trades**: 3
- **Daily Loss Limit**: 2%
- **Max Consecutive Losses**: 3 (auto-stop)
- **Trade Cooldown**: 15 minutes

## Deployment

### Linux/WSL

```bash
# Create startup script
echo 'cd /path/to/trading_bot && source venv/bin/activate && python main.py >> logs/trading.log 2>&1 &'

# Add to cron for daily startup
crontab -e
# Add: 0 9 * * 1-5 /path/to/start_trading.sh
```

### Docker

```bash
# Build image
docker build -t swingbot .

# Run container
docker-compose up -d

# View logs
docker-compose logs -f
```

## Troubleshooting

### Common Issues

**1. TOTP Not Working**
- Ensure TOTP secret is correct (32 characters)
- Check system time is accurate

**2. Login Failed**
- Verify API credentials
- Check internet connection

**3. Orders Not Executing**
- Check balance
- Check market hours
- Check kill switch status

**4. Database Errors**
- For SQLite: Check data directory permissions
- For PostgreSQL: Verify connection settings

### Logs

Check `logs/` directory for detailed logs:
- `trading_bot.log` - Main logs
- `errors.log` - Error logs
- `trades.log` - Trade execution logs

## License

MIT License

## Disclaimer

This is for educational purposes. Trading involves risk. Use at your own risk.
# Setup - run once after install
playwright install chromium

