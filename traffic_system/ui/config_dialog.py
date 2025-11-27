"""
Configuration Dialog for System Settings
"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                             QTabWidget, QWidget, QFormLayout, QDoubleSpinBox,
                             QSpinBox, QLineEdit, QCheckBox, QGroupBox, QLabel)
from PyQt6.QtCore import Qt

from ..config.settings import Settings


class ConfigDialog(QDialog):
    """Configuration dialog for system settings"""
    
    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Cấu Hình Hệ Thống - System Configuration")
        self.setMinimumSize(600, 500)
        
        self.setup_ui()
        
    def apply_theme(self, is_dark: bool):
        """Apply theme style"""
        if is_dark:
            self.setStyleSheet("""
                QDialog {
                    background-color: #1e1e2e;
                    color: #e0e0e0;
                    font-family: 'Inter', sans-serif;
                }
                QWidget {
                    background-color: #1e1e2e;
                    color: #e0e0e0;
                    font-size: 14px;
                }
                QTabWidget::pane {
                    border: 1px solid #3e3e5e;
                    border-radius: 8px;
                    background-color: #232334;
                }
                QTabBar::tab {
                    background-color: #2a2a3c;
                    color: #a0a0a0;
                    padding: 8px 16px;
                    margin-right: 2px;
                    border-top-left-radius: 6px;
                    border-top-right-radius: 6px;
                }
                QTabBar::tab:selected {
                    background-color: #3e3e5e;
                    color: #ffffff;
                    border-bottom: 2px solid #89b4fa;
                }
                QLabel {
                    color: #e0e0e0;
                }
                QLineEdit, QSpinBox, QDoubleSpinBox {
                    background-color: #313244;
                    color: #ffffff;
                    border: 1px solid #45475a;
                    border-radius: 4px;
                    padding: 5px;
                }
                QPushButton {
                    background-color: #313244;
                    color: #ffffff;
                    border: 1px solid #45475a;
                    border-radius: 6px;
                    padding: 8px 16px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #45475a;
                }
            """)
        else:
            self.setStyleSheet("""
                QDialog {
                    background-color: #f5f5f5;
                    color: #333333;
                    font-family: 'Inter', sans-serif;
                }
                QWidget {
                    background-color: #f5f5f5;
                    color: #333333;
                    font-size: 14px;
                }
                QTabWidget::pane {
                    border: 1px solid #e0e0e0;
                    border-radius: 8px;
                    background-color: #ffffff;
                }
                QTabBar::tab {
                    background-color: #e3f2fd;
                    color: #333333;
                    padding: 8px 16px;
                    margin-right: 2px;
                    border-top-left-radius: 6px;
                    border-top-right-radius: 6px;
                }
                QTabBar::tab:selected {
                    background-color: #1976D2;
                    color: #ffffff;
                }
                QLabel {
                    color: #333333;
                }
                QLineEdit, QSpinBox, QDoubleSpinBox {
                    background-color: #ffffff;
                    color: #333333;
                    border: 1px solid #bdbdbd;
                    border-radius: 4px;
                    padding: 5px;
                }
                QPushButton {
                    background-color: #1976D2;
                    color: #ffffff;
                    border: none;
                    border-radius: 6px;
                    padding: 8px 16px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #1565C0;
                }
            """)
    
    def setup_ui(self):
        """Setup UI"""
        layout = QVBoxLayout(self)
        
        # Tabs
        tabs = QTabWidget()
        tabs.addTab(self.create_model_tab(), "Model")
        tabs.addTab(self.create_tracker_tab(), "Tracker / DeepSORT")
        tabs.addTab(self.create_calibration_tab(), "Hiệu Chỉnh")
        tabs.addTab(self.create_video_tab(), "Video")
        
        layout.addWidget(tabs)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        btn_reset = QPushButton("Khôi Phục Mặc Định")
        btn_reset.clicked.connect(self.reset_defaults)
        button_layout.addWidget(btn_reset)
        
        button_layout.addStretch()
        
        btn_cancel = QPushButton("Hủy")
        btn_cancel.clicked.connect(self.reject)
        button_layout.addWidget(btn_cancel)
        
        btn_save = QPushButton("Lưu")
        btn_save.clicked.connect(self.save_settings)
        button_layout.addWidget(btn_save)
        
        layout.addLayout(button_layout)
    
    def create_model_tab(self):
        """Create model configuration tab"""
        widget = QWidget()
        layout = QFormLayout(widget)
        
        # Model path
        self.edit_model_path = QLineEdit(self.settings.model.model_path)
        layout.addRow("Đường dẫn Model:", self.edit_model_path)
        
        # Confidence threshold
        self.spin_conf = QDoubleSpinBox()
        self.spin_conf.setRange(0.0, 1.0)
        self.spin_conf.setSingleStep(0.05)
        self.spin_conf.setValue(self.settings.model.conf_threshold)
        layout.addRow("Ngưỡng Confidence:", self.spin_conf)
        
        # IOU threshold
        self.spin_iou = QDoubleSpinBox()
        self.spin_iou.setRange(0.0, 1.0)
        self.spin_iou.setSingleStep(0.05)
        self.spin_iou.setValue(self.settings.model.iou_threshold)
        layout.addRow("Ngưỡng IOU:", self.spin_iou)
        
        # Detection filter
        self.spin_det_filter = QDoubleSpinBox()
        self.spin_det_filter.setRange(0.0, 1.0)
        self.spin_det_filter.setSingleStep(0.05)
        self.spin_det_filter.setValue(self.settings.model.detection_conf_filter)
        layout.addRow("Lọc Detection:", self.spin_det_filter)
        
        layout.addRow(QLabel(""))
        layout.addRow(QLabel("Lưu ý: Thay đổi cài đặt Model cần khởi tạo lại Detector"))
        
        return widget
    
    def create_tracker_tab(self):
        """Create tracker configuration tab"""
        widget = QWidget()
        layout = QFormLayout(widget)
        
        # Max age
        self.spin_max_age = QSpinBox()
        self.spin_max_age.setRange(1, 100)
        self.spin_max_age.setValue(self.settings.tracker.max_age)
        layout.addRow("Max Age (frames):", self.spin_max_age)
        
        # N init
        self.spin_n_init = QSpinBox()
        self.spin_n_init.setRange(1, 50)
        self.spin_n_init.setValue(self.settings.tracker.n_init)
        layout.addRow("N Init (frames):", self.spin_n_init)
        
        # Max IOU distance
        self.spin_max_iou_dist = QDoubleSpinBox()
        self.spin_max_iou_dist.setRange(0.0, 1.0)
        self.spin_max_iou_dist.setSingleStep(0.05)
        self.spin_max_iou_dist.setValue(self.settings.tracker.max_iou_distance)
        layout.addRow("Max IOU Distance:", self.spin_max_iou_dist)
        
        # Max cosine distance
        self.spin_max_cos_dist = QDoubleSpinBox()
        self.spin_max_cos_dist.setRange(0.0, 1.0)
        self.spin_max_cos_dist.setSingleStep(0.05)
        self.spin_max_cos_dist.setValue(self.settings.tracker.max_cosine_distance)
        layout.addRow("Max Cosine Distance:", self.spin_max_cos_dist)
        
        # NN budget
        self.spin_nn_budget = QSpinBox()
        self.spin_nn_budget.setRange(1, 200)
        self.spin_nn_budget.setValue(self.settings.tracker.nn_budget)
        layout.addRow("NN Budget:", self.spin_nn_budget)
        
        # Embedder
        self.edit_embedder = QLineEdit(self.settings.tracker.embedder)
        layout.addRow("Embedder:", self.edit_embedder)
        
        # Embedder GPU
        self.check_embedder_gpu = QCheckBox("Sử dụng GPU cho Embedder")
        self.check_embedder_gpu.setChecked(self.settings.tracker.embedder_gpu)
        layout.addRow("", self.check_embedder_gpu)
        
        layout.addRow(QLabel(""))
        layout.addRow(QLabel("Lưu ý: Thay đổi cài đặt Tracker cần khởi tạo lại"))
        
        return widget
    
    def create_calibration_tab(self):
        """Create calibration configuration tab"""
        widget = QWidget()
        layout = QFormLayout(widget)
        
        # Default road length
        self.spin_def_length = QDoubleSpinBox()
        self.spin_def_length.setRange(1.0, 1000.0)
        self.spin_def_length.setSuffix(" m")
        self.spin_def_length.setValue(self.settings.calibration.default_road_length)
        layout.addRow("Chiều dài mặc định (Ls):", self.spin_def_length)
        
        # Default road width
        self.spin_def_width = QDoubleSpinBox()
        self.spin_def_width.setRange(1.0, 100.0)
        self.spin_def_width.setSuffix(" m")
        self.spin_def_width.setValue(self.settings.calibration.default_road_width)
        layout.addRow("Chiều rộng mặc định (Ws):", self.spin_def_width)
        
        # Use perspective transform
        self.check_perspective = QCheckBox("Sử dụng Perspective Transform")
        self.check_perspective.setChecked(self.settings.calibration.use_perspective_transform)
        layout.addRow("", self.check_perspective)
        
        # Enable save
        self.check_save_calib = QCheckBox("Tự động lưu Hiệu Chỉnh")
        self.check_save_calib.setChecked(self.settings.calibration.enable_save)
        layout.addRow("", self.check_save_calib)
        
        # Profiles directory
        self.edit_profiles_dir = QLineEdit(self.settings.calibration.profiles_dir)
        layout.addRow("Thư mục Profiles:", self.edit_profiles_dir)
        
        return widget
    
    def create_video_tab(self):
        """Create video configuration tab"""
        widget = QWidget()
        layout = QFormLayout(widget)
        
        # Frame skip
        self.spin_frame_skip = QSpinBox()
        self.spin_frame_skip.setRange(1, 10)
        self.spin_frame_skip.setValue(self.settings.video.frame_skip)
        layout.addRow("Frame Skip:", self.spin_frame_skip)
        
        # FPS limit
        self.spin_fps_limit = QSpinBox()
        self.spin_fps_limit.setRange(0, 120)
        self.spin_fps_limit.setSpecialValueText("Không giới hạn")
        self.spin_fps_limit.setValue(self.settings.video.fps_limit or 0)
        layout.addRow("Giới hạn FPS:", self.spin_fps_limit)
        
        # Process resize width
        self.spin_resize = QSpinBox()
        self.spin_resize.setRange(0, 1920)
        self.spin_resize.setSpecialValueText("Không resize")
        self.spin_resize.setValue(self.settings.video.process_resize_width or 0)
        layout.addRow("Resize Width:", self.spin_resize)
        
        # Wait key ms
        self.spin_wait_key = QSpinBox()
        self.spin_wait_key.setRange(1, 100)
        self.spin_wait_key.setSuffix(" ms")
        self.spin_wait_key.setValue(self.settings.video.wait_key_ms)
        layout.addRow("Wait Key Delay:", self.spin_wait_key)
        
        return widget
    
    def save_settings(self):
        """Save settings and close"""
        # Model
        self.settings.model.model_path = self.edit_model_path.text()
        self.settings.model.conf_threshold = self.spin_conf.value()
        self.settings.model.iou_threshold = self.spin_iou.value()
        self.settings.model.detection_conf_filter = self.spin_det_filter.value()
        
        # Tracker
        self.settings.tracker.max_age = self.spin_max_age.value()
        self.settings.tracker.n_init = self.spin_n_init.value()
        self.settings.tracker.max_iou_distance = self.spin_max_iou_dist.value()
        self.settings.tracker.max_cosine_distance = self.spin_max_cos_dist.value()
        self.settings.tracker.nn_budget = self.spin_nn_budget.value()
        self.settings.tracker.embedder = self.edit_embedder.text()
        self.settings.tracker.embedder_gpu = self.check_embedder_gpu.isChecked()
        
        # Calibration
        self.settings.calibration.default_road_length = self.spin_def_length.value()
        self.settings.calibration.default_road_width = self.spin_def_width.value()
        self.settings.calibration.use_perspective_transform = self.check_perspective.isChecked()
        self.settings.calibration.enable_save = self.check_save_calib.isChecked()
        self.settings.calibration.profiles_dir = self.edit_profiles_dir.text()
        
        # Video
        self.settings.video.frame_skip = self.spin_frame_skip.value()
        fps = self.spin_fps_limit.value()
        self.settings.video.fps_limit = fps if fps > 0 else None
        resize = self.spin_resize.value()
        self.settings.video.process_resize_width = resize if resize > 0 else None
        self.settings.video.wait_key_ms = self.spin_wait_key.value()
        
        # Save to file
        self.settings.save()
        
        self.accept()
    
    def reset_defaults(self):
        """Reset to default values"""
        from PyQt6.QtWidgets import QMessageBox
        
        reply = QMessageBox.question(
            self,
            "Khôi Phục Mặc Định",
            "Khôi phục tất cả cài đặt về giá trị mặc định?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.settings.reset_to_defaults()
            self.close()
            
            # Reopen dialog with new defaults
            new_dialog = ConfigDialog(self.settings, self.parent())
            new_dialog.exec()
