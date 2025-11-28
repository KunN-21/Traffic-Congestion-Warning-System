"""
Main Window for Traffic Congestion Monitoring System
PyQt6-based GUI application with enhanced features
"""

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QFileDialog, QMessageBox,
                             QGroupBox, QGridLayout, QStatusBar, QTabWidget,
                             QStackedWidget, QComboBox)
from PyQt6.QtGui import QAction
import os
import time

from .video_widget import VideoWidget
from .config_dialog import ConfigDialog
from .chart_widget import TrafficChartPanel, MiniDensityGauge
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
        self.setWindowTitle("Hệ Thống Giám Sát Giao Thông - Traffic Monitoring System")
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
        self.calibration = CalibrationManager(self.settings.calibration.profiles_dir)
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
        layout.setSpacing(15)
        
        # Back to video list button
        self.btn_back = QPushButton("Quay Lại Danh Sách")
        self.btn_back.setMinimumHeight(50)
        self.btn_back.setStyleSheet("""
            QPushButton {
                background-color: #45475a;
                color: white;
                border: 1px solid #585b70;
                border-radius: 6px;
                font-weight: bold;
                font-size: 15px;
                padding: 12px 24px;
            }
            QPushButton:hover {
                background-color: #585b70;
            }
        """)
        self.btn_back.clicked.connect(self.show_video_selector)
        layout.addWidget(self.btn_back)
        
        # Calibration mode selector
        mode_layout = QHBoxLayout()
        mode_label = QLabel("Chế độ:")
        mode_label.setStyleSheet("color: #cdd6f4; font-size: 14px;")
        self.combo_calib_mode = QComboBox()
        self.combo_calib_mode.addItems(["Đa Giác (4 điểm)", "Hình Tròn (vòng xoay)", "Elip (vòng xoay dẹt)"])
        self.combo_calib_mode.setStyleSheet("""
            QComboBox {
                background-color: #45475a;
                color: #cdd6f4;
                border: 1px solid #585b70;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 14px;
                min-width: 180px;
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
        """)
        self.combo_calib_mode.currentIndexChanged.connect(self.on_calib_mode_changed)
        mode_layout.addWidget(mode_label)
        mode_layout.addWidget(self.combo_calib_mode)
        mode_layout.addStretch()
        layout.addLayout(mode_layout)
        
        # Calibration button
        self.btn_calibrate = QPushButton("Hiệu Chỉnh Vùng Quan Sát")
        self.btn_calibrate.setMinimumHeight(50)
        self.btn_calibrate.setEnabled(False)
        self.btn_calibrate.setStyleSheet("""
            QPushButton {
                background-color: #fab387;
                color: #1e1e2e;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 15px;
                padding: 12px 24px;
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
        
        # Traffic Light ROI button
        self.btn_traffic_light = QPushButton("Chọn Vùng Đèn Giao Thông")
        self.btn_traffic_light.setMinimumHeight(50)
        self.btn_traffic_light.setEnabled(False)
        self.btn_traffic_light.setStyleSheet("""
            QPushButton {
                background-color: #cba6f7;
                color: #1e1e2e;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 15px;
                padding: 12px 24px;
            }
            QPushButton:hover {
                background-color: #ddb6ff;
            }
            QPushButton:disabled {
                background-color: #313244;
                color: #6c7086;
            }
        """)
        self.btn_traffic_light.clicked.connect(self.start_traffic_light_calibration)
        layout.addWidget(self.btn_traffic_light)
        
        # Play/Pause button
        self.btn_play = QPushButton("Phát Video")
        self.btn_play.setMinimumHeight(50)
        self.btn_play.setEnabled(False)
        self.btn_play.setStyleSheet("""
            QPushButton {
                background-color: #a6e3a1;
                color: #1e1e2e;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 15px;
                padding: 12px 24px;
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
        self.btn_stop.setMinimumHeight(50)
        self.btn_stop.setEnabled(False)
        self.btn_stop.setStyleSheet("""
            QPushButton {
                background-color: #f38ba8;
                color: #1e1e2e;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 15px;
                padding: 12px 24px;
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
        """Create right panel with statistics and charts"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)
        
        # Density Gauge at top
        gauge_group = QGroupBox("Mật Độ Giao Thông")
        gauge_layout = QHBoxLayout(gauge_group)
        self.density_gauge = MiniDensityGauge()
        self.density_gauge.apply_theme(self.is_dark_theme)
        gauge_layout.addWidget(self.density_gauge)
        gauge_layout.addStretch()
        layout.addWidget(gauge_group)
        
        # Tab widget for different info sections
        tabs = QTabWidget()
        
        # Tab 1: Statistics
        stats_tab = self.create_stats_tab()
        tabs.addTab(stats_tab, "Thống Kê")
        
        # Tab 2: Charts
        self.chart_panel = TrafficChartPanel()
        self.chart_panel.apply_theme(self.is_dark_theme)
        tabs.addTab(self.chart_panel, "Biểu Đồ")
        
        layout.addWidget(tabs, stretch=1)
        
        return widget
    
    def create_stats_tab(self):
        """Create statistics tab content"""
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
        
        # Calibration info
        calib_group = QGroupBox("Thông Số Hiệu Chỉnh")
        calib_layout = QGridLayout(calib_group)
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
        
        layout.addWidget(calib_group)
        
        # Vehicle counts
        vehicle_group = QGroupBox("Số Lượng Phương Tiện")
        vehicle_layout = QGridLayout(vehicle_group)
        vehicle_layout.setSpacing(8)
        
        vehicle_names = {
            'motorcycle': 'Xe máy',
            'bicycle': 'Xe đạp', 
            'car': 'Ô tô',
            'bus': 'Xe buýt',
            'truck': 'Xe tải'
        }
        
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
        
        # Help menu
        help_menu = menubar.addMenu("&Trợ Giúp")
        
        about_action = QAction("Về Phần Mềm", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def setup_connections(self):
        """Setup signal connections"""
        self.video_widget.frame_processed.connect(self.update_statistics)
        self.video_widget.calibration_complete.connect(self.on_calibration_complete)
        self.video_widget.calibration_cancelled.connect(self.on_calibration_cancelled)
        self.video_widget.traffic_light_calibration_complete.connect(self.on_traffic_light_calibration_complete)
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
        has_traffic_light = False
        if self.calibration.load_profile(self.video_name):
            has_calibration = True
            # Load traffic light ROI if available
            if self.calibration.calibration and self.calibration.calibration.traffic_light_roi:
                has_traffic_light = True
        
        # Load video
        self.video_widget.load_video(file_path, self.detector, self.tracker)
        
        # Set traffic light ROI if available
        if has_traffic_light:
            self.video_widget.set_traffic_light_roi(self.calibration.calibration.traffic_light_roi)
        
        # Show info message
        if has_calibration or has_traffic_light:
            msg_parts = []
            if has_calibration:
                msg_parts.append("thông số hiệu chỉnh")
            if has_traffic_light:
                msg_parts.append("vùng đèn giao thông")
            QMessageBox.information(
                self,
                "Đã tải cấu hình",
                f"Đã tải {' và '.join(msg_parts)} cho video này."
            )
            self.update_calibration_display()
        
        # Update UI
        self.lbl_video.setText(os.path.basename(file_path))
        self.lbl_status.setText("Đã tải video")
        self.btn_calibrate.setEnabled(True)
        self.btn_traffic_light.setEnabled(True)
        if has_traffic_light:
            self.btn_traffic_light.setText("Đã thiết lập đèn GT")
        else:
            self.btn_traffic_light.setText("Cài Đặt Đèn GT")
        self.btn_play.setEnabled(self.calibration.calibration is not None)
        self.btn_stop.setEnabled(True)
        
        self.statusBar.showMessage(f"Đã mở: {file_path}")
    
    def open_video(self):
        """Open video file via file dialog"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn Video",
            "",
            "Video Files (*.mp4 *.avi *.mov *.mkv);;All Files (*.*)"
        )
        
        if file_path:
            self.load_video(file_path)
    
    def initialize_detector_tracker(self):
        """Initialize detector and tracker with current settings"""
        self.detector = VehicleDetector(
            model_path=self.settings.model.model_path,
            conf_threshold=self.settings.model.conf_threshold,
            iou_threshold=self.settings.model.iou_threshold,
            conf_filter=self.settings.model.detection_conf_filter
        )
        
        # Get tracker type from settings
        tracker_type = getattr(self.settings.tracker, 'tracker_type', 'deepsort')
        
        self.tracker = VehicleTracker(
            tracker_type=tracker_type,
            max_age=self.settings.tracker.max_age,
            n_init=self.settings.tracker.n_init,
            max_iou_distance=self.settings.tracker.max_iou_distance,
            max_cosine_distance=self.settings.tracker.max_cosine_distance,
            nn_budget=self.settings.tracker.nn_budget,
            embedder=self.settings.tracker.embedder,
            embedder_gpu=self.settings.tracker.embedder_gpu,
            track_buffer=getattr(self.settings.tracker, 'track_buffer', 30),
            match_thresh=getattr(self.settings.tracker, 'match_thresh', 0.8)
        )
        
        self.statusBar.showMessage(f"Đã khởi tạo Detector và Tracker ({tracker_type})")
    
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
        self.btn_traffic_light.setEnabled(False)
        self.btn_play.setEnabled(False)
        
        # Show instructions based on mode
        mode = self.calibration.get_mode()
        required_points = self.calibration.get_required_points()
        mode_instructions = {
            CalibrationMode.POLYGON: "Nhấn 4 điểm trên video để đánh dấu vùng quan sát",
            CalibrationMode.CIRCLE: "Nhấn 1 điểm TÂM, sau đó 1 điểm trên BÁN KÍNH",
            CalibrationMode.ELLIPSE: "Nhấn 1 điểm TÂM, sau đó 2 điểm trên 2 TRỤC"
        }
        self.lbl_status.setText(f"Đang hiệu chỉnh - Nhấn {required_points} điểm")
        self.statusBar.showMessage(mode_instructions.get(mode, "Đang hiệu chỉnh..."))
    
    def start_traffic_light_calibration(self):
        """Start traffic light ROI calibration"""
        if self.video_path is None:
            QMessageBox.warning(self, "Lỗi", "Vui lòng mở video trước!")
            return
        
        self.video_widget.start_traffic_light_calibration()
        self.btn_traffic_light.setText("Đang chọn vùng đèn...")
        self.btn_traffic_light.setEnabled(False)
        self.btn_calibrate.setEnabled(False)
        self.btn_play.setEnabled(False)
        self.lbl_status.setText("Chọn vùng đèn - Nhấn 4 điểm")
        self.statusBar.showMessage("Nhấn 4 điểm để chọn vùng chứa đèn giao thông")
    
    def on_traffic_light_calibration_complete(self):
        """Called when traffic light ROI calibration is complete"""
        self.btn_traffic_light.setText("Đã thiết lập đèn GT")
        self.btn_traffic_light.setEnabled(True)
        self.btn_calibrate.setEnabled(True)
        self.btn_play.setEnabled(self.calibration.calibration is not None)
        self.lbl_status.setText("Đã thiết lập vùng đèn")
        self.statusBar.showMessage("Vùng đèn giao thông đã được thiết lập!")
        
        # Save traffic light ROI to calibration profile
        if self.video_name and self.calibration.calibration:
            tl_detector = self.video_widget.get_traffic_light_detector()
            self.calibration.calibration.traffic_light_roi = tl_detector.get_points()
            self.calibration.save_profile(self.video_name)
    
    def on_calibration_cancelled(self):
        """Called when calibration is cancelled by user"""
        self.is_calibrating = False
        self.btn_calibrate.setText("Hiệu Chỉnh Vùng Quan Sát")
        self.btn_calibrate.setEnabled(True)
        self.btn_traffic_light.setEnabled(True)
        self.btn_play.setEnabled(self.calibration.calibration is not None)
        self.lbl_status.setText("Đã hủy hiệu chỉnh")
        self.statusBar.showMessage("Hiệu chỉnh đã bị hủy. Nhấn nút Hiệu Chỉnh để thử lại.")
    
    def on_calibration_complete(self, road_length: float, road_width: float):
        """Called when calibration is complete"""
        self.is_calibrating = False
        self.btn_calibrate.setText("Hiệu Chỉnh Lại")
        self.btn_calibrate.setEnabled(True)
        self.btn_traffic_light.setEnabled(True)
        self.btn_play.setEnabled(True)
        
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
                msg = f"Hiệu chỉnh hoàn tất!\n\nChiều dài Ls: {road_length:.1f}m\nChiều rộng Ws: {road_width:.1f}m\nDiện tích DT: {road_length*road_width:.1f}m²"
        else:
            msg = f"Hiệu chỉnh hoàn tất!\n\nChiều dài Ls: {road_length:.1f}m\nChiều rộng Ws: {road_width:.1f}m\nDiện tích DT: {road_length*road_width:.1f}m²"
        
        QMessageBox.information(self, "Hoàn Tất", msg)
    
    def update_calibration_display(self):
        """Update calibration display based on calibration mode"""
        if self.calibration.calibration:
            cal = self.calibration.calibration
            
            # Update labels based on calibration mode
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
                self.lbl_length.setText(f"{cal.road_length_meters:.2f} m")
                self.lbl_param2_title.setVisible(True)
                self.lbl_width.setVisible(True)
                self.lbl_width.setText(f"{cal.road_width_meters:.2f} m")
            
            self.lbl_area.setText(f"{cal.road_area_meters:.2f} m²")
    
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
        
        if 'congestion_status' in stats:
            status = stats['congestion_status']
            color = stats.get('congestion_color', (0, 0, 0))
            # Convert BGR to RGB for Qt
            color_str = f"rgb({color[2]}, {color[1]}, {color[0]})"
            self.lbl_congestion.setText(status)
            self.lbl_congestion.setStyleSheet(
                f"font-size: 20px; font-weight: bold; color: {color_str};"
            )
            
            # Update density gauge
            self.density_gauge.set_value(density_percentage, status, color)
        
        # Update charts with stats dict
        chart_stats = {
            'density_percentage': density_percentage,
            'vehicle_counts': vehicle_counts
        }
        self.chart_panel.update_data(chart_stats)
    
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
            "<p><b>Traffic Monitoring System</b></p>"
            "<p>Phiên bản 1.0.0</p>"
            "<p>Sử dụng YOLO v11 và DeepSORT để phát hiện và theo dõi phương tiện.</p>"
            "<p>Tính toán mật độ giao thông dựa trên diện tích chiếm dụng.</p>"
            "<hr>"
            "<p>Công thức: R = (TL / DT) x 100</p>"
            "<p>(c) 2025 - Đồ Án Tốt Nghiệp</p>"
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
            self.video_widget.is_calibrating_traffic_light = False
        
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
            
        # Update charts theme
        if hasattr(self, 'chart_panel'):
            self.chart_panel.apply_theme(self.is_dark_theme)
            
        if hasattr(self, 'density_gauge'):
            self.density_gauge.apply_theme(self.is_dark_theme)
            
        self.statusBar.showMessage(f"Đã chuyển sang chế độ {'Tối' if self.is_dark_theme else 'Sáng'}")

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
