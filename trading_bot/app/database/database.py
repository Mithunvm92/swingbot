"""
Database Module
==============
SQLAlchemy database layer with models and migrations.
"""

import os
from pathlib import Path
from datetime import datetime
from typing import Optional, List
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, Text, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import enum

from app.config import database
from app.utils.logger import trading_logger
from app.utils.helpers import ensure_directory

# Create engine
Base = declarative_base()


# ============================================================================
# ENUMS
# ============================================================================

class OrderStatus(enum.Enum):
    """Order status"""
    PENDING = "PENDING"
    COMPLETE = "COMPLETE"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class TradeType(enum.Enum):
    """Trade type"""
    BUY = "BUY"
    SELL = "SELL"


class SignalType(enum.Enum):
    """Signal type"""
    BUY = "BUY"
    SELL = "SELL"
    STRONG_BUY = "STRONG_BUY"
    STRONG_SELL = "STRONG_SELL"
    NEUTRAL = "NEUTRAL"


class TradingMode(enum.Enum):
    """Trading mode"""
    BACKTEST = "backtest"
    PAPER = "paper"
    LIVE = "live"


# ============================================================================
# MODELS
# ============================================================================

class Trade(Base):
    """Trade model"""
    __tablename__ = "trades"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    exchange = Column(String(10), default="NSE")
    trade_type = Column(SQLEnum(TradeType), nullable=False)
    quantity = Column(Integer, nullable=False)
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, default=0.0)
    entry_time = Column(DateTime, nullable=False)
    exit_time = Column(DateTime)
    order_id = Column(String(50))
    product = Column(String(10), default="CNC")
    status = Column(SQLEnum(OrderStatus), default=OrderStatus.PENDING)
    pnl = Column(Float, default=0.0)
    pnl_percent = Column(Float, default=0.0)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    def __repr__(self):
        return f"<Trade {self.symbol} {self.trade_type.value} {self.quantity}@{self.entry_price}>"


class Signal(Base):
    """Signal model"""
    __tablename__ = "signals"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    signal_type = Column(SQLEnum(SignalType), nullable=False)
    entry_price = Column(Float, nullable=False)
    stop_loss = Column(Float, nullable=False)
    target_price = Column(Float, nullable=False)
    confidence = Column(Float, default=0.0)
    reason = Column(String(200))
    ema_20 = Column(Float)
    ema_50 = Column(Float)
    volume_ratio = Column(Float)
    executed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    
    def __repr__(self):
        return f"<Signal {self.symbol} {self.signal_type.value} @ {self.entry_price}>"


class Position(Base):
    """Position model"""
    __tablename__ = "positions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    exchange = Column(String(10), default="NSE")
    quantity = Column(Integer, nullable=False)
    average_price = Column(Float, nullable=False)
    current_price = Column(Float, default=0.0)
    product = Column(String(10), default="CNC")
    is_open = Column(Boolean, default=True)
    trade_ids = Column(String(200))  # Comma-separated trade IDs
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    def __repr__(self):
        return f"<Position {self.symbol} {self.quantity}@{self.average_price}>"


class DailyLog(Base):
    """Daily log model"""
    __tablename__ = "daily_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String(10), nullable=False, unique=True, index=True)
    trades_count = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    pnl = Column(Float, default=0.0)
    pnl_percent = Column(Float, default=0.0)
    capital = Column(Float)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
    
    def __repr__(self):
        return f"<DailyLog {self.date} P&L: {self.pnl}>"


class PerformanceMetrics(Base):
    """Performance metrics model"""
    __tablename__ = "performance_metrics"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    period = Column(String(20), nullable=False)
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    win_rate = Column(Float, default=0.0)
    total_pnl = Column(Float, default=0.0)
    avg_pnl = Column(Float, default=0.0)
    max_drawdown = Column(Float, default=0.0)
    sharpe_ratio = Column(Float, default=0.0)
    cagr = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.now)
    
    def __repr__(self):
        return f"<PerformanceMetrics {self.period} WR: {self.win_rate}%, P&L: {self.total_pnl}>"


# ============================================================================
# DATABASE MANAGER
# ============================================================================

class DatabaseManager:
    """Database manager for trading bot"""
    
    def __init__(self, connection_string: Optional[str] = None):
        """
        Initialize database manager.
        
        Args:
            connection_string: Database connection string
        """
        if connection_string is None:
            connection_string = database.connection_string
        
        ensure_directory(Path(database.SQLITE_PATH).parent)
        
        self.engine = create_engine(connection_string, echo=False)
        self.SessionLocal = sessionmaker(bind=self.engine)
        
        trading_logger.info(f"Database initialized: {connection_string}")
    
    def create_tables(self) -> None:
        """Create all tables"""
        Base.metadata.create_all(self.engine)
        trading_logger.info("Database tables created")
    
    def drop_tables(self) -> None:
        """Drop all tables"""
        Base.metadata.drop_all(self.engine)
        trading_logger.warning("Database tables dropped")
    
    def get_session(self) -> Session:
        """Get database session"""
        return self.SessionLocal()
    
    def close(self) -> None:
        """Close database connection"""
        self.engine.dispose()


# ============================================================================
# REPOSITORY CLASSES
# ============================================================================

