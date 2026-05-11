"""
Main Entry Point
===============
Main entry point for the swing trading bot.
Orchestrates all modules and handles initialization.
"""

import os
import sys
import signal
from datetime import datetime
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import trading, zerodha, validate_config, print_config_summary
from app.utils.logger import trading_logger, get_logger
from app.auth.zerodha_login import ZerodhaLogin
from app.auth.token_manager import get_access_token
from app.broker.zerodha_client import ZerodhaClient
from app.strategy.risk_manager import get_risk_manager
from app.scanner.scanner import StockScanner, ScannerConfig
from app.alerts.telegram_alert import get_telegram_bot
from app.database.database import get_database
from app.scheduler.scheduler import create_trading_scheduler


# ============================================================================
# TRADING MODES
# ============================================================================

class TradingMode:
    """Trading modes"""
    BACKTEST = "backtest"
    PAPER = "paper"
    LIVE = "live"


# ============================================================================
# TRADING BOT
# ============================================================================

class SwingTradingBot:
    """
    Main swing trading bot.
    Coordinates all trading components.
    """
    
    def __init__(self):
        """Initialize trading bot"""
        self.mode = trading.MODE
        self.running = False
        
        # Components
        self.client: Optional[ZerodhaClient] = None
        self.scanner: Optional[StockScanner] = None
        self.scheduler = create_trading_scheduler()
        self.risk_manager = None
        
        # Signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        trading_logger.warning(f"Received signal {signum}, shutting down...")
        self.shutdown()
        sys.exit(0)
    
    def initialize(self) -> None:
        """Initialize bot components"""
        trading_logger.info("Initializing Swing Trading Bot...")
        
        # Validate configuration
        errors = validate_config()
        if errors:
            trading_logger.error("Configuration errors detected:")
            for error in errors:
                trading_logger.error(f"  - {error}")
            trading_logger.warning("Continuing with limited functionality...")
        
        # Print config summary
        print_config_summary()
        
        # Initialize database
        if self.mode != TradingMode.BACKTEST:
            trading_logger.info("Initializing database...")
            db = get_database()
        
        # Test Telegram connection if enabled
        if self.mode in [TradingMode.PAPER, TradingMode.LIVE]:
            bot = get_telegram_bot()
            if bot.bot_token and bot.chat_id:
                bot.test_connection()
        
        # Initialize client for LIVE mode
        if self.mode == TradingMode.LIVE:
            trading_logger.info("Initializing Zerodha client...")
            
            try:
                # Try to get access token
                access_token = get_access_token()
                self.client = ZerodhaClient(access_token=access_token)
                
                # Validate connection
                profile = self.client.get_profile()
                trading_logger.info(f"Connected as: {profile.get('user_name', 'Unknown')}")
                
            except Exception as e:
                trading_logger.error(f"Failed to initialize client: {e}")
                trading_logger.warning("Proceeding in limited mode...")
        
        # Initialize scanner
        trading_logger.info("Initializing scanner...")
        scanner_config = ScannerConfig(
            symbols=trading.DEFAULT_WATCHLIST,
            scan_interval=trading.SCAN_INTERVAL_MINUTES
        )
        self.scanner = StockScanner(client=self.client, config=scanner_config)
        
        # Initialize risk manager
        self.risk_manager = get_risk_manager()
        self.scanner.set_risk_manager(self.risk_manager)
        
        # Setup scheduler jobs
        self._setup_scheduler_jobs()
        
        trading_logger.info("Initialization complete!")
    
    def _setup_scheduler_jobs(self) -> None:
        """Setup scheduler jobs"""
        if self.mode == TradingMode.LIVE:
            # Add scanner
            self.scheduler.set_scanner_function(self.run_scanner)
            
            # Add position monitor
            self.scheduler.set_monitor_function(self.monitor_positions)
            
            # Add end of day
            self.scheduler.set_end_of_day_function(self.end_of_day)
            
            # Add daily summary
            self.scheduler.set_daily_summary_function(self.send_daily_summary)
        
        elif self.mode == TradingMode.PAPER:
            # Add scanner
            self.scheduler.set_scanner_function(self.run_scanner)
            
            # Add daily summary
            self.scheduler.set_daily_summary_function(self.send_daily_summary)
        
        self.scheduler.setup_jobs()
    
    def start(self) -> None:
        """Start trading bot"""
        if self.running:
            trading_logger.warning("Bot already running")
            return
        
        trading_logger.info(f"Starting Swing Trading Bot in {self.mode.upper()} mode...")
        
        self.running = True
        
        if self.mode in [TradingMode.PAPER, TradingMode.LIVE]:
            # Start scheduler
            self.scheduler.start()
        else:
            trading_logger.info("Backtest mode - use run_backtest() method")
        
        trading_logger.info("Bot started successfully!")
    
    def shutdown(self) -> None:
        """Shutdown trading bot"""
        if not self.running:
            return
        
        trading_logger.info("Shutting down trading bot...")
        
        # Stop scheduler
        if self.scheduler.scheduler.is_running():
            self.scheduler.shutdown()
        
        self.running = False
        trading_logger.info("Bot shutdown complete")
    
    def run_scanner(self) -> None:
        """Run stock scanner"""
        if not self.scanner:
            trading_logger.warning("Scanner not initialized")
            return
        
        trading_logger.info("Running scanner...")
        
        try:
            # Scan all symbols
            results = self.scanner.scan_all()
            
            # Get buy signals
            buy_signals = self.scanner.get_buy_signals()
            
            if buy_signals:
                trading_logger.info(f"Found {len(buy_signals)} buy signals")
                
                # Process based on mode
                if self.mode == TradingMode.PAPER:
                    from app.paper_trading.paper_engine import PaperTradingEngine
                    self._process_paper_signals(buy_signals)
                
                elif self.mode == TradingMode.LIVE:
                    self._process_live_signals(buy_signals)
            
        except Exception as e:
            trading_logger.error(f"Scanner error: {e}")
    
    def _process_paper_signals(self, signals) -> None:
        """Process signals in paper trading mode"""
        from app.paper_trading.paper_engine import PaperTradingEngine
        
        engine = PaperTradingEngine(
            initial_capital=trading.INITIAL_CAPITAL,
            strategy=self.scanner.strategy
        )
        
        for result in signals:
            if not result.signal:
                continue
            
            engine.process_scan_result(result)
    
    def _process_live_signals(self, signals) -> None:
        """Process signals in live trading mode"""
        from app.live_trading.trade_executor import LiveTradingEngine
        
        engine = LiveTradingEngine(
            initial_capital=trading.INITIAL_CAPITAL,
            client=self.client,
            strategy=self.scanner.strategy
        )
        
        for result in signals:
            if not result.signal:
                continue
            
            engine.process_scan_result(result)
    
    def monitor_positions(self) -> None:
        """Monitor open positions"""
        if not self.client:
            return
        
        try:
            positions = self.client.get_open_positions()
            
            for position in positions:
                if position.quantity == 0:
                    continue
                
                quote = self.client.get_quote(position.trading_symbol)
                current_price = quote.last_price
                
                # Check exits
                should_exit, reason = self.scanner.strategy.should_exit(
                    symbol=position.trading_symbol,
                    entry_price=position.average_price,
                    current_price=current_price,
                    close_prices=[position.average_price, current_price]
                )
                
                if should_exit:
                    trading_logger.info(f"Exit signal: {position.trading_symbol} - {reason}")
                    # Execute exit in live mode
        except Exception as e:
            trading_logger.error(f"Position monitor error: {e}")
    
    def end_of_day(self) -> None:
        """End of day processing"""
        trading_logger.info("End of day processing...")
        
        if self.mode == TradingMode.LIVE:
            # Close any open positions at market close
            try:
                positions = self.client.get_open_positions()
                
                for position in positions:
                    if position.quantity > 0:
                        # Place market sell order
                        self.client.sell_order(
                            symbol=position.trading_symbol,
                            quantity=abs(position.quantity)
                        )
                        
                        trading_logger.info(f"Closed position: {position.trading_symbol}")
            except Exception as e:
                trading_logger.error(f"End of day error: {e}")
    
    def send_daily_summary(self) -> None:
        """Send daily summary"""
        try:
            bot = get_telegram_bot()
            
            # Get P&L
            capital = trading.INITIAL_CAPITAL
            trades_today = 0
            pnl = 0.0
            open_positions = 0
            
            if self.mode == TradingMode.LIVE and self.client:
                positions = self.client.get_positions()
                for pos in positions:
                    if pos.quantity != 0:
                        pnl += pos.pnl
                        open_positions += 1
                trades_today = len(positions)
            
            pnl_percent = (pnl / capital) * 100 if capital > 0 else 0
            
            bot.send_daily_summary(
                date=datetime.now().strftime("%Y-%m-%d"),
                trades=trades_today,
                pnl=pnl,
                pnl_percent=pnl_percent,
                capital=capital,
                open_positions=open_positions
            )
            
        except Exception as e:
            trading_logger.error(f"Daily summary error: {e}")
    
    def run_backtest(self, data: dict) -> None:
        """Run backtest"""
        if self.mode != TradingMode.BACKTEST:
            trading_logger.warning("Not in backtest mode")
            return
        
        from app.backtesting.backtester import BacktestEngine
        
        engine = BacktestEngine()
        
        trading_logger.info("Starting backtest...")
        metrics = engine.run_backtest(data)
        
        trading_logger.info("Backtest complete!")
        engine.print_metrics()
        
        # Export reports
        reports_dir = Path(__file__).parent.parent / "reports"
        reports_dir.mkdir(exist_ok=True)
        
        engine.export_trades(reports_dir / "trade_history.csv")
        engine.export_equity_curve(reports_dir / "equity_curve.csv")


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main entry point"""
    # Create and initialize bot
    bot = SwingTradingBot()
    bot.initialize()
    
    # Start bot
    bot.start()


if __name__ == "__main__":
    main()