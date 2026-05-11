"""
Scheduler Module
===============
APScheduler-based scheduler for automated trading tasks.
"""

from typing import Optional, Callable, Dict, List
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger

from app.config import scheduler, trading
from app.utils.logger import trading_logger
from app.utils.helpers import is_market_open


# ============================================================================
# JOB DEFINITIONS
# ============================================================================

class JobType:
    """Job types"""
    SCANNER = "scanner"
    DAILY_LOGIN = "daily_login"
    POSITION_MONITOR = "position_monitor"
    END_OF_DAY = "end_of_day"
    DAILY_SUMMARY = "daily_summary"


# ============================================================================
# SCHEDULER
# ============================================================================

class TradingScheduler:
    """
    Trading scheduler for automated tasks.
    Manages market-hour-aware scheduling.
    """
    
    def __init__(self, timezone: str = "Asia/Kolkata"):
        """
        Initialize scheduler.
        
        Args:
            timezone: Timezone string
        """
        self.scheduler = BlockingScheduler(timezone=timezone)
        self.jobs: Dict[str, dict] = {}
        self._running = False
    
    def add_scanner_job(
        self,
        func: Callable,
        interval_minutes: int = 15,
        name: str = "scanner"
    ) -> str:
        """
        Add scanner job.
        
        Args:
            func: Scanner function
            interval_minutes: Interval in minutes
            name: Job name
        
        Returns:
            Job ID
        """
        job_id = self.scheduler.add_job(
            func,
            trigger=IntervalTrigger(minutes=interval_minutes),
            id=name,
            name=f"Scanner ({interval_minutes} min)",
            replace_existing=True
        )
        
        self.jobs[name] = {
            "id": job_id,
            "type": JobType.SCANNER,
            "func": func
        }
        
        trading_logger.info(f"Scanner job scheduled: every {interval_minutes} minutes")
        
        return job_id
    
    def add_market_scanner_job(
        self,
        func: Callable,
        interval_minutes: int = 15,
        name: str = "market_scanner"
    ) -> str:
        """
        Add market-hours-only scanner job.
        
        Args:
            func: Scanner function
            interval_minutes: Interval in minutes
            name: Job name
        
        Returns:
            Job ID
        """
        job_id = self.scheduler.add_job(
            func,
            trigger=IntervalTrigger(minutes=interval_minutes),
            id=name,
            name=f"Market Scanner ({interval_minutes} min)",
            replace_existing=True,
            # Only run during market hours
            hour=f"{scheduler.MARKET_OPEN_HOUR}-{scheduler.MARKET_CLOSE_HOUR}",
            minute=f"*/{interval_minutes}"
        )
        
        self.jobs[name] = {
            "id": job_id,
            "type": JobType.SCANNER,
            "func": func,
            "market_only": True
        }
        
        trading_logger.info(f"Market scanner job scheduled: every {interval_minutes} min during market hours")
        
        return job_id
    
    def add_daily_login_job(
        self,
        func: Callable,
        hour: int = 8,
        minute: int = 30,
        name: str = "daily_login"
    ) -> str:
        """
        Add daily auto-login job.
        
        Args:
            func: Login function
            hour: Hour (IST)
            minute: Minute
        
        Returns:
            Job ID
        """
        job_id = self.scheduler.add_job(
            func,
            trigger=CronTrigger(hour=hour, minute=minute),
            id=name,
            name="Daily Login",
            replace_existing=True
        )
        
        self.jobs[name] = {
            "id": job_id,
            "type": JobType.DAILY_LOGIN,
            "func": func
        }
        
        trading_logger.info(f"Daily login job scheduled: {hour:02d}:{minute:02d}")
        
        return job_id
    
    def add_position_monitor_job(
        self,
        func: Callable,
        interval_minutes: int = 5,
        name: str = "position_monitor"
    ) -> str:
        """
        Add position monitor job.
        
        Args:
            func: Monitor function
            interval_minutes: Interval in minutes
            name: Job name
        
        Returns:
            Job ID
        """
        job_id = self.scheduler.add_job(
            func,
            trigger=IntervalTrigger(minutes=interval_minutes),
            id=name,
            name=f"Position Monitor ({interval_minutes} min)",
            replace_existing=True
        )
        
        self.jobs[name] = {
            "id": job_id,
            "type": JobType.POSITION_MONITOR,
            "func": func
        }
        
        trading_logger.info(f"Position monitor job scheduled: every {interval_minutes} minutes")
        
        return job_id
    
    def add_end_of_day_job(
        self,
        func: Callable,
        hour: int = 15,
        minute: int = 25,
        name: str = "end_of_day"
    ) -> str:
        """
        Add end of day job.
        
        Args:
            func: End of day function
            hour: Hour (IST)
            minute: Minute
        
        Returns:
            Job ID
        """
        job_id = self.scheduler.add_job(
            func,
            trigger=CronTrigger(hour=hour, minute=minute),
            id=name,
            name="End of Day",
            replace_existing=True
        )
        
        self.jobs[name] = {
            "id": job_id,
            "type": JobType.END_OF_DAY,
            "func": func
        }
        
        trading_logger.info(f"End of day job scheduled: {hour:02d}:{minute:02d}")
        
        return job_id
    
    def add_daily_summary_job(
        self,
        func: Callable,
        hour: int = 18,
        minute: int = 0,
        name: str = "daily_summary"
    ) -> str:
        """
        Add daily summary job.
        
        Args:
            func: Summary function
            hour: Hour (IST)
            minute: Minute
        
        Returns:
            Job ID
        """
        job_id = self.scheduler.add_job(
            func,
            trigger=CronTrigger(hour=hour, minute=minute),
            id=name,
            name="Daily Summary",
            replace_existing=True
        )
        
        self.jobs[name] = {
            "id": job_id,
            "type": JobType.DAILY_SUMMARY,
            "func": func
        }
        
        trading_logger.info(f"Daily summary job scheduled: {hour:02d}:{minute:02d}")
        
        return job_id
    
    def remove_job(self, job_id: str) -> None:
        """Remove a job"""
        self.scheduler.remove_job(job_id)
        trading_logger.info(f"Job removed: {job_id}")
    
    def list_jobs(self) -> List[dict]:
        """List all scheduled jobs"""
        jobs = []
        
        for job in self.scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": str(job.next_run_time) if job.next_run_time else None
            })
        
        return jobs
    
    def start(self) -> None:
        """Start scheduler"""
        if not self._running:
            self.scheduler.start()
            self._running = True
            trading_logger.info("Scheduler started")
    
    def shutdown(self, wait: bool = True) -> None:
        """Shutdown scheduler"""
        if self._running:
            self.scheduler.shutdown(wait=wait)
            self._running = False
            trading_logger.info("Scheduler shutdown")
    
    def is_running(self) -> bool:
        """Check if running"""
        return self._running