class TradeRepository:
    """Trade repository"""
    
    def __init__(self, db: DatabaseManager):
        """Initialize repository"""
        self.db = db
    
    def create(self, trade: Trade) -> Trade:
        """Create trade"""
        session = self.db.get_session()
        try:
            session.add(trade)
            session.commit()
            session.refresh(trade)
            return trade
        finally:
            session.close()
    
    def get(self, trade_id: int) -> Optional[Trade]:
        """Get trade by ID"""
        session = self.db.get_session()
        try:
            return session.query(Trade).filter(Trade.id == trade_id).first()
        finally:
            session.close()
    
    def get_by_symbol(self, symbol: str, status: Optional[OrderStatus] = None) -> List[Trade]:
        """Get trades by symbol"""
        session = self.db.get_session()
        try:
            query = session.query(Trade).filter(Trade.symbol == symbol)
            if status:
                query = query.filter(Trade.status == status)
            return query.all()
        finally:
            session.close()
    
    def get_all(self, limit: int = 100) -> List[Trade]:
        """Get all trades"""
        session = self.db.get_session()
        try:
            return session.query(Trade).order_by(Trade.created_at.desc()).limit(limit).all()
        finally:
            session.close()
    
    def update(self, trade: Trade) -> Trade:
        """Update trade"""
        session = self.db.get_session()
        try:
            session.merge(trade)
            session.commit()
            session.refresh(trade)
            return trade
        finally:
            session.close()
    
    def delete(self, trade_id: int) -> bool:
        """Delete trade"""
        session = self.db.get_session()
        try:
            trade = session.query(Trade).filter(Trade.id == trade_id).first()
            if trade:
                session.delete(trade)
                session.commit()
                return True
            return False
        finally:
            session.close()


class SignalRepository:
    """Signal repository"""
    
    def __init__(self, db: DatabaseManager):
        """Initialize repository"""
        self.db = db
    
    def create(self, signal: Signal) -> Signal:
        """Create signal"""
        session = self.db.get_session()
        try:
            session.add(signal)
            session.commit()
            session.refresh(signal)
            return signal
        finally:
            session.close()
    
    def get_all(self, limit: int = 100) -> List[Signal]:
        """Get all signals"""
        session = self.db.get_session()
        try:
            return session.query(Signal).order_by(Signal.created_at.desc()).limit(limit).all()
        finally:
            session.close()
    
    def get_unexecuted(self) -> List[Signal]:
        """Get unexecuted signals"""
        session = self.db.get_session()
        try:
            return session.query(Signal).filter(Signal.executed == False).all()
        finally:
            session.close()


class PositionRepository:
    """Position repository"""
    
    def __init__(self, db: DatabaseManager):
        """Initialize repository"""
        self.db = db
    
    def create(self, position: Position) -> Position:
        """Create position"""
        session = self.db.get_session()
        try:
            session.add(position)
            session.commit()
            session.refresh(position)
            return position
        finally:
            session.close()
    
    def get_open(self) -> List[Position]:
        """Get open positions"""
        session = self.db.get_session()
        try:
            return session.query(Position).filter(Position.is_open == True).all()
        finally:
            session.close()
    
    def get_by_symbol(self, symbol: str) -> Optional[Position]:
        """Get position by symbol"""
        session = self.db.get_session()
        try:
            return session.query(Position).filter(
                Position.symbol == symbol,
                Position.is_open == True
            ).first()
        finally:
            session.close()
    
    def update(self, position: Position) -> Position:
        """Update position"""
        session = self.db.get_session()
        try:
            session.merge(position)
            session.commit()
            session.refresh(position)
            return position
        finally:
            session.close()


class DailyLogRepository:
    """Daily log repository"""
    
    def __init__(self, db: DatabaseManager):
        """Initialize repository"""
        self.db = db
    
    def create(self, log: DailyLog) -> DailyLog:
        """Create daily log"""
        session = self.db.get_session()
        try:
            session.add(log)
            session.commit()
            session.refresh(log)
            return log
        finally:
            session.close()
    
    def get_by_date(self, date: str) -> Optional[DailyLog]:
        """Get log by date"""
        session = self.db.get_session()
        try:
            return session.query(DailyLog).filter(DailyLog.date == date).first()
        finally:
            session.close()
    
    def update(self, log: DailyLog) -> DailyLog:
        """Update daily log"""
        session = self.db.get_session()
        try:
            session.merge(log)
            session.commit()
            session.refresh(log)
            return log
        finally:
            session.close()


# ============================================================================
# FACTORY
# ============================================================================

# Global database instance
_db: Optional[DatabaseManager] = None


def get_database() -> DatabaseManager:
    """Get database manager"""
    global _db
    if _db is None:
        _db = DatabaseManager()
        _db.create_tables()
    return _db


def get_trade_repository() -> TradeRepository:
    """Get trade repository"""
    return TradeRepository(get_database())


def get_signal_repository() -> SignalRepository:
    """Get signal repository"""
    return SignalRepository(get_database())


def get_position_repository() -> PositionRepository:
    """Get position repository"""
    return PositionRepository(get_database())


def get_daily_log_repository() -> DailyLogRepository:
    """Get daily log repository"""
    return DailyLogRepository(get_database())


__all__ = [
    "Base",
    "OrderStatus",
    "TradeType",
    "SignalType",
    "TradingMode",
    "Trade",
    "Signal",
    "Position",
    "DailyLog",
    "PerformanceMetrics",
    "DatabaseManager",
    "TradeRepository",
    "SignalRepository",
    "PositionRepository",
    "DailyLogRepository",
    "get_database",
    "get_trade_repository",
    "get_signal_repository",
    "get_position_repository",
    "get_daily_log_repository"
]