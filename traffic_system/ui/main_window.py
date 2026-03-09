"""
Main Window for Traffic Congestion Monitoring System
PyQt6-based GUI application with enhanced features
"""

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QFileDialog, QMessageBox,
                             QGroupBox, QGridLayout, QStatusBar, QTabWidget,
                             QStackedWidget, QComboBox, QInputDialog)
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt
import os
import time

from .video_widget import VideoWidget
from .config_dialog import ConfigDialog
from .timeline_widget import VideoTimeline
from .video_selector import VideoSelectorWidget
from ..config.settings import Settings
from ..core.detector import VehicleDetector
from ..core.tracker import VehicleTracker
from ..core.calibration import CalibrationMode
from ..core.calibration import CalibrationManager
from ..core.density_calculator import DensityCalculator
from ..utils.logger import get_logger

logger = get_logger(__name__)


class MainWindow(QMainWindow):
    """Main application window with integrated features"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Hệ Thống Giám Sát Giao Thông")
        self.setGeometry(100, 100, 1600, 950)
        
        # Theme state - default to light mode
        self.is_dark_theme = False
        self.apply_theme()
        
        logger.info("Initializing MainWindow...")
        
        # Initialize settings
        self.settings = Settings()
        
        # Initialize components
        self.detector = None
        self.tracker = None
        # Use absolute path for calibration profiles
        self.calibration = CalibrationManager(self.settings.calibration.get_absolute_profiles_dir())
        self.density_calculator = DensityCalculator(self.settings)
        
        # Video path
        self.video_path = None
        self.video_name = None
        
        # Performance tracking
        self._last_fps_time = time.time()
        self._frame_count = 0
        self._current_fps = 0.0
        
        # UI Setup
        self.setup_ui()
        self.setup_menu()
        self.setup_connections()
        
        # Apply control buttons theme after UI is created
        self.apply_control_buttons_theme()
        
        # Status
        self.is_playing = False
        self.is_calibrating = False
        
        logger.info("MainWindow initialized successfully")
    
    def setup_ui(self):
        """Setup user interface with stacked widget for pages"""
        # Central widget with stacked layout
        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)
        
        # Page 0: Video Selector (Start screen)
        self.video_selector = VideoSelectorWidget("Video")
        self.video_selector.apply_theme(self.is_dark_theme)
        self.video_selector.video_selected.connect(self.on_video_selected)
        self.stacked_widget.addWidget(self.video_selector)
        
        # Page 1: Main Analysis View
        self.main_view = QWidget()
        main_layout = QHBoxLayout(self.main_view)
        
        # Left panel - Video and controls
        left_panel = self.create_left_panel()
        main_layout.addWidget(left_panel, stretch=3)
        
        # Right panel - Information and statistics
        right_panel = self.create_right_panel()
        main_layout.addWidget(right_panel, stretch=1)
        
        self.stacked_widget.addWidget(self.main_view)
        
        # Status bar
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("Sẵn sàng - Chọn video để bắt đầu")
    
    def create_left_panel(self):
        """Create left panel with video display and timeline"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(5)
        
        # Video widget
        self.video_widget = VideoWidget(self.settings, self.calibration)
        layout.addWidget(self.video_widget, stretch=1)
        
        # Timeline widget
        self.timeline = VideoTimeline()
        self.timeline.setMaximumHeight(80)
        self.timeline.apply_theme(self.is_dark_theme)
        layout.addWidget(self.timeline)
        
        # Control buttons
        controls = self.create_control_buttons()
        layout.addWidget(controls)
        
        return widget
    
    def create_control_buttons(self):
        """Create control buttons"""
        group = QGroupBox("Điều Khiển")
        layout = QHBoxLayout(group)
        layout.setSpacing(10)
        
        # Common styles
        combobox_style = """
            QComboBox {
                background-color: #45475a;
                color: #cdd6f4;
                border: 1px solid #585b70;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 14px;
            }
            QComboBox:hover {
                border-color: #89b4fa;
            }
            QComboBox::drop-down {
                border: none;
                padding-right: 8px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid #cdd6f4;
                margin-right: 8px;
            }
            QComboBox QAbstractItemView {
                background-color: #313244;
                color: #cdd6f4;
                selection-background-color: #585b70;
                border: 1px solid #585b70;
                border-radius: 4px;
            }
        """
        
        # Back to video list button
        self.btn_back = QPushButton("Quay Lại Danh Sách")
        self.btn_back.setMinimumHeight(40)
        self.btn_back.setStyleSheet("""
            QPushButton {
                background-color: #45475a;
                color: white;
                border: 1px solid #585b70;
                border-radius: 6px;
                font-weight: bold;
                font-size: 14px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #585b70;
            }
        """)
        self.btn_back.clicked.connect(self.show_video_selector)
        layout.addWidget(self.btn_back)
        
        # Lane selector
        self.lbl_lane = QLabel("Số làn:")
        self.lbl_lane.setStyleSheet("color: #cdd6f4; font-size: 14px;")
        layout.addWidget(self.lbl_lane)
        
        self.combo_num_lanes = QComboBox()
        self.combo_num_lanes.addItems(["1 làn", "2 làn"])
        self.combo_num_lanes.setStyleSheet(combobox_style)
        self.combo_num_lanes.currentIndexChanged.connect(self.on_num_lanes_changed)
        layout.addWidget(self.combo_num_lanes)
        
        # Current lane label
        self.lbl_current_lane = QLabel("Làn: 1/1")
        self.lbl_current_lane.setStyleSheet("""
            color: #a6e3a1;
            font-size: 14px;
            font-weight: bold;
            background-color: #313244;
            padding: 8px 16px;
            border-radius: 6px;
        """)
        layout.addWidget(self.lbl_current_lane)
        
        # Calibration mode selector
        self.lbl_mode = QLabel("Chế độ:")
        self.lbl_mode.setStyleSheet("color: #cdd6f4; font-size: 14px;")
        layout.addWidget(self.lbl_mode)
        
        self.combo_calib_mode = QComboBox()
        self.combo_calib_mode.addItems(["Đa Giác (4 điểm)", "Hình Tròn (vòng xoay)", "Elip (vòng xoay dẹt)"])
        self.combo_calib_mode.setStyleSheet(combobox_style)
        self.combo_calib_mode.currentIndexChanged.connect(self.on_calib_mode_changed)
        layout.addWidget(self.combo_calib_mode)
        
        # Calibration button
        self.btn_calibrate = QPushButton("Hiệu Chỉnh Vùng Quan Sát")
        self.btn_calibrate.setMinimumHeight(40)
        self.btn_calibrate.setEnabled(False)
        self.btn_calibrate.setStyleSheet("""
            QPushButton {
                background-color: #fab387;
                color: #1e1e2e;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 14px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #f9c096;
            }
            QPushButton:disabled {
                background-color: #313244;
                color: #6c7086;
            }
        """)
        self.btn_calibrate.clicked.connect(self.start_calibration)
        layout.addWidget(self.btn_calibrate)
        
        # Play/Pause button
        self.btn_play = QPushButton("Phát Video")
        self.btn_play.setMinimumHeight(40)
        self.btn_play.setEnabled(False)
        self.btn_play.setStyleSheet("""
            QPushButton {
                background-color: #a6e3a1;
                color: #1e1e2e;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 14px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #94e2d5;
            }
            QPushButton:disabled {
                background-color: #313244;
                color: #6c7086;
            }
        """)
        self.btn_play.clicked.connect(self.toggle_play)
        layout.addWidget(self.btn_play)
        
        # Stop button
        self.btn_stop = QPushButton("Dừng Phân Tích")
        self.btn_stop.setMinimumHeight(40)
        self.btn_stop.setEnabled(False)
        self.btn_stop.setStyleSheet("""
            QPushButton {
                background-color: #f38ba8;
                color: #1e1e2e;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 14px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #eba0ac;
            }
            QPushButton:disabled {
                background-color: #313244;
                color: #6c7086;
            }
        """)
        self.btn_stop.clicked.connect(self.stop_video)
        layout.addWidget(self.btn_stop)
        
        return group
    
    def create_right_panel(self):
        """Create right panel with statistics and configuration"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)
        
        # Density Status at top - simple display with Low/Medium/High and percentage
        gauge_group = QGroupBox("Mật Độ Giao Thông")
        gauge_layout = QHBoxLayout(gauge_group)
        gauge_layout.setSpacing(15)
        
        # Status label (Low/Medium/High)
        self.lbl_density_status = QLabel("--")
        self.lbl_density_status.setStyleSheet("""
            font-size: 24px;
            font-weight: bold;
            padding: 10px 20px;
            border-radius: 8px;
            background-color: #6c7086;
            color: white;
        """)
        self.lbl_density_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_density_status.setMinimumWidth(120)
        gauge_layout.addWidget(self.lbl_density_status)
        
        # Percentage label
        self.lbl_density_percent = QLabel("0.0%")
        self.lbl_density_percent.setStyleSheet("""
            font-size: 28px;
            font-weight: bold;
            color: #89b4fa;
        """)
        self.lbl_density_percent.setAlignment(Qt.AlignmentFlag.AlignCenter)
        gauge_layout.addWidget(self.lbl_density_percent)
        
        gauge_layout.addStretch()
        layout.addWidget(gauge_group)
        
        # Tab widget for different info sections
        tabs = QTabWidget()
        
        # Tab 1: Statistics (Lane counts only)
        stats_tab = self.create_stats_tab()
        tabs.addTab(stats_tab, "Thống Kê")
        
        # Tab 2: Configuration (System info, Calibration params, Density info)
        config_tab = self.create_config_tab()
        tabs.addTab(config_tab, "Cấu Hình")
        
        layout.addWidget(tabs, stretch=1)
        
        return widget
    
    def create_stats_tab(self):
        """Create statistics tab content - Lane vehicle counts only"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)
        
        vehicle_names = {
            'motorcycle': 'Xe máy',
            'bicycle': 'Xe đạp', 
            'car': 'Ô tô',
            'bus': 'Xe buýt',
            'truck': 'Xe tải'
        }
        
        # Lane 1 vehicle counts
        vehicle1_group = QGroupBox("Làn 1 - Số Lượng Phương Tiện")
        vehicle1_layout = QGridLayout(vehicle1_group)
        vehicle1_layout.setSpacing(8)
        
        self.lbl_lane1_counts = {}
        row = 0
        for vehicle_type in ['motorcycle', 'bicycle', 'car', 'bus', 'truck']:
            label = QLabel(f"{vehicle_names.get(vehicle_type, vehicle_type)}:")
            label.setStyleSheet("font-size: 16px; font-weight: bold;")
            count = QLabel("0")
            count.setStyleSheet("font-size: 18px; font-weight: bold; color: #a6e3a1;")
            vehicle1_layout.addWidget(label, row, 0)
            vehicle1_layout.addWidget(count, row, 1)
            self.lbl_lane1_counts[vehicle_type] = count
            row += 1
        
        # Lane 1 density status
        lbl = QLabel("Mật độ giao thông:")
        lbl.setStyleSheet("font-size: 18px; font-weight: bold;")
        vehicle1_layout.addWidget(lbl, row, 0)
        
        # Status and ratio in horizontal layout
        lane1_status_widget = QWidget()
        lane1_status_layout = QHBoxLayout(lane1_status_widget)
        lane1_status_layout.setContentsMargins(0, 0, 0, 0)
        lane1_status_layout.setSpacing(10)
        
        self.lbl_lane1_status = QLabel("-")
        self.lbl_lane1_status.setStyleSheet("font-size: 18px; font-weight: bold;")
        lane1_status_layout.addWidget(self.lbl_lane1_status)
        
        self.lbl_lane1_ratio = QLabel("0.0%")
        self.lbl_lane1_ratio.setStyleSheet("font-size: 18px; font-weight: bold; color: #89b4fa;")
        lane1_status_layout.addWidget(self.lbl_lane1_ratio)
        
        lane1_status_layout.addStretch()
        vehicle1_layout.addWidget(lane1_status_widget, row, 1)
        
        layout.addWidget(vehicle1_group)
        
        # Lane 2 vehicle counts
        vehicle2_group = QGroupBox("Làn 2 - Số Lượng Phương Tiện")
        vehicle2_layout = QGridLayout(vehicle2_group)
        vehicle2_layout.setSpacing(8)
        
        self.lbl_lane2_counts = {}
        row = 0
        for vehicle_type in ['motorcycle', 'bicycle', 'car', 'bus', 'truck']:
            label = QLabel(f"{vehicle_names.get(vehicle_type, vehicle_type)}:")
            label.setStyleSheet("font-size: 16px; font-weight: bold;")
            count = QLabel("0")
            count.setStyleSheet("font-size: 18px; font-weight: bold; color: #fab387;")
            vehicle2_layout.addWidget(label, row, 0)
            vehicle2_layout.addWidget(count, row, 1)
            self.lbl_lane2_counts[vehicle_type] = count
            row += 1
        
        # Lane 2 density status
        lbl = QLabel("Mật độ giao thông:")
        lbl.setStyleSheet("font-size: 18px; font-weight: bold;")
        vehicle2_layout.addWidget(lbl, row, 0)
        
        # Status and ratio in horizontal layout
        lane2_status_widget = QWidget()
        lane2_status_layout = QHBoxLayout(lane2_status_widget)
        lane2_status_layout.setContentsMargins(0, 0, 0, 0)
        lane2_status_layout.setSpacing(10)
        
        self.lbl_lane2_status = QLabel("-")
        self.lbl_lane2_status.setStyleSheet("font-size: 18px; font-weight: bold;")
        lane2_status_layout.addWidget(self.lbl_lane2_status)
        
        self.lbl_lane2_ratio = QLabel("0.0%")
        self.lbl_lane2_ratio.setStyleSheet("font-size: 18px; font-weight: bold; color: #89b4fa;")
        lane2_status_layout.addWidget(self.lbl_lane2_ratio)
        
        lane2_status_layout.addStretch()
        vehicle2_layout.addWidget(lane2_status_widget, row, 1)
        
        layout.addWidget(vehicle2_group)
        
        # Overall vehicle counts (for backward compatibility and single-lane mode)
        vehicle_group = QGroupBox("Tổng Số Lượng Phương Tiện")
        vehicle_layout = QGridLayout(vehicle_group)
        vehicle_layout.setSpacing(8)
        
        self.lbl_counts = {}
        row = 0
        for vehicle_type in ['motorcycle', 'bicycle', 'car', 'bus', 'truck']:
            label = QLabel(f"{vehicle_names.get(vehicle_type, vehicle_type)}:")
            label.setStyleSheet("font-size: 16px; font-weight: bold;")
            count = QLabel("0")
            count.setStyleSheet("font-size: 20px; font-weight: bold; color: #89b4fa;")
            vehicle_layout.addWidget(label, row, 0)
            vehicle_layout.addWidget(count, row, 1)
            self.lbl_counts[vehicle_type] = count
            row += 1
        
        layout.addWidget(vehicle_group)
        
        layout.addStretch()
        
        return widget
    
    def create_config_tab(self):
        """Create configuration tab content - System info, Calibration params, Density info"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)
        
        # System info
        info_group = QGroupBox("Thông Tin Hệ Thống")
        info_layout = QGridLayout(info_group)
        info_layout.setSpacing(8)
        
        lbl = QLabel("Trạng thái:")
        lbl.setStyleSheet("font-size: 16px; font-weight: bold;")
        info_layout.addWidget(lbl, 0, 0)
        self.lbl_status = QLabel("Chưa tải video")
        self.lbl_status.setStyleSheet("font-size: 16px;")
        info_layout.addWidget(self.lbl_status, 0, 1)
        
        lbl = QLabel("Video:")
        lbl.setStyleSheet("font-size: 16px; font-weight: bold;")
        info_layout.addWidget(lbl, 1, 0)
        self.lbl_video = QLabel("-")
        self.lbl_video.setWordWrap(True)
        self.lbl_video.setStyleSheet("font-size: 16px;")
        info_layout.addWidget(self.lbl_video, 1, 1)
        
        lbl = QLabel("Model AI:")
        lbl.setStyleSheet("font-size: 16px; font-weight: bold;")
        info_layout.addWidget(lbl, 2, 0)
        self.lbl_model = QLabel(self.settings.model.model_path)
        self.lbl_model.setWordWrap(True)
        self.lbl_model.setStyleSheet("font-size: 16px;")
        info_layout.addWidget(self.lbl_model, 2, 1)
        
        lbl = QLabel("Tốc độ xử lý:")
        lbl.setStyleSheet("font-size: 16px; font-weight: bold;")
        info_layout.addWidget(lbl, 3, 0)
        self.lbl_fps = QLabel("-")
        self.lbl_fps.setStyleSheet("font-weight: bold; color: #a6e3a1; font-size: 18px;")
        info_layout.addWidget(self.lbl_fps, 3, 1)
        
        layout.addWidget(info_group)
        
        # Calibration info - Lane 1
        self.calib_lane1_group = QGroupBox("Thông Số Hiệu Chỉnh - Làn 1")
        calib_layout = QGridLayout(self.calib_lane1_group)
        calib_layout.setSpacing(8)
        
        # First parameter label (length/radius/major axis)
        self.lbl_param1_title = QLabel("Chiều dài Ls (m):")
        self.lbl_param1_title.setStyleSheet("font-size: 16px; font-weight: bold;")
        calib_layout.addWidget(self.lbl_param1_title, 0, 0)
        self.lbl_length = QLabel("-")
        self.lbl_length.setStyleSheet("font-size: 16px;")
        calib_layout.addWidget(self.lbl_length, 0, 1)
        
        # Second parameter label (width/minor axis) - hidden for circle
        self.lbl_param2_title = QLabel("Chiều rộng Ws (m):")
        self.lbl_param2_title.setStyleSheet("font-size: 16px; font-weight: bold;")
        calib_layout.addWidget(self.lbl_param2_title, 1, 0)
        self.lbl_width = QLabel("-")
        self.lbl_width.setStyleSheet("font-size: 16px;")
        calib_layout.addWidget(self.lbl_width, 1, 1)
        
        lbl = QLabel("Diện tích DT (m²):")
        lbl.setStyleSheet("font-size: 16px; font-weight: bold;")
        calib_layout.addWidget(lbl, 2, 0)
        self.lbl_area = QLabel("-")
        self.lbl_area.setStyleSheet("font-size: 16px;")
        calib_layout.addWidget(self.lbl_area, 2, 1)
        
        # Edit button for Lane 1
        self.btn_edit_lane1 = QPushButton("Chỉnh Sửa")
        self.btn_edit_lane1.setStyleSheet("font-size: 14px; padding: 5px 10px;")
        self.btn_edit_lane1.clicked.connect(lambda: self.edit_lane_calibration(1))
        self.btn_edit_lane1.setEnabled(False)
        calib_layout.addWidget(self.btn_edit_lane1, 3, 0, 1, 2)
        
        layout.addWidget(self.calib_lane1_group)
        
        # Calibration info - Lane 2 (initially hidden)
        self.calib_lane2_group = QGroupBox("Thông Số Hiệu Chỉnh - Làn 2")
        calib_layout2 = QGridLayout(self.calib_lane2_group)
        calib_layout2.setSpacing(8)
        
        # Lane 2 - First parameter label
        self.lbl_param1_title_lane2 = QLabel("Chiều dài Ls (m):")
        self.lbl_param1_title_lane2.setStyleSheet("font-size: 16px; font-weight: bold;")
        calib_layout2.addWidget(self.lbl_param1_title_lane2, 0, 0)
        self.lbl_length_lane2 = QLabel("-")
        self.lbl_length_lane2.setStyleSheet("font-size: 16px;")
        calib_layout2.addWidget(self.lbl_length_lane2, 0, 1)
        
        # Lane 2 - Second parameter label
        self.lbl_param2_title_lane2 = QLabel("Chiều rộng Ws (m):")
        self.lbl_param2_title_lane2.setStyleSheet("font-size: 16px; font-weight: bold;")
        calib_layout2.addWidget(self.lbl_param2_title_lane2, 1, 0)
        self.lbl_width_lane2 = QLabel("-")
        self.lbl_width_lane2.setStyleSheet("font-size: 16px;")
        calib_layout2.addWidget(self.lbl_width_lane2, 1, 1)
        
        lbl2 = QLabel("Diện tích DT (m²):")
        lbl2.setStyleSheet("font-size: 16px; font-weight: bold;")
        calib_layout2.addWidget(lbl2, 2, 0)
        self.lbl_area_lane2 = QLabel("-")
        self.lbl_area_lane2.setStyleSheet("font-size: 16px;")
        calib_layout2.addWidget(self.lbl_area_lane2, 2, 1)
        
        # Edit button for Lane 2
        self.btn_edit_lane2 = QPushButton("Chỉnh Sửa")
        self.btn_edit_lane2.setStyleSheet("font-size: 14px; padding: 5px 10px;")
        self.btn_edit_lane2.clicked.connect(lambda: self.edit_lane_calibration(2))
        self.btn_edit_lane2.setEnabled(False)
        calib_layout2.addWidget(self.btn_edit_lane2, 3, 0, 1, 2)
        
        self.calib_lane2_group.setVisible(False)  # Hidden by default
        layout.addWidget(self.calib_lane2_group)
        
        # Density info
        density_group = QGroupBox("Mật Độ Giao Thông")
        density_layout = QGridLayout(density_group)
        density_layout.setSpacing(8)
        
        lbl = QLabel("Diện tích chiếm dụng TL:")
        lbl.setStyleSheet("font-size: 16px; font-weight: bold;")
        density_layout.addWidget(lbl, 0, 0)
        self.lbl_occupied = QLabel("-")
        self.lbl_occupied.setStyleSheet("font-size: 16px;")
        density_layout.addWidget(self.lbl_occupied, 0, 1)
        
        lbl = QLabel("Tỉ lệ R (%):")
        lbl.setStyleSheet("font-size: 16px; font-weight: bold;")
        density_layout.addWidget(lbl, 1, 0)
        self.lbl_percentage = QLabel("-")
        self.lbl_percentage.setStyleSheet("font-size: 22px; font-weight: bold; color: #89b4fa;")
        density_layout.addWidget(self.lbl_percentage, 1, 1)
        
        lbl = QLabel("Tình trạng:")
        lbl.setStyleSheet("font-size: 16px; font-weight: bold;")
        density_layout.addWidget(lbl, 2, 0)
        self.lbl_congestion = QLabel("-")
        self.lbl_congestion.setStyleSheet("font-size: 24px; font-weight: bold;")
        density_layout.addWidget(self.lbl_congestion, 2, 1)
        
        layout.addWidget(density_group)
        
        layout.addStretch()
        
        return widget
    
    def setup_menu(self):
        """Setup menu bar"""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("&File")
        
        open_action = QAction("Mở Video", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_video)
        file_menu.addAction(open_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("Thoát", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # View menu
        view_menu = menubar.addMenu("&Hiển Thị")
        
        theme_action = QAction("Chuyển Chế Độ Sáng/Tối", self)
        theme_action.setShortcut("Ctrl+T")
        theme_action.triggered.connect(self.toggle_theme)
        view_menu.addAction(theme_action)
        
        # Settings menu
        settings_menu = menubar.addMenu("&Cài Đặt")
        
        config_action = QAction("Cấu Hình Hệ Thống", self)
        config_action.triggered.connect(self.open_config_dialog)
        settings_menu.addAction(config_action)
    
    def setup_connections(self):
        """Setup signal connections"""
        self.video_widget.frame_processed.connect(self.update_statistics)
        self.video_widget.calibration_complete.connect(self.on_calibration_complete)
        self.video_widget.calibration_cancelled.connect(self.on_calibration_cancelled)
        self.video_widget.position_changed.connect(self.on_video_position_changed)
        
        # Timeline connections
        self.timeline.position_changed.connect(self.on_timeline_seek)
        self.timeline.play_pause_clicked.connect(self.toggle_play)
        
        # Initialize vehicle counts to 0
        for vehicle_type in self.lbl_counts:
            self.lbl_counts[vehicle_type].setText('0')
        
        logger.debug("Signal connections established")
    
    def on_video_position_changed(self, current_frame: int, total_frames: int, fps: float):
        """Handle video position change from video widget"""
        self.timeline.set_total_frames(total_frames, self.video_widget.get_video_fps())
        self.timeline.set_position(current_frame, fps)
        self.lbl_fps.setText(f"{fps:.1f}")
    
    def on_timeline_seek(self, frame_number: int):
        """Handle seek from timeline"""
        self.video_widget.seek_to_frame(frame_number)
        logger.debug(f"Seeked to frame {frame_number}")
    
    def on_video_selected(self, video_path: str):
        """Handle video selection from selector"""
        logger.info(f"Video selected: {video_path}")
        self.load_video(video_path)
        # Switch to main analysis view
        self.stacked_widget.setCurrentIndex(1)
    
    def show_video_selector(self):
        """Switch back to video selector screen"""
        # Stop current video if playing
        if self.is_playing:
            self.stop_video()
        
        # Reset calibration for new video
        self.calibration.reset()
        
        # Refresh video list
        self.video_selector.load_videos()
        
        # Switch to selector
        self.stacked_widget.setCurrentIndex(0)
        self.statusBar.showMessage("Chọn video để bắt đầu phân tích")
    
    def load_video(self, file_path: str):
        """Load a video file"""
        self.video_path = file_path
        self.video_name = os.path.splitext(os.path.basename(file_path))[0]
        
        # Initialize detector and tracker if not done
        if self.detector is None:
            self.initialize_detector_tracker()
        
        # Try to load calibration profile
        has_calibration = False
        if self.calibration.load_profile(self.video_name):
            has_calibration = True
            # Sync UI with loaded profile
            num_lanes = self.calibration.get_num_lanes()
            self.combo_num_lanes.blockSignals(True)  # Prevent triggering on_num_lanes_changed
            self.combo_num_lanes.setCurrentIndex(num_lanes - 1)
            self.combo_num_lanes.blockSignals(False)
            self.lbl_current_lane.setText(f"Làn: {num_lanes}/{num_lanes}")
            # Also sync calibration mode
            mode = self.calibration.get_mode()
            mode_index = {CalibrationMode.POLYGON: 0, CalibrationMode.CIRCLE: 1, CalibrationMode.ELLIPSE: 2}
            self.combo_calib_mode.blockSignals(True)
            self.combo_calib_mode.setCurrentIndex(mode_index.get(mode, 0))
            self.combo_calib_mode.blockSignals(False)
        else:
            # No profile - reset UI to defaults
            self.combo_num_lanes.blockSignals(True)
            self.combo_num_lanes.setCurrentIndex(0)  # Default to 1 lane
            self.combo_num_lanes.blockSignals(False)
            self.lbl_current_lane.setText("Làn: 1/1")
            self.combo_calib_mode.blockSignals(True)
            self.combo_calib_mode.setCurrentIndex(0)  # Default to polygon
            self.combo_calib_mode.blockSignals(False)
            # Reset calibration manager to 1 lane
            self.calibration.set_num_lanes(1)
            self.calibration.set_mode(CalibrationMode.POLYGON)
        
        # Load video
        self.video_widget.load_video(file_path, self.detector, self.tracker)
        
        # Show info message
        if has_calibration:
            QMessageBox.information(
                self,
                "Đã tải cấu hình",
                "Đã tải thông số hiệu chỉnh cho video này."
            )
            self.update_calibration_display()
        
        # Update UI
        self.lbl_video.setText(os.path.basename(file_path))
        self.lbl_status.setText("Đã tải video")
        self.btn_calibrate.setEnabled(True)
        self.btn_play.setEnabled(self.calibration.calibration is not None)
        self.btn_stop.setEnabled(True)
        
        self.statusBar.showMessage(f"Đã mở: {file_path}")
    
    def open_video(self):
        """Open video file via file dialog"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn Video",
            "",
            "File Video (*.mp4 *.avi *.mov *.mkv);;Tất cả File (*.*)"
        )
        
        if file_path:
            self.load_video(file_path)
    
    def initialize_detector_tracker(self):
        """Initialize detector and tracker with current settings"""
        # Use absolute path for model
        model_path = self.settings.model.get_absolute_model_path()
        self.detector = VehicleDetector(
            model_path=model_path,
            conf_threshold=self.settings.model.conf_threshold,
            iou_threshold=self.settings.model.iou_threshold,
            conf_filter=self.settings.model.detection_conf_filter
        )
        
        # Initialize BoT-SORT tracker
        self.tracker = VehicleTracker(
            tracker_type="botsort",
            track_buffer=getattr(self.settings.tracker, 'track_buffer', 30),
            match_thresh=getattr(self.settings.tracker, 'match_thresh', 0.8)
        )
        
        self.statusBar.showMessage("Đã khởi tạo Detector và Tracker (BoT-SORT)")
    
    def on_num_lanes_changed(self, index: int):
        """Handle number of lanes change"""
        num_lanes = index + 1  # index 0 = 1 lane, index 1 = 2 lanes, etc.
        self.calibration.set_num_lanes(num_lanes)
        self.lbl_current_lane.setText(f"Làn: 1/{num_lanes}")
        self.statusBar.showMessage(f"Số làn đường: {num_lanes}")
        logger.info(f"Number of lanes set to: {num_lanes}")
    
    def on_calib_mode_changed(self, index: int):
        """Handle calibration mode change"""
        modes = [CalibrationMode.POLYGON, CalibrationMode.CIRCLE, CalibrationMode.ELLIPSE]
        mode = modes[index]
        self.calibration.set_mode(mode)
        
        # Update status message
        mode_names = {
            CalibrationMode.POLYGON: "Đa giác (4 điểm)",
            CalibrationMode.CIRCLE: "Hình tròn (2 điểm: tâm + bán kính)",
            CalibrationMode.ELLIPSE: "Elip (3 điểm: tâm + 2 trục)"
        }
        self.statusBar.showMessage(f"Chế độ hiệu chỉnh: {mode_names[mode]}")
    
    def start_calibration(self):
        """Start calibration mode"""
        if self.video_path is None:
            QMessageBox.warning(self, "Lỗi", "Vui lòng mở video trước!")
            return
        
        self.is_calibrating = True
        self.video_widget.start_calibration()
        self.btn_calibrate.setText("Đang hiệu chỉnh...")
        self.btn_calibrate.setEnabled(False)
        self.btn_play.setEnabled(False)
        
        # Update current lane display
        num_lanes = self.calibration.get_num_lanes()
        current_lane = self.calibration.get_current_lane()
        self.lbl_current_lane.setText(f"Làn: {current_lane}/{num_lanes}")
        
        # Show instructions based on mode
        mode = self.calibration.get_mode()
        required_points = self.calibration.get_required_points()
        mode_instructions = {
            CalibrationMode.POLYGON: "Nhấn 4 điểm trên video để đánh dấu vùng quan sát",
            CalibrationMode.CIRCLE: "Nhấn 1 điểm TÂM, sau đó 1 điểm trên BÁN KÍNH",
            CalibrationMode.ELLIPSE: "Nhấn 1 điểm TÂM, sau đó 2 điểm trên 2 TRỤC"
        }
        lane_info = f" - Làn {current_lane}/{num_lanes}" if num_lanes > 1 else ""
        self.lbl_status.setText(f"Đang hiệu chỉnh{lane_info} - Nhấn {required_points} điểm")
        self.statusBar.showMessage(mode_instructions.get(mode, "Đang hiệu chỉnh...") + lane_info)
    
    def on_calibration_cancelled(self):
        """Called when calibration is cancelled by user"""
        self.is_calibrating = False
        self.btn_calibrate.setText("Hiệu Chỉnh Vùng Quan Sát")
        self.btn_calibrate.setEnabled(True)
        self.btn_play.setEnabled(self.calibration.calibration is not None)
        self.lbl_status.setText("Đã hủy hiệu chỉnh")
        self.statusBar.showMessage("Hiệu chỉnh đã bị hủy. Nhấn nút Hiệu Chỉnh để thử lại.")
    
    def on_calibration_complete(self, road_length: float, road_width: float):
        """Called when calibration is complete (for one lane or all lanes)"""
        num_lanes = self.calibration.get_num_lanes()
        
        # Check if all lanes are calibrated
        if not self.calibration.is_all_lanes_calibrated():
            # More lanes to calibrate
            current_lane = self.calibration.get_current_lane()
            self.lbl_current_lane.setText(f"Làn: {current_lane}/{num_lanes}")
            self.lbl_status.setText(f"Đang hiệu chỉnh làn {current_lane}/{num_lanes}")
            self.statusBar.showMessage(f"Làn {current_lane-1} hoàn tất! Tiếp tục hiệu chỉnh làn {current_lane}...")
            
            # Continue calibration for next lane
            self.video_widget.is_calibrating = True
            if self.video_widget.current_frame is not None:
                self.video_widget.display_frame(self.video_widget.current_frame)
            return
        
        # All lanes are calibrated
        self.is_calibrating = False
        self.btn_calibrate.setText("Hiệu Chỉnh Lại")
        self.btn_calibrate.setEnabled(True)
        self.btn_play.setEnabled(True)
        
        # Reset lane display
        self.lbl_current_lane.setText(f"Làn: {num_lanes}/{num_lanes}")
        
        # Save calibration profile
        if self.video_name:
            self.calibration.save_profile(self.video_name)
        
        self.update_calibration_display()
        self.lbl_status.setText("Hiệu chỉnh hoàn tất")
        self.statusBar.showMessage("Hiệu chỉnh hoàn tất! Nhấn Phát Video để bắt đầu giám sát.")
        
        # Create message based on calibration mode
        if self.calibration.calibration:
            cal = self.calibration.calibration
            if cal.calibration_mode == "circle":
                # Use stored radii if available
                if cal.radius_outer is not None and cal.radius_inner is not None:
                    msg = f"Hiệu chỉnh hoàn tất!\n\nBán kính ngoài r1: {cal.radius_outer:.1f}m\nBán kính trong r2: {cal.radius_inner:.1f}m\nDiện tích DT: {cal.road_area_meters:.1f}m²"
                else:
                    import math
                    radius_m = math.sqrt(cal.road_area_meters / math.pi)
                    msg = f"Hiệu chỉnh hoàn tất!\n\nBán kính: {radius_m:.1f}m\nDiện tích DT: {cal.road_area_meters:.1f}m²"
            elif cal.calibration_mode == "ellipse":
                msg = f"Hiệu chỉnh hoàn tất!\n\nTrục chính: {road_length:.1f}m\nTrục phụ: {road_width:.1f}m\nDiện tích DT: {cal.road_area_meters:.1f}m²"
            else:
                # Polygon mode with multi-lane info
                if num_lanes > 1:
                    msg = f"Hiệu chỉnh hoàn tất!\n\nSố làn: {num_lanes}\nTổng diện tích DT: {cal.road_area_meters:.1f}m²"
                else:
                    msg = f"Hiệu chỉnh hoàn tất!\n\nChiều dài Ls: {road_length:.1f}m\nChiều rộng Ws: {road_width:.1f}m\nDiện tích DT: {road_length*road_width:.1f}m²"
        else:
            msg = f"Hiệu chỉnh hoàn tất!\n\nChiều dài Ls: {road_length:.1f}m\nChiều rộng Ws: {road_width:.1f}m\nDiện tích DT: {road_length*road_width:.1f}m²"
        
        QMessageBox.information(self, "Hoàn Tất", msg)
    
    def update_calibration_display(self):
        """Update calibration display based on calibration mode and number of lanes"""
        if self.calibration.calibration:
            cal = self.calibration.calibration
            num_lanes = getattr(cal, 'num_lanes', 1)
            lanes = getattr(cal, 'lanes', None)
            
            # Update Lane 1 title based on number of lanes
            if num_lanes > 1:
                self.calib_lane1_group.setTitle("Thông Số Hiệu Chỉnh - Làn 1")
            else:
                self.calib_lane1_group.setTitle("Thông Số Hiệu Chỉnh")
            
            # Update labels based on calibration mode for Lane 1
            if cal.calibration_mode == "circle":
                # Circle mode - show outer and inner radii
                if cal.radius_outer is not None and cal.radius_inner is not None:
                    self.lbl_param1_title.setText("Bán kính ngoài r1 (m):")
                    self.lbl_param2_title.setText("Bán kính trong r2 (m):")
                    self.lbl_length.setText(f"{cal.radius_outer:.2f} m")
                    self.lbl_param2_title.setVisible(True)
                    self.lbl_width.setVisible(True)
                    self.lbl_width.setText(f"{cal.radius_inner:.2f} m")
                else:
                    # Legacy: single radius from area
                    self.lbl_param1_title.setText("Bán kính (m):")
                    import math
                    radius_m = math.sqrt(cal.road_area_meters / math.pi)
                    self.lbl_length.setText(f"{radius_m:.2f} m")
                    self.lbl_param2_title.setVisible(False)
                    self.lbl_width.setVisible(False)
            elif cal.calibration_mode == "ellipse":
                # Ellipse mode - show semi-major and semi-minor axes
                self.lbl_param1_title.setText("Trục chính (m):")
                self.lbl_param2_title.setText("Trục phụ (m):")
                # Use length as semi-major, width as semi-minor
                self.lbl_length.setText(f"{cal.road_length_meters:.2f} m")
                self.lbl_param2_title.setVisible(True)
                self.lbl_width.setVisible(True)
                self.lbl_width.setText(f"{cal.road_width_meters:.2f} m")
            else:
                # Polygon mode - show length and width
                self.lbl_param1_title.setText("Chiều dài Ls (m):")
                self.lbl_param2_title.setText("Chiều rộng Ws (m):")
                
                # If multi-lane with lanes data, show lane 1 specific data
                if lanes and len(lanes) >= 1:
                    lane1 = lanes[0]
                    self.lbl_length.setText(f"{lane1.get('road_length_meters', cal.road_length_meters):.2f} m")
                    self.lbl_width.setText(f"{lane1.get('road_width_meters', cal.road_width_meters):.2f} m")
                    self.lbl_area.setText(f"{lane1.get('road_area_meters', cal.road_area_meters):.2f} m²")
                else:
                    self.lbl_length.setText(f"{cal.road_length_meters:.2f} m")
                    self.lbl_width.setText(f"{cal.road_width_meters:.2f} m")
                    self.lbl_area.setText(f"{cal.road_area_meters:.2f} m²")
                
                self.lbl_param2_title.setVisible(True)
                self.lbl_width.setVisible(True)
            
            # Update area for non-polygon modes
            if cal.calibration_mode != "polygon" or not lanes or len(lanes) < 1:
                self.lbl_area.setText(f"{cal.road_area_meters:.2f} m²")
            
            # Handle Lane 2 display
            if num_lanes >= 2 and lanes and len(lanes) >= 2:
                self.calib_lane2_group.setVisible(True)
                lane2 = lanes[1]
                
                # Update Lane 2 labels based on mode
                if cal.calibration_mode == "circle":
                    self.lbl_param1_title_lane2.setText("Bán kính ngoài r1 (m):")
                    self.lbl_param2_title_lane2.setText("Bán kính trong r2 (m):")
                    self.lbl_length_lane2.setText(f"{lane2.get('road_length_meters', 0):.2f} m")
                    self.lbl_width_lane2.setText(f"{lane2.get('road_width_meters', 0):.2f} m")
                elif cal.calibration_mode == "ellipse":
                    self.lbl_param1_title_lane2.setText("Trục chính (m):")
                    self.lbl_param2_title_lane2.setText("Trục phụ (m):")
                    self.lbl_length_lane2.setText(f"{lane2.get('road_length_meters', 0):.2f} m")
                    self.lbl_width_lane2.setText(f"{lane2.get('road_width_meters', 0):.2f} m")
                else:
                    self.lbl_param1_title_lane2.setText("Chiều dài Ls (m):")
                    self.lbl_param2_title_lane2.setText("Chiều rộng Ws (m):")
                    self.lbl_length_lane2.setText(f"{lane2.get('road_length_meters', 0):.2f} m")
                    self.lbl_width_lane2.setText(f"{lane2.get('road_width_meters', 0):.2f} m")
                
                self.lbl_area_lane2.setText(f"{lane2.get('road_area_meters', 0):.2f} m²")
                self.btn_edit_lane2.setEnabled(True)
            else:
                self.calib_lane2_group.setVisible(False)
                self.btn_edit_lane2.setEnabled(False)
            
            # Enable edit button for Lane 1
            self.btn_edit_lane1.setEnabled(True)
        else:
            # No calibration - disable edit buttons
            self.btn_edit_lane1.setEnabled(False)
            self.btn_edit_lane2.setEnabled(False)
    
    def edit_lane_calibration(self, lane_number: int):
        """Edit calibration parameters for a specific lane"""
        if not self.calibration.calibration:
            QMessageBox.warning(self, "Lỗi", "Chưa có dữ liệu hiệu chỉnh!")
            return
        
        cal = self.calibration.calibration
        mode = cal.calibration_mode
        lanes = getattr(cal, 'lanes', None)
        
        # Get current values for this lane
        if lanes and len(lanes) >= lane_number:
            lane_data = lanes[lane_number - 1]
            current_length = lane_data.get('road_length_meters', cal.road_length_meters)
            current_width = lane_data.get('road_width_meters', cal.road_width_meters)
        else:
            current_length = cal.road_length_meters
            current_width = cal.road_width_meters
        
        # Determine labels based on mode
        if mode in ("circle", "ellipse"):
            param1_label = "Bán kính ngoài r1 (m):"
            param2_label = "Bán kính trong r2 (m):"
            title = f"Chỉnh Sửa Thông Số Vòng Xoay - Làn {lane_number}"
        else:
            param1_label = "Chiều dài Ls (m):"
            param2_label = "Chiều rộng Ws (m):"
            title = f"Chỉnh Sửa Thông Số - Làn {lane_number}"
        
        # Ask for first parameter
        new_length, ok = QInputDialog.getDouble(
            self, title, param1_label,
            current_length, 0.1, 1000.0, 2
        )
        if not ok:
            return
        
        # Ask for second parameter
        if mode in ("circle", "ellipse"):
            # For circle/ellipse, r2 must be less than r1
            new_width, ok = QInputDialog.getDouble(
                self, title, f"{param2_label}\n(Phải nhỏ hơn r1 = {new_length:.2f}m)",
                current_width, 0.0, new_length - 0.1, 2
            )
        else:
            new_width, ok = QInputDialog.getDouble(
                self, title, param2_label,
                current_width, 0.1, 500.0, 2
            )
        if not ok:
            return
        
        # Update calibration
        success = self.calibration.update_lane_parameters(
            lane_number, new_length, new_width
        )
        
        if success:
            # Save profile
            if self.video_name:
                self.calibration.save_profile(self.video_name)
            
            # Update display
            self.update_calibration_display()
            
            QMessageBox.information(
                self, "Thành Công",
                f"Đã cập nhật thông số làn {lane_number}!"
            )
        else:
            QMessageBox.warning(
                self, "Lỗi",
                f"Không thể cập nhật thông số làn {lane_number}!"
            )
    
    def toggle_play(self):
        """Toggle play/pause"""
        if not self.calibration.calibration:
            QMessageBox.warning(self, "Lỗi", "Vui lòng hiệu chỉnh vùng quan sát trước!")
            return
        
        if self.is_playing:
            self.video_widget.pause()
            self.btn_play.setText("Tiếp Tục Phát")
            self.lbl_status.setText("Tạm dừng")
        else:
            self.video_widget.play()
            self.btn_play.setText("Tạm Dừng")
            self.lbl_status.setText("Đang giám sát")
        
        self.is_playing = not self.is_playing
    
    def stop_video(self):
        """Stop video"""
        self.video_widget.stop()
        self.is_playing = False
        self.btn_play.setText("Phát Video")
        self.btn_play.setEnabled(self.calibration.calibration is not None)
        self.lbl_status.setText("Đã dừng")
        self.statusBar.showMessage("Đã dừng phân tích video")
        
        # Reset statistics display
        for vehicle_type in self.lbl_counts:
            self.lbl_counts[vehicle_type].setText('0')
        self.lbl_occupied.setText('-')
        self.lbl_percentage.setText('-')
        self.lbl_congestion.setText('-')
    
    def update_statistics(self, stats: dict):
        """Update statistics display"""
        # Update vehicle counts - always update all types
        vehicle_counts = {}
        if 'vehicle_counts' in stats:
            # First reset all to 0
            for vehicle_type in self.lbl_counts:
                self.lbl_counts[vehicle_type].setText('0')
            
            # Then update with actual counts
            for vehicle_type, count in stats['vehicle_counts'].items():
                vehicle_counts[vehicle_type] = count
                if vehicle_type in self.lbl_counts:
                    self.lbl_counts[vehicle_type].setText(str(count))
        
        # Update density info
        density_percentage = 0
        if 'occupied_area' in stats:
            self.lbl_occupied.setText(f"{stats['occupied_area']:.2f} m2")
        
        if 'density_percentage' in stats:
            density_percentage = stats['density_percentage']
            self.lbl_percentage.setText(f"{density_percentage:.1f}%")
        
        # Update per-lane vehicle counts and density display
        if 'lane_densities' in stats and stats['lane_densities']:
            lane_densities = stats['lane_densities']
            
            # Lane 1
            if 'lane1' in lane_densities:
                lane1_info = lane_densities['lane1']
                
                # Update Lane 1 vehicle counts
                for vehicle_type in self.lbl_lane1_counts:
                    count = lane1_info.get('vehicle_counts', {}).get(vehicle_type, 0)
                    self.lbl_lane1_counts[vehicle_type].setText(str(count))
                
                # Update Lane 1 status
                status1 = lane1_info['congestion_status']
                color1 = lane1_info['congestion_color']
                color1_str = f"rgb({color1[2]}, {color1[1]}, {color1[0]})"
                self.lbl_lane1_status.setText(status1)
                self.lbl_lane1_status.setStyleSheet(
                    f"font-size: 16px; font-weight: bold; color: {color1_str};"
                )
                
                # Update Lane 1 ratio
                lane1_ratio = lane1_info.get('density_percentage', 0)
                self.lbl_lane1_ratio.setText(f"{lane1_ratio:.1f}%")
                self.lbl_lane1_ratio.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {color1_str};")
            else:
                # Reset Lane 1
                for vehicle_type in self.lbl_lane1_counts:
                    self.lbl_lane1_counts[vehicle_type].setText('0')
                self.lbl_lane1_status.setText("-")
                self.lbl_lane1_status.setStyleSheet("font-size: 16px; font-weight: bold;")
                self.lbl_lane1_ratio.setText("0.0%")
                self.lbl_lane1_ratio.setStyleSheet("font-size: 14px; font-weight: bold; color: #89b4fa;")
            
            # Lane 2
            if 'lane2' in lane_densities:
                lane2_info = lane_densities['lane2']
                
                # Update Lane 2 vehicle counts
                for vehicle_type in self.lbl_lane2_counts:
                    count = lane2_info.get('vehicle_counts', {}).get(vehicle_type, 0)
                    self.lbl_lane2_counts[vehicle_type].setText(str(count))
                
                # Update Lane 2 status
                status2 = lane2_info['congestion_status']
                color2 = lane2_info['congestion_color']
                color2_str = f"rgb({color2[2]}, {color2[1]}, {color2[0]})"
                self.lbl_lane2_status.setText(status2)
                self.lbl_lane2_status.setStyleSheet(
                    f"font-size: 16px; font-weight: bold; color: {color2_str};"
                )
                
                # Update Lane 2 ratio
                lane2_ratio = lane2_info.get('density_percentage', 0)
                self.lbl_lane2_ratio.setText(f"{lane2_ratio:.1f}%")
                self.lbl_lane2_ratio.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {color2_str};")
            else:
                # Reset Lane 2
                for vehicle_type in self.lbl_lane2_counts:
                    self.lbl_lane2_counts[vehicle_type].setText('0')
                self.lbl_lane2_status.setText("-")
                self.lbl_lane2_status.setStyleSheet("font-size: 16px; font-weight: bold;")
                self.lbl_lane2_ratio.setText("0.0%")
                self.lbl_lane2_ratio.setStyleSheet("font-size: 14px; font-weight: bold; color: #89b4fa;")
        else:
            # Single lane mode - show all in Lane 1
            if 'vehicle_counts' in stats:
                for vehicle_type, count in stats['vehicle_counts'].items():
                    if vehicle_type in self.lbl_lane1_counts:
                        self.lbl_lane1_counts[vehicle_type].setText(str(count))
            
            # Reset Lane 2
            for vehicle_type in self.lbl_lane2_counts:
                self.lbl_lane2_counts[vehicle_type].setText('0')
            
            # Update Lane 1 status with overall status
            if 'congestion_status' in stats:
                status = stats['congestion_status']
                color = stats.get('congestion_color', (0, 0, 0))
                color_str = f"rgb({color[2]}, {color[1]}, {color[0]})"
                self.lbl_lane1_status.setText(status)
                self.lbl_lane1_status.setStyleSheet(
                    f"font-size: 16px; font-weight: bold; color: {color_str};"
                )
                # Update Lane 1 ratio in single lane mode
                self.lbl_lane1_ratio.setText(f"{density_percentage:.1f}%")
                self.lbl_lane1_ratio.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {color_str};")
            
            self.lbl_lane2_status.setText("-")
            self.lbl_lane2_status.setStyleSheet("font-size: 16px; font-weight: bold;")
            self.lbl_lane2_ratio.setText("0.0%")
            self.lbl_lane2_ratio.setStyleSheet("font-size: 14px; font-weight: bold; color: #89b4fa;")
        
        # Update main density status display
        if 'congestion_status' in stats:
            status = stats['congestion_status']
            color = stats.get('congestion_color', (0, 0, 0))
            # Convert BGR to RGB for Qt
            color_str = f"rgb({color[2]}, {color[1]}, {color[0]})"
            self.lbl_congestion.setText(status)
            self.lbl_congestion.setStyleSheet(
                f"font-size: 20px; font-weight: bold; color: {color_str};"
            )
            
            # Update density status display (Thấp/Trung bình/Cao with percentage)
            self.update_density_status(density_percentage, status, color)
        else:
            # No congestion status - still update based on percentage
            if density_percentage < 30:
                status = 'Thấp'
                color = (0, 255, 0)  # Green
            elif density_percentage < 80:
                status = 'Trung bình'
                color = (0, 165, 255)  # Orange
            else:
                status = 'Cao'
                color = (0, 0, 255)  # Red
            self.update_density_status(density_percentage, status, color)
    
    def update_density_status(self, percentage: float, status: str, color: tuple):
        """Update density status display with Thấp/Trung bình/Cao and percentage"""
        # Status is now directly Thấp/Trung bình/Cao from settings
        display_status = status if status in ['Thấp', 'Trung bình', 'Cao'] else '--'
        
        # Set status label with appropriate color
        if display_status == 'Thấp':
            bg_color = '#4caf50'  # Green
        elif display_status == 'Trung bình':
            bg_color = '#ff9800'  # Orange
        elif display_status == 'Cao':
            bg_color = '#f44336'  # Red
        else:
            bg_color = '#6c7086'  # Gray
        
        self.lbl_density_status.setText(display_status)
        self.lbl_density_status.setStyleSheet(f"""
            font-size: 24px;
            font-weight: bold;
            padding: 10px 20px;
            border-radius: 8px;
            background-color: {bg_color};
            color: white;
        """)
        
        # Update percentage label
        self.lbl_density_percent.setText(f"{percentage:.1f}%")
        # Color based on percentage
        if percentage < 30:
            percent_color = '#4caf50'  # Green
        elif percentage < 60:
            percent_color = '#ff9800'  # Orange
        else:
            percent_color = '#f44336'  # Red
        self.lbl_density_percent.setStyleSheet(f"""
            font-size: 28px;
            font-weight: bold;
            color: {percent_color};
        """)
    
    def open_config_dialog(self):
        """Open configuration dialog"""
        dialog = ConfigDialog(self.settings, self)
        dialog.apply_theme(self.is_dark_theme)
        if dialog.exec():
            # Update model path display
            self.lbl_model.setText(self.settings.model.model_path)
            
            # Settings were saved, reinitialize if needed
            if self.detector or self.tracker:
                reply = QMessageBox.question(
                    self,
                    "Khởi tạo lại?",
                    f"Cài đặt đã thay đổi.\nTracker: {self.settings.tracker.tracker_type}\n\nKhởi tạo lại Detector/Tracker?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    self.initialize_detector_tracker()
                    self.statusBar.showMessage(f"Đã áp dụng cài đặt mới (Tracker: {self.settings.tracker.tracker_type})")
            else:
                # Update display even if not reinitializing
                self.statusBar.showMessage("Đã lưu cài đặt")
    
    def show_about(self):
        """Show about dialog"""
        QMessageBox.about(
            self,
            "Giới Thiệu",
            "<h2>Hệ Thống Giám Sát Giao Thông</h2>"
            "<p><b>Hệ Thống Giám Sát & Cảnh Báo Ùn Tắc</b></p>"
            "<p>Phiên bản 2.0.0</p>"
            "<p>Sử dụng YOLO v11 và BoT-SORT để phát hiện và theo dõi phương tiện.</p>"
            "<p>Tính toán mật độ giao thông dựa trên diện tích chiếm dụng.</p>"
            "<hr>"
            "<p>Công thức: R = (TL / DT) x 100</p>"
            "<p>© 2025 - Đồ Án Tốt Nghiệp</p>"
        )
    
    def closeEvent(self, event):
        """Handle window close event"""
        # Check if calibrating
        if self.is_calibrating:
            reply = QMessageBox.question(
                self,
                "Xác Nhận Thoát",
                "Đang trong quá trình hiệu chỉnh. Bạn có chắc muốn thoát?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return
            else:
                # Reset calibration state
                self.is_calibrating = False
                self.calibration.reset()
        
        if self.is_playing:
            reply = QMessageBox.question(
                self,
                "Xác Nhận Thoát",
                "Video đang chạy. Bạn có chắc muốn thoát?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return
        
        # Clean up video widget
        if hasattr(self, 'video_widget'):
            self.video_widget.is_calibrating = False
        
        event.accept()

    def toggle_theme(self):
        """Toggle between dark and light theme"""
        self.is_dark_theme = not self.is_dark_theme
        self.apply_theme()
        
        # Update video selector theme
        if hasattr(self, 'video_selector'):
            self.video_selector.apply_theme(self.is_dark_theme)
            
        # Update timeline theme
        if hasattr(self, 'timeline'):
            self.timeline.apply_theme(self.is_dark_theme)
        
        # Update control buttons theme
        self.apply_control_buttons_theme()
            
        self.statusBar.showMessage(f"Đã chuyển sang chế độ {'Tối' if self.is_dark_theme else 'Sáng'}")
    
    def apply_control_buttons_theme(self):
        """Apply theme to control buttons"""
        if self.is_dark_theme:
            # Dark theme styles
            combobox_style = """
                QComboBox {
                    background-color: #45475a;
                    color: #cdd6f4;
                    border: 1px solid #585b70;
                    border-radius: 6px;
                    padding: 8px 12px;
                    font-size: 14px;
                }
                QComboBox:hover {
                    border-color: #89b4fa;
                }
                QComboBox::drop-down {
                    border: none;
                    padding-right: 8px;
                }
                QComboBox::down-arrow {
                    image: none;
                    border-left: 5px solid transparent;
                    border-right: 5px solid transparent;
                    border-top: 6px solid #cdd6f4;
                    margin-right: 8px;
                }
                QComboBox QAbstractItemView {
                    background-color: #313244;
                    color: #cdd6f4;
                    selection-background-color: #585b70;
                    border: 1px solid #585b70;
                    border-radius: 4px;
                }
            """
            label_style = "color: #cdd6f4; font-size: 14px;"
            lane_label_style = """
                color: #a6e3a1;
                font-size: 14px;
                font-weight: bold;
                background-color: #313244;
                padding: 8px 16px;
                border-radius: 6px;
            """
            back_btn_style = """
                QPushButton {
                    background-color: #45475a;
                    color: white;
                    border: 1px solid #585b70;
                    border-radius: 6px;
                    font-weight: bold;
                    font-size: 14px;
                    padding: 8px 16px;
                }
                QPushButton:hover {
                    background-color: #585b70;
                }
            """
            calibrate_btn_style = """
                QPushButton {
                    background-color: #fab387;
                    color: #1e1e2e;
                    border: none;
                    border-radius: 6px;
                    font-weight: bold;
                    font-size: 14px;
                    padding: 8px 16px;
                }
                QPushButton:hover {
                    background-color: #f9c096;
                }
                QPushButton:disabled {
                    background-color: #313244;
                    color: #6c7086;
                }
            """
            play_btn_style = """
                QPushButton {
                    background-color: #a6e3a1;
                    color: #1e1e2e;
                    border: none;
                    border-radius: 6px;
                    font-weight: bold;
                    font-size: 14px;
                    padding: 8px 16px;
                }
                QPushButton:hover {
                    background-color: #94e2d5;
                }
                QPushButton:disabled {
                    background-color: #313244;
                    color: #6c7086;
                }
            """
            stop_btn_style = """
                QPushButton {
                    background-color: #f38ba8;
                    color: #1e1e2e;
                    border: none;
                    border-radius: 6px;
                    font-weight: bold;
                    font-size: 14px;
                    padding: 8px 16px;
                }
                QPushButton:hover {
                    background-color: #eba0ac;
                }
                QPushButton:disabled {
                    background-color: #313244;
                    color: #6c7086;
                }
            """
        else:
            # Light theme styles
            combobox_style = """
                QComboBox {
                    background-color: #ffffff;
                    color: #333333;
                    border: 1px solid #cccccc;
                    border-radius: 6px;
                    padding: 8px 12px;
                    font-size: 14px;
                }
                QComboBox:hover {
                    border-color: #1976D2;
                }
                QComboBox::drop-down {
                    border: none;
                    padding-right: 8px;
                }
                QComboBox::down-arrow {
                    image: none;
                    border-left: 5px solid transparent;
                    border-right: 5px solid transparent;
                    border-top: 6px solid #333333;
                    margin-right: 8px;
                }
                QComboBox QAbstractItemView {
                    background-color: #ffffff;
                    color: #333333;
                    selection-background-color: #e3f2fd;
                    border: 1px solid #cccccc;
                    border-radius: 4px;
                }
            """
            label_style = "color: #333333; font-size: 14px;"
            lane_label_style = """
                color: #2e7d32;
                font-size: 14px;
                font-weight: bold;
                background-color: #e8f5e9;
                padding: 8px 16px;
                border-radius: 6px;
            """
            back_btn_style = """
                QPushButton {
                    background-color: #757575;
                    color: white;
                    border: none;
                    border-radius: 6px;
                    font-weight: bold;
                    font-size: 14px;
                    padding: 8px 16px;
                }
                QPushButton:hover {
                    background-color: #616161;
                }
            """
            calibrate_btn_style = """
                QPushButton {
                    background-color: #ff9800;
                    color: #ffffff;
                    border: none;
                    border-radius: 6px;
                    font-weight: bold;
                    font-size: 14px;
                    padding: 8px 16px;
                }
                QPushButton:hover {
                    background-color: #f57c00;
                }
                QPushButton:disabled {
                    background-color: #e0e0e0;
                    color: #9e9e9e;
                }
            """
            play_btn_style = """
                QPushButton {
                    background-color: #4caf50;
                    color: #ffffff;
                    border: none;
                    border-radius: 6px;
                    font-weight: bold;
                    font-size: 14px;
                    padding: 8px 16px;
                }
                QPushButton:hover {
                    background-color: #388e3c;
                }
                QPushButton:disabled {
                    background-color: #e0e0e0;
                    color: #9e9e9e;
                }
            """
            stop_btn_style = """
                QPushButton {
                    background-color: #f44336;
                    color: #ffffff;
                    border: none;
                    border-radius: 6px;
                    font-weight: bold;
                    font-size: 14px;
                    padding: 8px 16px;
                }
                QPushButton:hover {
                    background-color: #d32f2f;
                }
                QPushButton:disabled {
                    background-color: #e0e0e0;
                    color: #9e9e9e;
                }
            """
        
        # Apply styles to widgets
        if hasattr(self, 'combo_num_lanes'):
            self.combo_num_lanes.setStyleSheet(combobox_style)
        if hasattr(self, 'combo_calib_mode'):
            self.combo_calib_mode.setStyleSheet(combobox_style)
        if hasattr(self, 'lbl_current_lane'):
            self.lbl_current_lane.setStyleSheet(lane_label_style)
        if hasattr(self, 'lbl_lane'):
            self.lbl_lane.setStyleSheet(label_style)
        if hasattr(self, 'lbl_mode'):
            self.lbl_mode.setStyleSheet(label_style)
        if hasattr(self, 'btn_back'):
            self.btn_back.setStyleSheet(back_btn_style)
        if hasattr(self, 'btn_calibrate'):
            self.btn_calibrate.setStyleSheet(calibrate_btn_style)
        if hasattr(self, 'btn_play'):
            self.btn_play.setStyleSheet(play_btn_style)
        if hasattr(self, 'btn_stop'):
            self.btn_stop.setStyleSheet(stop_btn_style)

    def apply_theme(self):
        """Apply current theme"""
        if self.is_dark_theme:
            self.apply_dark_theme()
        else:
            self.apply_light_theme()

    def apply_dark_theme(self):
        """Apply modern dark theme"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e2e;
                color: #e0e0e0;
                font-family: 'Inter', sans-serif;
            }
            QWidget {
                background-color: #1e1e2e;
                color: #e0e0e0;
                font-size: 14px;
                font-family: 'Inter', sans-serif;
            }
            QMenuBar {
                background-color: #2a2a3c;
                color: #e0e0e0;
                border-bottom: 1px solid #3e3e5e;
                padding: 6px;
                font-size: 14px;
            }
            QMenuBar::item:selected {
                background-color: #3e3e5e;
                color: #ffffff;
            }
            QMenu {
                background-color: #2a2a3c;
                color: #e0e0e0;
                border: 1px solid #3e3e5e;
                font-size: 14px;
            }
            QMenu::item:selected {
                background-color: #3e3e5e;
                color: #ffffff;
            }
            QGroupBox {
                font-weight: bold;
                font-size: 16px;
                border: 1px solid #3e3e5e;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 12px;
                background-color: #232334;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px;
                color: #89b4fa;
                font-size: 16px;
            }
            QTabWidget::pane {
                border: 1px solid #3e3e5e;
                border-radius: 8px;
                background-color: #232334;
            }
            QTabBar::tab {
                background-color: #2a2a3c;
                color: #a0a0a0;
                padding: 10px 20px;
                margin-right: 2px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-size: 14px;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background-color: #3e3e5e;
                color: #ffffff;
                border-bottom: 2px solid #89b4fa;
            }
            QLabel {
                color: #e0e0e0;
                font-size: 14px;
            }
            QStatusBar {
                background-color: #2a2a3c;
                color: #89b4fa;
                border-top: 1px solid #3e3e5e;
                font-size: 14px;
                padding: 5px;
            }
            QPushButton {
                background-color: #313244;
                color: #ffffff;
                border: 1px solid #45475a;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #45475a;
                border: 1px solid #585b70;
            }
            QPushButton:pressed {
                background-color: #585b70;
            }
            QPushButton:disabled {
                background-color: #181825;
                color: #6c7086;
                border: 1px solid #313244;
            }
            QScrollArea {
                border: none;
                background-color: #1e1e2e;
            }
        """)

    def apply_light_theme(self):
        """Apply light theme"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
                color: #333333;
                font-family: 'Inter', sans-serif;
            }
            QWidget {
                background-color: #f5f5f5;
                color: #333333;
                font-size: 14px;
                font-family: 'Inter', sans-serif;
            }
            QMenuBar {
                background-color: #ffffff;
                color: #333333;
                border-bottom: 1px solid #e0e0e0;
                padding: 6px;
                font-size: 14px;
            }
            QMenuBar::item:selected {
                background-color: #e3f2fd;
                color: #1976D2;
            }
            QMenu {
                background-color: #ffffff;
                color: #333333;
                border: 1px solid #e0e0e0;
                font-size: 14px;
            }
            QMenu::item:selected {
                background-color: #e3f2fd;
                color: #1976D2;
            }
            QGroupBox {
                font-weight: bold;
                font-size: 16px;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 12px;
                background-color: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px;
                color: #1976D2;
                font-size: 16px;
            }
            QTabWidget::pane {
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                background-color: #ffffff;
            }
            QTabBar::tab {
                background-color: #e3f2fd;
                color: #333333;
                padding: 10px 20px;
                margin-right: 2px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-size: 14px;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background-color: #1976D2;
                color: #ffffff;
            }
            QLabel {
                color: #333333;
                font-size: 14px;
            }
            QStatusBar {
                background-color: #ffffff;
                color: #1976D2;
                border-top: 1px solid #e0e0e0;
                font-size: 14px;
                padding: 5px;
            }
            QPushButton {
                background-color: #1976D2;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #1565C0;
            }
            QPushButton:pressed {
                background-color: #0D47A1;
            }
            QPushButton:disabled {
                background-color: #BDBDBD;
                color: #757575;
            }
            QScrollArea {
                border: none;
                background-color: #f5f5f5;
            }
        """)
