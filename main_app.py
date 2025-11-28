"""
Main Application Entry Point
Traffic Congestion Warning System
"""

import sys
from PyQt6.QtWidgets import QApplication
from traffic_system.ui.main_window import MainWindow


def main():
    """Main application entry point"""
    app = QApplication(sys.argv)
    
    # Set application info
    app.setApplicationName("Traffic Congestion Warning System")
    app.setOrganizationName("Traffic Monitoring Team")
    
    # Create and show main window
    window = MainWindow()
    window.show()
    
    # Run application
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