# ============================================================================
# TRADING SPECIFIC SCHEDULER
# ============================================================================

class TradingJobScheduler:
    """
    Trading-specific scheduler with predefined jobs.
    """
    
    def __init__(self):
        """Initialize trading job scheduler"""
        self.scheduler = TradingScheduler(timezone=scheduler.TIMEZONE)
        
        # Job functions (to be set)
        self.scanner_func: Optional[Callable] = None
        self.login_func: Optional[Callable] = None
        self.monitor_func: Optional[Callable] = None
        self.eod_func: Optional[Callable] = None
        self.summary_func: Optional[Callable] = None
    
    def set_scanner_function(self, func: Callable) -> None:
        """Set scanner function"""
        self.scanner_func = func
    
    def set_login_function(self, func: Callable) -> None:
        """Set login function"""
        self.login_func = func
    
    def set_monitor_function(self, func: Callable) -> None:
        """Set position monitor function"""
        self.monitor_func = func
    
    def set_end_of_day_function(self, func: Callable) -> None:
        """Set end of day function"""
        self.eod_func = func
    
    def set_daily_summary_function(self, func: Callable) -> None:
        """Set daily summary function"""
        self.summary_func = func
    
    def setup_jobs(self) -> None:
        """Setup all trading jobs"""
        # Scanner job
        if self.scanner_func:
            self.scheduler.add_market_scanner_job(
                self.scanner_func,
                interval_minutes=trading.SCAN_INTERVAL_MINUTES
            )
        
        # Daily login
        if self.login_func:
            self.scheduler.add_daily_login_job(
                self.login_func,
                hour=scheduler.AUTO_LOGIN_HOUR,
                minute=scheduler.AUTO_LOGIN_MINUTE
            )
        
        # Position monitor
        if self.monitor_func:
            self.scheduler.add_position_monitor_job(
                self.monitor_func,
                interval_minutes=5
            )
        
        # End of day
        if self.eod_func:
            self.scheduler.add_end_of_day_job(
                self.eod_func,
                hour=scheduler.MARKET_CLOSE_HOUR - 5,
                minute=scheduler.MARKET_CLOSE_MINUTE
            )
        
        # Daily summary
        if self.summary_func:
            self.scheduler.add_daily_summary_job(
                self.summary_func,
                hour=18,
                minute=0
            )
        
        trading_logger.info("Trading jobs configured")
    
    def start(self) -> None:
        """Start scheduler"""
        self.scheduler.start()
    
    def shutdown(self) -> None:
        """Shutdown scheduler"""
        self.scheduler.shutdown()


# ============================================================================
# FACTORY
# ============================================================================

def create_scheduler(timezone: str = "Asia/Kolkata") -> TradingScheduler:
    """
    Create trading scheduler.
    
    Args:
        timezone: Timezone
    
    Returns:
        TradingScheduler instance
    """
    return TradingScheduler(timezone=timezone)


def create_trading_scheduler() -> TradingJobScheduler:
    """
    Create trading job scheduler.
    
    Returns:
        TradingJobScheduler instance
    """
    return TradingJobScheduler()


__all__ = [
    "JobType",
    "TradingScheduler",
    "TradingJobScheduler",
    "create_scheduler",
    "create_trading_scheduler"
]