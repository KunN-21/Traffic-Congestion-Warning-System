"""
Main Application Entry Point
Traffic Congestion Warning System
"""

import sys
import os

# Fix DPI scaling on Windows - must be before QApplication
if sys.platform == "win32":
    # Method 1: Use Qt's high DPI scaling
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"  # Disable Qt's auto scaling
    
    # Method 2: Set Windows DPI awareness (more reliable)
    try:
        from ctypes import windll
        # SetProcessDpiAwareness(2) = Per-Monitor DPI Aware
        windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            # Fallback for older Windows
            windll.user32.SetProcessDPIAware()
        except Exception:
            pass

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from traffic_system.ui.main_window import MainWindow


def main():

    app = QApplication(sys.argv)
    app.setApplicationName("Traffic Congestion Warning System")
    app.setOrganizationName("Traffic Monitoring Team")
    
    # Set default font size for better scaling
    font = app.font()
    if sys.platform == "win32":
        font.setPointSize(9)  # Slightly smaller font on Windows
    app.setFont(font)
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
