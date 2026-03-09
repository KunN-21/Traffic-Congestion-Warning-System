"""
Path utilities for cross-platform compatibility
Handles paths correctly for both development and packaged (PyInstaller) environments
"""

import sys
from pathlib import Path


def get_base_path() -> Path:
    """
    Get the base path of the application.
    
    When running from source: returns the directory containing main_app.py
    When running from PyInstaller bundle: returns the temporary extraction directory
    
    Returns:
        Path object pointing to the base directory
    """
    if getattr(sys, 'frozen', False):
        # Running in PyInstaller bundle
        # sys._MEIPASS is the path to the temporary folder where PyInstaller extracts files
        base_path = Path(sys._MEIPASS)
    else:
        # Running from source code
        # Get the directory containing this file, then go up to the project root
        base_path = Path(__file__).parent.parent
    
    return base_path


def get_resource_path(relative_path: str) -> str:
    """
    Get absolute path to a resource file.
    
    Works correctly in both development and packaged environments.
    
    Args:
        relative_path: Path relative to the project root (e.g., "Model/best_v2.pt")
    
    Returns:
        Absolute path string to the resource
    
    Example:
        >>> model_path = get_resource_path("Model/best_v2.pt")
        >>> config_path = get_resource_path("traffic_system/config/default_config.json")
    """
    base_path = get_base_path()
    resource_path = base_path / relative_path
    return str(resource_path)


def get_user_data_path() -> Path:
    """
    Get path to user data directory (for saving logs, profiles, etc.)
    
    This directory persists across application restarts, unlike the PyInstaller
    temporary directory.
    
    Returns:
        Path to user data directory
    """
    if getattr(sys, 'frozen', False):
        # When packaged, use the directory containing the executable
        user_data = Path(sys.executable).parent
    else:
        # When running from source, use the project directory
        user_data = Path(__file__).parent.parent
    
    return user_data


def get_logs_path() -> Path:
    """
    Get path to logs directory.
    
    Returns:
        Path to logs directory (creates if doesn't exist)
    """
    logs_path = get_user_data_path() / "logs"
    logs_path.mkdir(exist_ok=True)
    return logs_path


def get_calibration_profiles_path() -> Path:
    """
    Get path to calibration profiles directory.
    
    Returns:
        Path to calibration_profiles directory (creates if doesn't exist)
    """
    profiles_path = get_user_data_path() / "calibration_profiles"
    profiles_path.mkdir(exist_ok=True)
    return profiles_path


def get_config_path() -> Path:
    """
    Get path to user config directory.
    
    Returns:
        Path to config directory
    """
    return get_user_data_path() / "traffic_system" / "config"


def ensure_directories():
    """
    Ensure all required directories exist.
    Call this at application startup.
    """
    get_logs_path()
    get_calibration_profiles_path()
    
    # Ensure config directory exists
    config_path = get_config_path()
    config_path.mkdir(parents=True, exist_ok=True)


def is_frozen() -> bool:
    """
    Check if running from PyInstaller bundle.
    
    Returns:
        True if running from packaged .exe, False if running from source
    """
    return getattr(sys, 'frozen', False)
