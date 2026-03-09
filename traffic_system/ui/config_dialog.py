"""
Configuration Dialog for System Settings
"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                             QTabWidget, QWidget, QFormLayout, QDoubleSpinBox,
                             QSpinBox, QLineEdit, QCheckBox, QGroupBox, QLabel,
                             QComboBox)
from PyQt6.QtCore import Qt

from ..config.settings import Settings


class ConfigDialog(QDialog):
    """Configuration dialog for system settings"""
    
    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Cấu Hình Hệ Thống")
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
        tabs.addTab(self.create_model_tab(), "Model AI")
        tabs.addTab(self.create_tracker_tab(), "Bộ Theo Dõi")
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
        
        # Model selection group
        model_group = QGroupBox("Lựa Chọn Model")
        model_layout = QFormLayout(model_group)
        
        # Model path with browse button
        model_path_layout = QHBoxLayout()
        self.edit_model_path = QLineEdit(self.settings.model.model_path)
        model_path_layout.addWidget(self.edit_model_path)
        
        btn_browse_model = QPushButton("...")
        btn_browse_model.setMaximumWidth(40)
        btn_browse_model.clicked.connect(self.browse_model)
        model_path_layout.addWidget(btn_browse_model)
        model_layout.addRow("Đường dẫn Model:", model_path_layout)
        
        # Available models dropdown
        self.combo_available_models = QComboBox()
        self.populate_available_models()
        self.combo_available_models.currentTextChanged.connect(self.on_model_selected)
        model_layout.addRow("Models có sẵn:", self.combo_available_models)
        
        layout.addWidget(model_group)
        
        # Detection settings group
        detection_group = QGroupBox("Cài Đặt Phát Hiện")
        detection_layout = QFormLayout(detection_group)
        
        # Confidence threshold
        self.spin_conf = QDoubleSpinBox()
        self.spin_conf.setRange(0.0, 1.0)
        self.spin_conf.setSingleStep(0.05)
        self.spin_conf.setValue(self.settings.model.conf_threshold)
        self.spin_conf.setToolTip("Ngưỡng confidence tối thiểu để nhận detection")
        detection_layout.addRow("Ngưỡng Confidence:", self.spin_conf)
        
        # IOU threshold
        self.spin_iou = QDoubleSpinBox()
        self.spin_iou.setRange(0.0, 1.0)
        self.spin_iou.setSingleStep(0.05)
        self.spin_iou.setValue(self.settings.model.iou_threshold)
        self.spin_iou.setToolTip("Ngưỡng IOU cho Non-Max Suppression")
        detection_layout.addRow("Ngưỡng IOU:", self.spin_iou)
        
        # Detection filter
        self.spin_det_filter = QDoubleSpinBox()
        self.spin_det_filter.setRange(0.0, 1.0)
        self.spin_det_filter.setSingleStep(0.05)
        self.spin_det_filter.setValue(self.settings.model.detection_conf_filter)
        self.spin_det_filter.setToolTip("Lọc detection sau NMS")
        detection_layout.addRow("Lọc Detection:", self.spin_det_filter)
        
        # Inference size
        self.spin_imgsz = QSpinBox()
        self.spin_imgsz.setRange(320, 1280)
        self.spin_imgsz.setSingleStep(32)
        self.spin_imgsz.setValue(self.settings.model.imgsz)
        self.spin_imgsz.setToolTip("Kích thước ảnh inference (phải chia hết cho 32)")
        detection_layout.addRow("Kích thước Inference:", self.spin_imgsz)

        # Max detections
        self.spin_max_det = QSpinBox()
        self.spin_max_det.setRange(10, 500)
        self.spin_max_det.setValue(self.settings.model.max_det)
        self.spin_max_det.setToolTip("Số detection tối đa mỗi frame")
        detection_layout.addRow("Số Detection Tối Đa:", self.spin_max_det)        # FP16 inference
        self.check_half = QCheckBox("Sử dụng FP16 (Half precision)")
        self.check_half.setChecked(self.settings.model.half)
        self.check_half.setToolTip("Tăng tốc inference trên GPU, có thể giảm độ chính xác nhẹ")
        detection_layout.addRow("", self.check_half)
        
        layout.addWidget(detection_group)
        
        layout.addRow(QLabel(""))
        note = QLabel("⚠️ Thay đổi cài đặt Model cần khởi tạo lại Detector")
        note.setStyleSheet("color: #f39c12; font-weight: bold;")
        layout.addRow(note)
        
        return widget
    
    def populate_available_models(self):
        """Populate available models dropdown"""
        import os
        self.combo_available_models.clear()
        self.combo_available_models.addItem("-- Chọn model --", "")
        
        model_dir = "Model"
        if os.path.exists(model_dir):
            for f in os.listdir(model_dir):
                if f.endswith('.pt') and not f.endswith(':Zone.Identifier'):
                    model_path = os.path.join(model_dir, f)
                    # Get file size
                    size_mb = os.path.getsize(model_path) / (1024 * 1024)
                    display_name = f"{f} ({size_mb:.1f} MB)"
                    self.combo_available_models.addItem(display_name, model_path)
    
    def on_model_selected(self, text):
        """Handle model selection from dropdown"""
        model_path = self.combo_available_models.currentData()
        if model_path:
            self.edit_model_path.setText(model_path)
    
    def browse_model(self):
        """Browse for model file"""
        from PyQt6.QtWidgets import QFileDialog
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn Model YOLO",
            "Model/",
            "Model YOLO (*.pt);;Tất cả File (*)"
        )
        if file_path:
            self.edit_model_path.setText(file_path)
    
    def create_tracker_tab(self):
        """Create tracker configuration tab - BoT-SORT only"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Tracker info
        info_group = QGroupBox("Thông Tin Tracker")
        info_layout = QFormLayout(info_group)
        
        info_label = QLabel("BoT-SORT (YOLO built-in)")
        info_label.setStyleSheet("font-weight: bold; font-size: 16px;")
        info_layout.addRow("Tracker:", info_label)
        
        desc_label = QLabel("Theo dõi tích hợp YOLO với GMC và ReID (tùy chọn). Cân bằng giữa tốc độ và độ chính xác.")
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #666666; font-style: italic;")
        info_layout.addRow("", desc_label)
        
        layout.addWidget(info_group)
        
        # BoT-SORT Tracking Settings
        tracking_group = QGroupBox("Cài Đặt Theo Dõi")
        tracking_layout = QFormLayout(tracking_group)
        
        # Track thresholds
        self.spin_track_high_thresh = QDoubleSpinBox()
        self.spin_track_high_thresh.setRange(0.1, 1.0)
        self.spin_track_high_thresh.setSingleStep(0.05)
        self.spin_track_high_thresh.setValue(getattr(self.settings.tracker, 'track_high_thresh', 0.5))
        self.spin_track_high_thresh.setToolTip("Ngưỡng confidence cao cho first association")
        tracking_layout.addRow("Ngưỡng Cao:", self.spin_track_high_thresh)
        
        self.spin_track_low_thresh = QDoubleSpinBox()
        self.spin_track_low_thresh.setRange(0.0, 0.5)
        self.spin_track_low_thresh.setSingleStep(0.05)
        self.spin_track_low_thresh.setValue(getattr(self.settings.tracker, 'track_low_thresh', 0.1))
        self.spin_track_low_thresh.setToolTip("Ngưỡng confidence thấp cho second association")
        tracking_layout.addRow("Ngưỡng Thấp:", self.spin_track_low_thresh)
        
        self.spin_new_track_thresh = QDoubleSpinBox()
        self.spin_new_track_thresh.setRange(0.1, 1.0)
        self.spin_new_track_thresh.setSingleStep(0.05)
        self.spin_new_track_thresh.setValue(getattr(self.settings.tracker, 'new_track_thresh', 0.6))
        self.spin_new_track_thresh.setToolTip("Ngưỡng confidence để tạo track mới")
        tracking_layout.addRow("Ngưỡng Track Mới:", self.spin_new_track_thresh)
        
        self.spin_track_buffer = QSpinBox()
        self.spin_track_buffer.setRange(10, 120)
        self.spin_track_buffer.setValue(getattr(self.settings.tracker, 'track_buffer', 30))
        self.spin_track_buffer.setToolTip("Số frame giữ track khi mất detection")
        tracking_layout.addRow("Bộ Đệm (frames):", self.spin_track_buffer)
        
        self.spin_match_thresh = QDoubleSpinBox()
        self.spin_match_thresh.setRange(0.5, 1.0)
        self.spin_match_thresh.setSingleStep(0.05)
        self.spin_match_thresh.setValue(getattr(self.settings.tracker, 'match_thresh', 0.8))
        self.spin_match_thresh.setToolTip("Ngưỡng matching (IOU threshold)")
        tracking_layout.addRow("Ngưỡng Khớp:", self.spin_match_thresh)
        
        layout.addWidget(tracking_group)
        
        # GMC & ReID settings
        gmc_reid_group = QGroupBox("Cài Đặt GMC & ReID")
        gmc_reid_layout = QFormLayout(gmc_reid_group)
        
        # GMC Method
        self.combo_gmc_method = QComboBox()
        self.combo_gmc_method.addItem("Sparse Optical Flow (Khuyến nghị)", "sparseOptFlow")
        self.combo_gmc_method.addItem("Đặc trưng ORB", "orb")
        self.combo_gmc_method.addItem("Đặc trưng SIFT", "sift")
        self.combo_gmc_method.addItem("ECC (Tương quan nâng cao)", "ecc")
        self.combo_gmc_method.addItem("Tắt GMC", "None")
        current_gmc = getattr(self.settings.tracker, 'gmc_method', 'sparseOptFlow')
        idx = self.combo_gmc_method.findData(current_gmc)
        if idx >= 0:
            self.combo_gmc_method.setCurrentIndex(idx)
        self.combo_gmc_method.setToolTip("Phương pháp Global Motion Compensation (bù chuyển động camera)")
        gmc_reid_layout.addRow("Phương Pháp GMC:", self.combo_gmc_method)
        
        # ReID settings
        self.check_with_reid = QCheckBox("Bật Re-Identification (ReID)")
        self.check_with_reid.setChecked(getattr(self.settings.tracker, 'with_reid', False))
        self.check_with_reid.setToolTip("ReID giúp tracking tốt hơn khi có che khuất, nhưng chậm hơn")
        self.check_with_reid.stateChanged.connect(self.on_reid_changed)
        gmc_reid_layout.addRow("", self.check_with_reid)
        
        # ReID Model
        self.combo_reid_model = QComboBox()
        self.combo_reid_model.addItem("Tự động (Native YOLO features)", "auto")
        self.combo_reid_model.addItem("YOLO11n-cls (Nhỏ nhất, nhanh nhất)", "yolo11n-cls.pt")
        self.combo_reid_model.addItem("YOLO11s-cls (Nhỏ, nhanh)", "yolo11s-cls.pt")
        self.combo_reid_model.addItem("YOLO11m-cls (Trung bình, cân bằng)", "yolo11m-cls.pt")
        self.combo_reid_model.addItem("YOLO11l-cls (Lớn, chính xác cao)", "yolo11l-cls.pt")
        self.combo_reid_model.addItem("YOLO11x-cls (Lớn nhất, chính xác nhất)", "yolo11x-cls.pt")
        current_reid_model = getattr(self.settings.tracker, 'reid_model', 'auto')
        idx = self.combo_reid_model.findData(current_reid_model)
        if idx >= 0:
            self.combo_reid_model.setCurrentIndex(idx)
        self.combo_reid_model.setToolTip("Model cho Re-Identification")
        gmc_reid_layout.addRow("Model ReID:", self.combo_reid_model)
        
        self.spin_proximity_thresh = QDoubleSpinBox()
        self.spin_proximity_thresh.setRange(0.1, 1.0)
        self.spin_proximity_thresh.setSingleStep(0.05)
        self.spin_proximity_thresh.setValue(getattr(self.settings.tracker, 'proximity_thresh', 0.5))
        self.spin_proximity_thresh.setToolTip("Ngưỡng IoU tối thiểu cho ReID matching")
        gmc_reid_layout.addRow("Ngưỡng Proximity:", self.spin_proximity_thresh)
        
        self.spin_appearance_thresh = QDoubleSpinBox()
        self.spin_appearance_thresh.setRange(0.1, 1.0)
        self.spin_appearance_thresh.setSingleStep(0.05)
        self.spin_appearance_thresh.setValue(getattr(self.settings.tracker, 'appearance_thresh', 0.25))
        self.spin_appearance_thresh.setToolTip("Ngưỡng appearance similarity cho ReID")
        gmc_reid_layout.addRow("Ngưỡng Appearance:", self.spin_appearance_thresh)
        
        layout.addWidget(gmc_reid_group)
        
        # Note
        note_label = QLabel("⚠️ Thay đổi cài đặt Tracker cần khởi tạo lại video")
        note_label.setStyleSheet("color: #f39c12; font-weight: bold;")
        layout.addWidget(note_label)
        
        layout.addStretch()
        
        # Initialize ReID state
        self.on_reid_changed()
        
        return widget
    
    def on_reid_changed(self):
        """Handle ReID checkbox change"""
        reid_enabled = self.check_with_reid.isChecked()
        self.combo_reid_model.setEnabled(reid_enabled)
        self.spin_proximity_thresh.setEnabled(reid_enabled)
        self.spin_appearance_thresh.setEnabled(reid_enabled)
    
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
        layout.addRow("Bỏ Qua Frame:", self.spin_frame_skip)

        # FPS limit
        self.spin_fps_limit = QSpinBox()
        self.spin_fps_limit.setRange(0, 120)
        self.spin_fps_limit.setSpecialValueText("Không giới hạn")
        self.spin_fps_limit.setValue(self.settings.video.fps_limit or 0)
        layout.addRow("Giới Hạn FPS:", self.spin_fps_limit)

        # Process resize width
        self.spin_resize = QSpinBox()
        self.spin_resize.setRange(0, 1920)
        self.spin_resize.setSpecialValueText("Không resize")
        self.spin_resize.setValue(self.settings.video.process_resize_width or 0)
        layout.addRow("Độ Rộng Resize:", self.spin_resize)

        # Wait key ms
        self.spin_wait_key = QSpinBox()
        self.spin_wait_key.setRange(1, 100)
        self.spin_wait_key.setSuffix(" ms")
        self.spin_wait_key.setValue(self.settings.video.wait_key_ms)
        layout.addRow("Độ Trễ Phím:", self.spin_wait_key)      
        
        return widget
    
    def save_settings(self):
        """Save settings and close"""
        # Model
        self.settings.model.model_path = self.edit_model_path.text()
        self.settings.model.conf_threshold = self.spin_conf.value()
        self.settings.model.iou_threshold = self.spin_iou.value()
        self.settings.model.detection_conf_filter = self.spin_det_filter.value()
        self.settings.model.imgsz = self.spin_imgsz.value()
        self.settings.model.max_det = self.spin_max_det.value()
        self.settings.model.half = self.check_half.isChecked()
        
        # BoT-SORT tracker settings
        self.settings.tracker.tracker_type = "botsort"
        self.settings.tracker.track_high_thresh = self.spin_track_high_thresh.value()
        self.settings.tracker.track_low_thresh = self.spin_track_low_thresh.value()
        self.settings.tracker.new_track_thresh = self.spin_new_track_thresh.value()
        self.settings.tracker.track_buffer = self.spin_track_buffer.value()
        self.settings.tracker.match_thresh = self.spin_match_thresh.value()
        
        # BoT-SORT GMC & ReID
        self.settings.tracker.gmc_method = self.combo_gmc_method.currentData()
        self.settings.tracker.with_reid = self.check_with_reid.isChecked()
        self.settings.tracker.reid_model = self.combo_reid_model.currentData()
        self.settings.tracker.proximity_thresh = self.spin_proximity_thresh.value()
        self.settings.tracker.appearance_thresh = self.spin_appearance_thresh.value()
        
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
