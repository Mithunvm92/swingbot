"""
Zerodha Client Module
=================
Broker connection implementation using Kite Connect API.
Provides methods for order execution, position tracking, and market data.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

import pandas as pd
from kiteconnect import KiteConnect
from kiteconnect import exceptions as KiteExceptions

from app.config import zerodha, trading
from app.auth.token_manager import get_access_token
from app.utils.logger import trading_logger
from app.utils.helpers import OrderError, DataError


# ============================================================================
# ORDER TYPES
# ============================================================================

class OrderType(Enum):
    """Order types"""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    SL = "SL"  # Stop Loss
    SLM = "SL-M"  # Stop Loss Market


class OrderProduct(Enum):
    """Order products"""
    CNC = "CNC"  # Cash and Carry (Delivery)
    MIS = "MIS"  # Intraday
    NRML = "NRML"  # Normal


class TransactionType(Enum):
    """Transaction types"""
    BUY = "BUY"
    SELL = "SELL"


class Variety(Enum):
    """Order varieties"""
    REGULAR = "regular"
    BO = "bo"  # Bracket Order
    CO = "co"  # Cover Order


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class Order:
    """Order information"""
    order_id: str
    trading_symbol: str
    exchange: str
    transaction_type: str
    quantity: int
    price: float
    order_type: str
    product: str
    status: str
    average_price: float = 0.0
    pending_quantity: int = 0
    filled_quantity: int = 0
    cancelled_quantity: int = 0
    placed_at: str = ""
    updated_at: str = ""
    
    def is_complete(self) -> bool:
        """Check if order is complete"""
        return self.status in ["COMPLETE", "FILLED"]
    
    def is_pending(self) -> bool:
        """Check if order is pending"""
        return self.status in ["OPEN", "PARTIALLY FILLED"]
    
    def is_cancelled(self) -> bool:
        """Check if order is cancelled"""
        return self.status in ["CANCELLED", "REJECTED"]


@dataclass
class Position:
    """Position information"""
    trading_symbol: str
    exchange: str
    quantity: int
    average_price: float
    last_price: float
    pnl: float
    m2m: float
    product: str
    realised: float = 0.0
    pending_quantity: int = 0
    
    @property
    def current_value(self) -> float:
        """Current position value"""
        return self.quantity * self.last_price
    
    @property
    def invested_value(self) -> float:
        """Invested value"""
        return self.quantity * self.average_price
    
    @property
    def pnl_percent(self) -> float:
        """PnL percentage"""
        if self.invested_value == 0:
            return 0.0
        return (self.pnl / self.invested_value) * 100
    
    def is_profitable(self) -> bool:
        """Check if position is profitable"""
        return self.pnl > 0


@dataclass
class Quote:
    """Quote information"""
    trading_symbol: str
    exchange: str
    last_price: float
    open: float
    high: float
    low: float
    close: float
    volume: int
    change: float = 0.0
    change_percent: float = 0.0
    
    @property
    def is_up(self) -> bool:
        """Check if price is up"""
        return self.change >= 0


@dataclass
class OHLC:
    """OHLC candlestick data"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int = 0


# ============================================================================
# ZERODHA CLIENT
# ============================================================================

