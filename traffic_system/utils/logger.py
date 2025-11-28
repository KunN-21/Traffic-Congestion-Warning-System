"""
Logging System for Traffic Congestion Warning System
Provides centralized logging with file and console output
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional


class TrafficLogger:
    """
    Centralized logging system for the traffic monitoring application.
    
    Features:
    - Console and file logging
    - Rotating log files by date
    - Different log levels for different modules
    - Performance metrics logging
    
    Usage:
        from traffic_system.utils.logger import get_logger
        logger = get_logger(__name__)
        logger.info("Message")
    """
    
    _instance: Optional['TrafficLogger'] = None
    _loggers: dict = {}
    
    # Log format
    LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s"
    DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
    
    # Default log directory
    DEFAULT_LOG_DIR = "logs"
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self.log_dir = Path(self.DEFAULT_LOG_DIR)
        self.log_dir.mkdir(exist_ok=True)
        
        # Create log file with date
        self.log_file = self.log_dir / f"traffic_system_{datetime.now().strftime('%Y%m%d')}.log"
        
        # Setup root logger
        self._setup_root_logger()
    
    def _setup_root_logger(self):
        """Setup the root logger with handlers"""
        root_logger = logging.getLogger("traffic_system")
        root_logger.setLevel(logging.DEBUG)
        
        # Remove existing handlers
        root_logger.handlers.clear()
        
        # Console handler (INFO level)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(self.LOG_FORMAT, self.DATE_FORMAT)
        console_handler.setFormatter(console_formatter)
        
        # File handler (DEBUG level - captures everything)
        file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(self.LOG_FORMAT, self.DATE_FORMAT)
        file_handler.setFormatter(file_formatter)
        
        root_logger.addHandler(console_handler)
        root_logger.addHandler(file_handler)
        
        root_logger.info(f"Logging initialized. Log file: {self.log_file}")
    
    def get_logger(self, name: str) -> logging.Logger:
        """
        Get a logger for a specific module.
        
        Args:
            name: Module name (usually __name__)
        
        Returns:
            Logger instance for the module
        """
        if name in self._loggers:
            return self._loggers[name]
        
        # Create child logger under traffic_system
        if not name.startswith("traffic_system"):
            logger_name = f"traffic_system.{name}"
        else:
            logger_name = name
        
        logger = logging.getLogger(logger_name)
        self._loggers[name] = logger
        
        return logger
    
    def set_level(self, level: str):
        """
        Set logging level for all loggers.
        
        Args:
            level: Logging level ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
        """
        numeric_level = getattr(logging, level.upper(), logging.INFO)
        logging.getLogger("traffic_system").setLevel(numeric_level)
    
    def get_log_file_path(self) -> str:
        """Get current log file path"""
        return str(self.log_file)


# Singleton instance
_traffic_logger = TrafficLogger()


def get_logger(name: str = "traffic_system") -> logging.Logger:
    """
    Get a logger for a specific module.
    
    This is the main function to use for getting loggers in the application.
    
    Args:
        name: Module name (usually pass __name__)
    
    Returns:
        Logger instance
    
    Example:
        from traffic_system.utils.logger import get_logger
        logger = get_logger(__name__)
        
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")
        logger.critical("Critical message")
    """
    return _traffic_logger.get_logger(name)


def set_log_level(level: str):
    """
    Set global logging level.
    
    Args:
        level: 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'
    """
    _traffic_logger.set_level(level)


class PerformanceLogger:
    """
    Helper class for logging performance metrics.
    
    Usage:
        from traffic_system.utils.logger import PerformanceLogger
        
        perf = PerformanceLogger("detector")
        perf.start("detection")
        # ... do detection ...
        perf.end("detection")
        perf.log_fps(30.5)
    """
    
    def __init__(self, component_name: str):
        self.logger = get_logger(f"performance.{component_name}")
        self._timers: dict = {}
    
    def start(self, operation: str):
        """Start timing an operation"""
        import time
        self._timers[operation] = time.perf_counter()
    
    def end(self, operation: str) -> float:
        """End timing and log the duration"""
        import time
        if operation not in self._timers:
            return 0.0
        
        duration = (time.perf_counter() - self._timers[operation]) * 1000  # ms
        self.logger.debug(f"{operation}: {duration:.2f}ms")
        del self._timers[operation]
        return duration
    
    def log_fps(self, fps: float):
        """Log FPS metric"""
        self.logger.debug(f"FPS: {fps:.1f}")
    
    def log_metric(self, name: str, value: float, unit: str = ""):
        """Log a custom metric"""
        self.logger.debug(f"{name}: {value:.2f}{unit}")
