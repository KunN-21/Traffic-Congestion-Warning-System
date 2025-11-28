"""
Traffic Congestion Warning System
================================

A comprehensive traffic monitoring and congestion warning system using
computer vision and deep learning technologies.

Overview
--------
This system provides real-time traffic density monitoring and congestion
warning using:

- **YOLOv11** for vehicle detection (car, motorcycle, bus, truck, bicycle)
- **DeepSORT** for multi-object tracking across frames
- **Area-based density calculation** using Vietnamese vehicle dimensions
- **PyQt6** for the graphical user interface

Main Components
---------------
1. **Core Modules** (`traffic_system.core`)
   - `detector.py`: YOLO-based vehicle detection with batch processing
   - `tracker.py`: DeepSORT vehicle tracking
   - `calibration.py`: Road area calibration using 4-point perspective
   - `density_calculator.py`: Traffic density calculation
   - `speed_estimator.py`: Vehicle speed estimation using tracking data
   - `video_thread.py`: Threaded video processing for performance

2. **UI Modules** (`traffic_system.ui`)
   - `main_window.py`: Main application window
   - `video_widget.py`: Video display and calibration interaction
   - `config_dialog.py`: Settings configuration dialog
   - `chart_widget.py`: Real-time statistics charts
   - `timeline_widget.py`: Video timeline and seek controls

3. **Configuration** (`traffic_system.config`)
   - `settings.py`: Application settings and vehicle dimensions

4. **Utilities** (`traffic_system.utils`)
   - `logger.py`: Centralized logging system

Quick Start
-----------
Basic usage::

    from traffic_system.ui.main_window import MainWindow
    from PyQt6.QtWidgets import QApplication
    import sys
    
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

Density Calculation
-------------------
The traffic density is calculated using the formula::

    R = (TL / DT) × 100

Where:
- **R**: Density percentage (%)
- **TL**: Total occupied area = Σ(Xi × SLi) in m²
- **DT**: Road area = Ls × Ws in m²
- **Xi**: Vehicle footprint area (length × width)
- **SLi**: Number of vehicles of type i

Vehicle Dimensions (Vietnamese Standard)
----------------------------------------
===========  ========  ========  ========  ==========
Vehicle      Length    Width     Height    Area (m²)
===========  ========  ========  ========  ==========
Motorcycle   2.05 m    0.725 m   1.102 m   1.486
Bicycle      1.75 m    0.600 m   1.050 m   1.050
Car          5.80 m    2.100 m   1.300 m   12.18
Bus          12.10 m   2.600 m   4.100 m   31.46
Truck        9.10 m    2.600 m   4.100 m   23.66
===========  ========  ========  ========  ==========

Density Levels
--------------
======  ========  =================  ======
Level   R Value   Status             Color
======  ========  =================  ======
Low     < 30%     Sparse traffic     Green
Medium  30-80%    Moderate traffic   Yellow
High    >= 80%    Heavy traffic      Red
======  ========  =================  ======

System Requirements
-------------------
- Python 3.8+
- PyQt6 >= 6.6.0
- PyTorch >= 2.0.0
- Ultralytics >= 8.0.0
- OpenCV >= 4.8.0
- CUDA (recommended for GPU acceleration)

Author
------
Traffic Monitoring Team - 2025

License
-------
© 2025 Traffic Monitoring Team. All rights reserved.
"""

__version__ = "1.0.0"
__author__ = "Traffic Monitoring Team"
__email__ = "team@example.com"

# Import main components for easier access
from .config.settings import Settings
from .core.detector import VehicleDetector
from .core.tracker import VehicleTracker
from .core.calibration import CalibrationManager
from .core.density_calculator import DensityCalculator
from .utils.logger import get_logger, set_log_level

__all__ = [
    "Settings",
    "VehicleDetector", 
    "VehicleTracker",
    "CalibrationManager",
    "DensityCalculator",
    "get_logger",
    "set_log_level",
]