class ZerodhaClient:
    """
    Zerodha Kite Connect API client.
    Provides methods for trading and market data.
    """
    
    def __init__(self, access_token: Optional[str] = None):
        """
        Initialize client.
        
        Args:
            access_token: Zerodha access token
        """
        self.api_key = zerodha.API_KEY
        
        # Initialize Kite session
        self.kite = KiteConnect(api_key=self.api_key)
        
        # Set access token
        if access_token is None:
            access_token = get_access_token()
        
        if access_token:
            self.kite.set_access_token(access_token)
        
        self._profile: Optional[Dict] = None
        self._margins: Optional[Dict] = None
        self._positions: List[Position] = []
    
    def _ensure_token(self) -> None:
        """Ensure access token is set"""
        if not self.kite.access_token:
            access_token = get_access_token()
            self.kite.set_access_token(access_token)
    
    # ========================================================================
    # PROFILE & MARGINS
    # ========================================================================
    
    
    def get_historical(self, symbol: str, interval: str = "day", days: int = 30) -> pd.DataFrame:
        """Get historical data as DataFrame."""
        ohlc_list = self.get_ohlc(symbol, interval, continuous=True)
        
        if not ohlc_list:
            return pd.DataFrame()
        
        # Convert to DataFrame
        data = []
        for o in ohlc_list:
            data.append({
                'date': o.timestamp,
                'open': o.open,
                'high': o.high,
                'low': o.low,
                'close': o.close,
                'volume': o.volume
            })
        
        df = pd.DataFrame(data)
        if not df.empty:
            df['date'] = pd.to_datetime(df['date'])
            df = df.set_index('date').sort_index()
        
        # Limit to requested days
        if len(df) > days:
            df = df.tail(days)
        
        return df


    def get_profile(self) -> Dict:
        """Get user profile"""
        self._ensure_token()
        
        if self._profile is None:
            self._profile = self.kite.profile()
            trading_logger.debug(f"Profile loaded: {self._profile.get('user_name')}")
        
        return self._profile
    
    def get_margins(self) -> Dict:
        """Get trading margins"""
        self._ensure_token()
        
        if self._margins is None:
            self._margins = self.kite.margins()
            trading_logger.debug("Margins loaded")
        
        return self._margins
    
    def get_balance(self) -> float:
        """Get available balance"""
        margins = self.get_margins()
        return margins.get("equity", {}).get("net", 0)
    
    # ========================================================================
    # INSTRUMENTS
    # ========================================================================
    
    def get_instrument_token(self, symbol: str, exchange: str = "NSE") -> int:
        """
        Get instrument token for a symbol.
        
        Args:
            symbol: Trading symbol
            exchange: Exchange name
        
        Returns:
            Instrument token
        """
        instruments = self.kite.instruments(exchange)
        
        for inst in instruments:
            if inst.get("tradingsymbol") == symbol:
                return inst.get("instrument_token")
        
        raise DataError(f"Instrument not found: {symbol}")
    
    def get_instrument_symbol(self, token: int, exchange: str = "NSE") -> str:
        """
        Get trading symbol for an instrument token.
        
        Args:
            instrument_token: Instrument token
            exchange: Exchange name
        
        Returns:
            Trading symbol
        """
        instruments = self.kite.instruments(exchange)
        
        for inst in instruments:
            if inst.get("instrument_token") == token:
                return inst.get("tradingsymbol")
        
        raise DataError(f"Instrument not found for token: {token}")
    
    def search_instruments(self, query: str) -> List[Dict]:
        """
        Search for instruments.
        
        Args:
            query: Search query
        
        Returns:
            List of matching instruments
        """
        return self.kite.search_instruments(query)
    
    # ========================================================================
    # QUOTES
    # ========================================================================
    
    def get_quote(self, symbol: str, exchange: str = "NSE") -> Quote:
        """
        Get quote for a symbol.
        
        Args:
            symbol: Trading symbol
            exchange: Exchange name
        
        Returns:
            Quote object
        """
        instrument = f"{exchange}:{symbol}"
        quotes = self.kite.quote(instrument)
        
        if instrument not in quotes:
            raise DataError(f"Quote not found: {symbol}")
        
        data = quotes[instrument]
        
        return Quote(
            trading_symbol=symbol,
            exchange=exchange,
            last_price=data.get("last_price", 0),
            open=data.get("ohlc", {}).get("open", 0),
            high=data.get("ohlc", {}).get("high", 0),
            low=data.get("ohlc", {}).get("low", 0),
            close=data.get("ohlc", {}).get("close", 0),
            volume=data.get("volume", 0),
            change=data.get("change", 0),
            change_percent=data.get("change", 0)
        )
    
    def get_quotes(self, symbols: List[str], exchange: str = "NSE") -> Dict[str, Quote]:
        """
        Get quotes for multiple symbols.
        
        Args:
            symbols: List of trading symbols
            exchange: Exchange name
        
        Returns:
            Dictionary of symbol -> Quote
        """
        instruments = [f"{exchange}:{s}" for s in symbols]
        quotes = self.kite.quote(instruments)
        
        result = {}
        for inst in instruments:
            symbol = inst.split(":")[1]
            if inst in quotes:
                data = quotes[inst]
                result[symbol] = Quote(
                    trading_symbol=symbol,
                    exchange=exchange,
                    last_price=data.get("last_price", 0),
                    open=data.get("ohlc", {}).get("open", 0),
                    high=data.get("ohlc", {}).get("high", 0),
                    low=data.get("ohlc", {}).get("low", 0),
                    close=data.get("ohlc", {}).get("close", 0),
                    volume=data.get("volume", 0),
                    change=data.get("change", 0),
                    change_percent=data.get("change", 0)
                )
        
        return result
    
    # ========================================================================
    # HISTORICAL DATA
    # ========================================================================
    
    def get_ohlc(
        self,
        symbol: str,
        interval: str = "15minute",
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        continuous: bool = False
    ) -> List[OHLC]:
        """
        Get OHLC historical data.
        
        Args:
            symbol: Trading symbol
            interval: Time interval (minute, 15minute, day, etc.)
            from_date: Start date
            to_date: End date
            continuous: Use continuous data for F&O
        
        Returns:
            List of OHLC candles
        """
        self._ensure_token()
        
        instrument = f"NSE:{symbol}"
        
        # Default dates if not provided
        if from_date is None:
            from_date = datetime.now().replace(hour=9, minute=15, second=0)
        if to_date is None:
            to_date = datetime.now()
        
        try:
            data = self.kite.ohlc(
                instrument=instrument,
                interval=interval,
                from_date=from_date.isoformat(),
                to_date=to_date.isoformat(),
                continuous=continuous
            )
            
            candles = []
            for timestamp, values in data.get(instrument, []):
                candles.append(OHLC(
                    timestamp=datetime.fromisoformat(timestamp),
                    open=values.get("open", 0),
                    high=values.get("high", 0),
                    low=values.get("low", 0),
                    close=values.get("close", 0),
                    volume=values.get("volume", 0)
                ))
            
            return candles
            
        except Exception as e:
            trading_logger.error(f"Error fetching OHLC: {e}")
            raise DataError(f"Failed to fetch OHLC data: {e}")
    
    # ========================================================================
    # ORDERS
    # ========================================================================
    
    def place_order(
        self,
        symbol: str,
        transaction_type: str,
        quantity: int,
        order_type: str = "MARKET",
        product: str = "CNC",
        price: float = 0.0,
        variety: str = "regular"
    ) -> str:
        """
        Place an order.
        
        Args:
            symbol: Trading symbol
            transaction_type: BUY or SELL
            quantity: Number of shares
            order_type: MARKET, LIMIT, SL, SL-M
            product: CNC, MIS, NRML
            price: Limit price (if applicable)
            variety: Order variety
        
        Returns:
            Order ID
        """
        self._ensure_token()
        
        try:
            # Get instrument token
            instrument_token = self.get_instrument_token(symbol)
            
            # Prepare order params
            params = {
                "exchange": "NSE",
                "tradingsymbol": symbol,
                "transaction_type": transaction_type,
                "quantity": quantity,
                "order_type": order_type,
                "product": product,
                "variety": variety
            }
            
            # Add price for limit orders
            if order_type in ["LIMIT", "SL", "SL-M"]:
                params["price"] = price
            
            # Place order
            order_id = self.kite.place_order(**params)
            
            trading_logger.info(f"Order placed: {symbol} {transaction_type} {quantity} @ ₹{price} [{order_id}]")
            
            return order_id
            
        except KiteExceptions.KiteException as e:
            trading_logger.error(f"Order placement failed: {e}")
            raise OrderError(f"Failed to place order: {e}")
    
    def buy_order(
        self,
        symbol: str,
        quantity: int,
        price: float = 0.0,
        order_type: str = "MARKET"
    ) -> str:
        """
        Place a buy order.
        
        Args:
            symbol: Trading symbol
            quantity: Number of shares
            price: Limit price
            order_type: Order type
        
        Returns:
            Order ID
        """
        product = trading.ORDER_TYPE
        return self.place_order(
            symbol=symbol,
            transaction_type="BUY",
            quantity=quantity,
            order_type=order_type,
            product=product,
            price=price
        )
    
    def sell_order(
        self,
        symbol: str,
        quantity: int,
        price: float = 0.0,
        order_type: str = "MARKET"
    ) -> str:
        """
        Place a sell order.
        
        Args:
            symbol: Trading symbol
            quantity: Number of shares
            price: Limit price
            order_type: Order type
        
        Returns:
            Order ID
        """
        product = trading.ORDER_TYPE
        return self.place_order(
            symbol=symbol,
            transaction_type="SELL",
            quantity=quantity,
            order_type=order_type,
            product=product,
            price=price
        )
    
    def get_order(self, order_id: str) -> Order:
        """
        Get order details.
        
        Args:
            order_id: Order ID
        
        Returns:
            Order object
        """
        orders = self.kite.orders()
        
        for order in orders:
            if order.get("order_id") == order_id:
                return Order(
                    order_id=order.get("order_id", ""),
                    trading_symbol=order.get("tradingsymbol", ""),
                    exchange=order.get("exchange", ""),
                    transaction_type=order.get("transaction_type", ""),
                    quantity=order.get("quantity", 0),
                    price=order.get("price", 0),
                    order_type=order.get("order_type", ""),
                    product=order.get("product", ""),
                    status=order.get("status", ""),
                    average_price=order.get("average_price", 0),
                    pending_quantity=order.get("pending_quantity", 0),
                    filled_quantity=order.get("filled_quantity", 0),
                    cancelled_quantity=order.get("cancelled_quantity", 0),
                    placed_at=order.get("placed_at", ""),
                    updated_at=order.get("updated_at", "")
                )
        
        raise OrderError(f"Order not found: {order_id}")
    
    def get_orders(self) -> List[Order]:
        """
        Get all orders.
        
        Returns:
            List of orders
        """
        orders = self.kite.orders()
        
        return [
            Order(
                order_id=o.get("order_id", ""),
                trading_symbol=o.get("tradingsymbol", ""),
                exchange=o.get("exchange", ""),
                transaction_type=o.get("transaction_type", ""),
                quantity=o.get("quantity", 0),
                price=o.get("price", 0),
                order_type=o.get("order_type", ""),
                product=o.get("product", ""),
                status=o.get("status", ""),
                average_price=o.get("average_price", 0),
                pending_quantity=o.get("pending_quantity", 0),
                filled_quantity=o.get("filled_quantity", 0),
                cancelled_quantity=o.get("cancelled_quantity", 0),
                placed_at=o.get("placed_at", ""),
                updated_at=o.get("updated_at", "")
            )
            for o in orders
        ]
    
    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an order.
        
        Args:
            order_id: Order ID
        
        Returns:
            True if cancelled
        """
        self._ensure_token()
        
        try:
            result = self.kite.cancel_order(order_id=order_id, variety="regular")
            trading_logger.info(f"Order cancelled: {order_id}")
            return True
        except Exception as e:
            trading_logger.error(f"Order cancellation failed: {e}")
            return False
    
    # ========================================================================
    # POSITIONS
    # ========================================================================
    
    def get_positions(self) -> List[Position]:
        """
        Get all positions.
        
        Returns:
            List of positions
        """
        self._ensure_token()
        
        try:
            data = self.kite.positions()
            
            positions = []
            
            # Net positions
            for pos in data.get("net", []):
                if pos.get("quantity", 0) != 0:
                    positions.append(Position(
                        trading_symbol=pos.get("tradingsymbol", ""),
                        exchange=pos.get("exchange", ""),
                        quantity=pos.get("quantity", 0),
                        average_price=pos.get("average_price", 0),
                        last_price=pos.get("last_price", 0),
                        pnl=pos.get("pnl", 0),
                        m2m=pos.get("m2m", 0),
                        product=pos.get("product", ""),
                        realised=pos.get("realised", 0)
                    ))
            
            self._positions = positions
            return positions
            
        except Exception as e:
            trading_logger.error(f"Error fetching positions: {e}")
            return []
    
    def get_position(self, symbol: str) -> Optional[Position]:
        """
        Get position for a symbol.
        
        Args:
            symbol: Trading symbol
        
        Returns:
            Position if exists
        """
        positions = self.get_positions()
        
        for pos in positions:
            if pos.trading_symbol == symbol:
                return pos
        
        return None
    
    def get_open_positions(self) -> List[Position]:
        """Get open positions (non-zero quantity)"""
        positions = self.get_positions()
        return [p for p in positions if p.quantity != 0]
    
    def get_day_positions(self) -> List[Position]:
        """Get today's positions"""
        positions = self.get_positions()
        return [p for p in positions if p.quantity != 0]
    
    # ========================================================================
    # HOLDINGS
    # ========================================================================
    
    def get_holdings(self) -> List[Dict]:
        """
        Get holdings.
        
        Returns:
            List of holdings
        """
        self._ensure_token()
        
        try:
            return self.kite.holdings()
        except Exception as e:
            trading_logger.error(f"Error fetching holdings: {e}")
            return []
    
    # ========================================================================
    # GTT TRIGGERS
    # ========================================================================
    
    def place_gtt_order(
        self,
        symbol: str,
        transaction_type: str,
        quantity: int,
        trigger_price: float,
        last_price: float = 0.0,
        order_type: str = "LIMIT"
    ) -> str:
        """
        Place GTT (Good Till Triggered) order.
        
        Args:
            symbol: Trading symbol
            transaction_type: BUY or SELL
            quantity: Number of shares
            trigger_price: Trigger price
            last_price: Last price
            order_type: Order type
        
        Returns:
            Trigger ID
        """
        self._ensure_token()
        
        try:
            instrument = f"NSE:{symbol}"
            
            # Prepare GTT params
            params = {
                "trigger_type": "single",
                "exchange": "NSE",
                "tradingsymbol": symbol,
                "last_price": last_price,
                "orders": [
                    {
                        "transaction_type": transaction_type,
                        "quantity": quantity,
                        "order_type": order_type,
                        "price": trigger_price,
                        "product": trading.ORDER_TYPE
                    }
                ]
            }
            
            trigger_id = self.kite.place_gtt(**params)
            
            trading_logger.info(f"GTT placed: {symbol} {transaction_type} {quantity} @ ₹{trigger_price}")
            
            return trigger_id
            
        except Exception as e:
            trading_logger.error(f"GTT placement failed: {e}")
            raise OrderError(f"Failed to place GTT: {e}")


# ============================================================================
# CLIENT FACTORY
# ============================================================================

def get_zerodha_client() -> ZerodhaClient:
    """
    Get Zerodha client instance (convenience function).
    
    Returns:
        ZerodhaClient instance
    """
    return ZerodhaClient()


__all__ = [
    "OrderType",
    "OrderProduct",
    "TransactionType",
    "Variety",
    "Order",
    "Position",
    "Quote",
    "OHLC",
    "ZerodhaClient",
    "get_zerodha_client"
]