"""Utility modules"""

from .logger import get_logger, set_log_level, PerformanceLogger
from .benchmark import Benchmarker, DetectionEvaluator, BenchmarkResult
from .paths import (
    get_base_path,
    get_resource_path,
    get_user_data_path,
    get_logs_path,
    get_calibration_profiles_path,
    get_config_path,
    ensure_directories,
    is_frozen
)

__all__ = [
    'get_logger', 
    'set_log_level', 
    'PerformanceLogger',
    'Benchmarker',
    'DetectionEvaluator',
    'BenchmarkResult',
    'get_base_path',
    'get_resource_path',
    'get_user_data_path',
    'get_logs_path',
    'get_calibration_profiles_path',
    'get_config_path',
    'ensure_directories',
    'is_frozen'
]
