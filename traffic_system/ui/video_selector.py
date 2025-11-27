"""
Video Selector Widget - Traffic Camera Monitoring Style
Displays available videos in the Video folder for selection
Dark theme with responsive layout
"""

import cv2
from pathlib import Path
from datetime import datetime
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QScrollArea, QFrame, QGridLayout,
                             QFileDialog, QSizePolicy)
from PyQt6.QtCore import pyqtSignal, Qt, QTimer
from PyQt6.QtGui import QPixmap, QImage

from ..utils.logger import get_logger

logger = get_logger(__name__)


class CameraCard(QFrame):
    """Camera/Video card widget - responsive design"""
    
    clicked = pyqtSignal(str)
    
    def __init__(self, video_path: str, camera_id: int = 1, parent=None):
        super().__init__(parent)
        self.video_path = video_path
        self.video_name = Path(video_path).stem
        self.camera_id = camera_id
        self.duration_str = "--:--"
        self.resolution = "---"
        self.fps_value = 0
        
        # Responsive sizing - larger cards
        self.setMinimumSize(350, 280)
        self.setMaximumSize(480, 380)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self.setup_ui()
        self.load_video_info()
        self.apply_theme(True)  # Default dark theme
    
    def apply_theme(self, is_dark: bool):
        """Apply theme style"""
        if is_dark:
            self.setStyleSheet("""
                CameraCard {
                    background-color: #2a2a3c;
                    border: 1px solid #3e3e5e;
                    border-radius: 12px;
                }
                CameraCard:hover {
                    border: 2px solid #89b4fa;
                    background-color: #313244;
                }
            """)
            self.preview_container.setStyleSheet("background-color: #181825; border-radius: 10px 10px 0 0;")
            self.info_bar.setStyleSheet("""
                background-color: #232334;
                border-radius: 0 0 10px 10px;
                border-top: 1px solid #3e3e5e;
            """)
            self.name_label.setStyleSheet("color: #e0e0e0; font-size: 16px; font-weight: bold;")
            self.duration_label.setStyleSheet("color: #89b4fa; font-size: 14px; font-weight: bold;")
            self.res_label.setStyleSheet("color: #a0a0a0; font-size: 13px;")
            self.status_label.setStyleSheet("""
                color: #a6e3a1; font-size: 13px; font-weight: bold;
                background-color: #1e1e2e; padding: 4px 10px; border-radius: 4px;
            """)
        else:
            self.setStyleSheet("""
                CameraCard {
                    background-color: #ffffff;
                    border: 1px solid #e0e0e0;
                    border-radius: 12px;
                }
                CameraCard:hover {
                    border: 2px solid #1976D2;
                    background-color: #f5f5f5;
                }
            """)
            self.preview_container.setStyleSheet("background-color: #eeeeee; border-radius: 10px 10px 0 0;")
            self.info_bar.setStyleSheet("""
                background-color: #f9f9f9;
                border-radius: 0 0 10px 10px;
                border-top: 1px solid #e0e0e0;
            """)
            self.name_label.setStyleSheet("color: #333333; font-size: 16px; font-weight: bold;")
            self.duration_label.setStyleSheet("color: #1976D2; font-size: 14px; font-weight: bold;")
            self.res_label.setStyleSheet("color: #666666; font-size: 13px;")
            self.status_label.setStyleSheet("""
                color: #2E7D32; font-size: 13px; font-weight: bold;
                background-color: #E8F5E9; padding: 4px 10px; border-radius: 4px;
            """)
    
    def setup_ui(self):
        """Setup UI with responsive layout"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Video preview container
        self.preview_container = QFrame()
        self.preview_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # Style set in apply_theme
        preview_layout = QVBoxLayout(self.preview_container)
        preview_layout.setContentsMargins(4, 4, 4, 4)
        
        # Thumbnail
        self.thumbnail_label = QLabel()
        self.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail_label.setStyleSheet("background: transparent;")
        self.thumbnail_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.thumbnail_label.setScaledContents(False)
        preview_layout.addWidget(self.thumbnail_label)
        
        layout.addWidget(self.preview_container, stretch=3)
        
        # Info bar at bottom
        self.info_bar = QFrame()
        self.info_bar.setMinimumHeight(70)
        # Style set in apply_theme
        info_layout = QVBoxLayout(self.info_bar)
        info_layout.setContentsMargins(12, 8, 12, 8)
        info_layout.setSpacing(4)
        
        # Camera name
        self.name_label = QLabel()
        # Style set in apply_theme
        self.name_label.setWordWrap(True)
        info_layout.addWidget(self.name_label)
        
        # Stats row
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(15)
        
        # Duration
        self.duration_label = QLabel()
        # Style set in apply_theme
        stats_layout.addWidget(self.duration_label)
        
        # Resolution
        self.res_label = QLabel()
        # Style set in apply_theme
        stats_layout.addWidget(self.res_label)
        
        stats_layout.addStretch()
        
        # Status indicator
        self.status_label = QLabel("SẴN SÀNG")
        # Style set in apply_theme
        stats_layout.addWidget(self.status_label)
        
        info_layout.addLayout(stats_layout)
        layout.addWidget(self.info_bar)
    
    def resizeEvent(self, event):
        """Handle resize for responsive thumbnail"""
        super().resizeEvent(event)
        # Re-scale thumbnail when resized
        if hasattr(self, '_original_pixmap') and self._original_pixmap:
            preview_size = self.preview_container.size()
            scaled = self._original_pixmap.scaled(
                preview_size.width() - 8, preview_size.height() - 8,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.thumbnail_label.setPixmap(scaled)
    
    def load_video_info(self):
        """Load video information and thumbnail"""
        try:
            cap = cv2.VideoCapture(self.video_path)
            if cap.isOpened():
                # Read first frame for thumbnail
                ret, frame = cap.read()
                if ret:
                    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    h, w, ch = rgb_frame.shape
                    
                    # Store resolution
                    self.resolution = f"{w}x{h}"
                    
                    # Create thumbnail
                    bytes_per_line = ch * w
                    qt_image = QImage(rgb_frame.data, w, h, bytes_per_line, 
                                     QImage.Format.Format_RGB888)
                    self._original_pixmap = QPixmap.fromImage(qt_image)
                    
                    # Initial scale
                    scaled_pixmap = self._original_pixmap.scaled(
                        300, 160,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    self.thumbnail_label.setPixmap(scaled_pixmap)
                
                # Get video info
                self.fps_value = cap.get(cv2.CAP_PROP_FPS)
                frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                duration = frames / self.fps_value if self.fps_value > 0 else 0
                
                minutes = int(duration // 60)
                seconds = int(duration % 60)
                self.duration_str = f"{minutes:02d}:{seconds:02d}"
                
                cap.release()
                
            # Update labels
            display_name = self.video_name
            if len(display_name) > 35:
                display_name = display_name[:32] + "..."
            
            self.name_label.setText(f"CAM-{self.camera_id:02d}: {display_name}")
            self.duration_label.setText(f"Thời lượng: {self.duration_str}")
            self.res_label.setText(self.resolution)
            
        except Exception as e:
            logger.error(f"Error loading video info: {e}")
            self.name_label.setText(f"CAM-{self.camera_id:02d}: Lỗi")
            self.status_label.setText("LỖI")
            self.status_label.setStyleSheet("""
                color: #f38ba8;
                font-size: 12px;
                font-weight: bold;
                background-color: #313244;
                padding: 4px 10px;
                border-radius: 4px;
            """)
    
    def mousePressEvent(self, event):
        """Handle click"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.video_path)
        super().mousePressEvent(event)
    
    def enterEvent(self, event):
        """Mouse enter - highlight"""
        self.status_label.setText("NHẤN ĐỂ PHÂN TÍCH")
        self.status_label.setStyleSheet("""
            color: #89b4fa;
            font-size: 12px;
            font-weight: bold;
            background-color: #313244;
            padding: 4px 10px;
            border-radius: 4px;
        """)
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """Mouse leave"""
        self.status_label.setText("SẴN SÀNG")
        self.status_label.setStyleSheet("""
            color: #a6e3a1;
            font-size: 12px;
            font-weight: bold;
            background-color: #1e1e2e;
            padding: 4px 10px;
            border-radius: 4px;
        """)
        super().leaveEvent(event)


class VideoSelectorWidget(QWidget):
    """Traffic Camera Monitoring Dashboard - Video Selection Screen - Dark Theme"""
    
    video_selected = pyqtSignal(str)
    
    def __init__(self, video_folder: str = "Video", parent=None):
        super().__init__(parent)
        self.video_folder = video_folder
        self.video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.wmv']
        
        # Default theme state
        self.is_dark = True
        
        self.setup_ui()
        self.load_videos()
        self.apply_theme(self.is_dark)
        
        # Update time every second
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_time)
        self.timer.start(1000)
    
    def setup_ui(self):
        """Setup Traffic Monitoring Dashboard UI - Light Theme"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # ===== TOP HEADER BAR =====
        self.header = QFrame()
        self.header.setMinimumHeight(90)
        self.header_layout = QHBoxLayout(self.header)
        self.header_layout.setContentsMargins(25, 12, 25, 12)
        
        # Logo/Title section
        title_section = QVBoxLayout()
        title_section.setSpacing(4)
        
        self.main_title = QLabel("HỆ THỐNG GIÁM SÁT GIAO THÔNG")
        self.main_title.setStyleSheet("""
            font-size: 32px;
            font-weight: bold;
            color: #ffffff;
            letter-spacing: 2px;
        """)
        title_section.addWidget(self.main_title)
        
        self.sub_title = QLabel("Traffic Monitoring & Congestion Warning System")
        self.sub_title.setStyleSheet("""
            font-size: 16px;
            color: rgba(255, 255, 255, 0.9);
            letter-spacing: 1px;
        """)
        title_section.addWidget(self.sub_title)
        
        self.header_layout.addLayout(title_section)
        self.header_layout.addStretch()
        
        # Status indicators
        status_section = QHBoxLayout()
        status_section.setSpacing(20)
        
        # System status
        self.system_status = QFrame()
        system_layout = QHBoxLayout(self.system_status)
        system_layout.setContentsMargins(15, 8, 15, 8)
        
        self.status_dot = QLabel()
        self.status_dot.setFixedSize(12, 12)
        self.status_dot.setStyleSheet("background-color: #4CAF50; border-radius: 6px;")
        system_layout.addWidget(self.status_dot)
        
        self.status_text = QLabel("HỆ THỐNG SẴN SÀNG")
        self.status_text.setStyleSheet("color: #ffffff; font-size: 16px; font-weight: bold;")
        system_layout.addWidget(self.status_text)
        
        status_section.addWidget(self.system_status)
        
        # Time display
        self.time_label = QLabel()
        # Style set in apply_theme
        self.update_time()
        status_section.addWidget(self.time_label)
        
        self.header_layout.addLayout(status_section)
        layout.addWidget(self.header)
        
        # ===== TOOLBAR =====
        self.toolbar = QFrame()
        self.toolbar.setMinimumHeight(60)
        toolbar_layout = QHBoxLayout(self.toolbar)
        toolbar_layout.setContentsMargins(25, 10, 25, 10)
        
        # Camera count
        self.camera_count_label = QLabel("SỐ LƯỢNG VIDEO: 0")
        # Style set in apply_theme
        toolbar_layout.addWidget(self.camera_count_label)
        
        # Folder path
        self.folder_label = QLabel(f"Thư mục: {self.video_folder}/")
        # Style set in apply_theme
        toolbar_layout.addWidget(self.folder_label)
        
        toolbar_layout.addStretch()
        
        # Buttons
        self.btn_refresh = QPushButton("Làm Mới")
        self.btn_refresh.setMinimumSize(130, 45)
        self.btn_refresh.clicked.connect(self.load_videos)
        toolbar_layout.addWidget(self.btn_refresh)
        
        self.btn_browse = QPushButton("Chọn Từ Máy Tính")
        self.btn_browse.setMinimumSize(180, 45)
        self.btn_browse.clicked.connect(self.browse_file)
        toolbar_layout.addWidget(self.btn_browse)
        
        layout.addWidget(self.toolbar)
        
        # ===== MAIN CONTENT AREA =====
        self.content = QFrame()
        content_layout = QVBoxLayout(self.content)
        content_layout.setContentsMargins(25, 20, 25, 20)
        
        # Section header
        self.section_header = QLabel("CHỌN VIDEO ĐỂ BẮT ĐẦU PHÂN TÍCH")
        # Style set in apply_theme
        content_layout.addWidget(self.section_header)
        
        # Scroll area for camera grid
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # Style set in apply_theme
        
        # Grid container
        self.grid_widget = QWidget()
        self.grid_widget.setStyleSheet("background-color: transparent;")
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setHorizontalSpacing(12)  # Chiều ngang gần hơn
        self.grid_layout.setVerticalSpacing(25)    # Chiều dọc xa hơn
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        
        self.scroll_area.setWidget(self.grid_widget)
        content_layout.addWidget(self.scroll_area, stretch=1)
        
        layout.addWidget(self.content, stretch=1)
        
        # ===== FOOTER =====
        self.footer = QFrame()
        self.footer.setMinimumHeight(50)
        footer_layout = QHBoxLayout(self.footer)
        footer_layout.setContentsMargins(25, 8, 25, 8)
        
        self.footer_text = QLabel("Nhấn vào video bất kỳ để bắt đầu phân tích mật độ giao thông")
        # Style set in apply_theme
        footer_layout.addWidget(self.footer_text)
        
        footer_layout.addStretch()
        
        self.version_label = QLabel("v2.0.0 | YOLO v11 + DeepSORT")
        # Style set in apply_theme
        footer_layout.addWidget(self.version_label)
        
        layout.addWidget(self.footer)
    
    def update_time(self):
        """Update time display"""
        now = datetime.now()
        self.time_label.setText(now.strftime("%Y-%m-%d  %H:%M:%S"))
    
    def load_videos(self):
        """Load videos from folder"""
        # Clear existing cards
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Get video files
        video_folder_path = Path(self.video_folder)
        if not video_folder_path.exists():
            logger.warning(f"Video folder not found: {self.video_folder}")
            self.camera_count_label.setText("SỐ LƯỢNG VIDEO: 0")
            
            error_label = QLabel("Không tìm thấy thư mục video")
            error_label.setStyleSheet("""
                color: #f38ba8;
                font-size: 18px;
                padding: 60px;
            """)
            error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid_layout.addWidget(error_label, 0, 0)
            return
        
        videos = []
        for ext in self.video_extensions:
            videos.extend(video_folder_path.glob(f"*{ext}"))
            videos.extend(video_folder_path.glob(f"*{ext.upper()}"))
        
        # Remove duplicates and sort
        videos = sorted(set(videos), key=lambda x: x.name.lower())
        
        self.camera_count_label.setText(f"SỐ LƯỢNG VIDEO: {len(videos)}")
        
        if not videos:
            empty_label = QLabel("Không có file video trong thư mục")
            empty_label.setStyleSheet("""
                color: #a0a0a0;
                font-size: 16px;
                padding: 60px;
            """)
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid_layout.addWidget(empty_label, 0, 0)
            return
        
        logger.info(f"Found {len(videos)} videos in {self.video_folder}")
        
        # Add camera cards to grid (responsive columns)
        cols = 4
        for i, video_path in enumerate(videos):
            row = i // cols
            col = i % cols
            
            card = CameraCard(str(video_path), camera_id=i+1)
            card.apply_theme(self.is_dark)
            card.clicked.connect(self.on_video_clicked)
            self.grid_layout.addWidget(card, row, col)
        
        # Make columns stretch equally
        for col in range(cols):
            self.grid_layout.setColumnStretch(col, 1)
    
    def on_video_clicked(self, video_path: str):
        """Handle video selection"""
        logger.info(f"Video selected: {video_path}")
        self.video_selected.emit(video_path)
    
    def browse_file(self):
        """Open file browser"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn Video",
            "",
            "Video Files (*.mp4 *.avi *.mov *.mkv *.wmv);;All Files (*.*)"
        )
        
        if file_path:
            self.video_selected.emit(file_path)

    def apply_theme(self, is_dark: bool):
        """Apply theme to widget"""
        self.is_dark = is_dark
        
        if is_dark:
            self.setStyleSheet("QWidget { background-color: #1e1e2e; color: #e0e0e0; font-size: 14px; }")
            self.header.setStyleSheet("""
                QFrame {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1e1e2e, stop:0.5 #2a2a3c, stop:1 #1e1e2e);
                    border-bottom: 3px solid #3e3e5e;
                }
            """)
            self.system_status.setStyleSheet("background-color: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 8px;")
            self.time_label.setStyleSheet("color: #ffffff; font-size: 18px; font-weight: bold; font-family: monospace; background-color: rgba(0, 0, 0, 0.2); padding: 8px 15px; border-radius: 6px;")
            self.toolbar.setStyleSheet("QFrame { background-color: #2a2a3c; border-bottom: 1px solid #3e3e5e; }")
            self.camera_count_label.setStyleSheet("color: #89b4fa; font-size: 18px; font-weight: bold;")
            self.folder_label.setStyleSheet("color: #a0a0a0; font-size: 16px;")
            self.btn_refresh.setStyleSheet("""
                QPushButton { background-color: #45475a; color: #ffffff; border: 1px solid #585b70; border-radius: 6px; font-size: 16px; font-weight: bold; padding: 10px 20px; }
                QPushButton:hover { background-color: #585b70; }
            """)
            self.btn_browse.setStyleSheet("""
                QPushButton { background-color: #89b4fa; color: #1e1e2e; border: none; border-radius: 6px; font-size: 16px; font-weight: bold; padding: 10px 20px; }
                QPushButton:hover { background-color: #b4befe; }
            """)
            self.content.setStyleSheet("background-color: #1e1e2e;")
            self.section_header.setStyleSheet("color: #a0a0a0; font-size: 18px; font-weight: bold; letter-spacing: 1px; padding-bottom: 15px;")
            self.scroll_area.setStyleSheet("""
                QScrollArea { border: none; background-color: transparent; }
                QScrollBar:vertical { background-color: #2a2a3c; width: 12px; border-radius: 6px; }
                QScrollBar::handle:vertical { background-color: #45475a; border-radius: 6px; min-height: 40px; }
                QScrollBar::handle:vertical:hover { background-color: #585b70; }
            """)
            self.footer.setStyleSheet("QFrame { background-color: #2a2a3c; border-top: 1px solid #3e3e5e; }")
            self.footer_text.setStyleSheet("color: #a0a0a0; font-size: 16px;")
            self.version_label.setStyleSheet("color: #6c7086; font-size: 14px;")
            
        else:
            self.setStyleSheet("QWidget { background-color: #f5f5f5; color: #333333; font-size: 14px; }")
            self.header.setStyleSheet("""
                QFrame {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1976D2, stop:0.5 #2196F3, stop:1 #1976D2);
                    border-bottom: 3px solid #1565C0;
                }
            """)
            self.system_status.setStyleSheet("background-color: rgba(255, 255, 255, 0.2); border: 2px solid rgba(255, 255, 255, 0.5); border-radius: 8px;")
            self.time_label.setStyleSheet("color: #ffffff; font-size: 18px; font-weight: bold; font-family: monospace; background-color: rgba(0, 0, 0, 0.2); padding: 8px 15px; border-radius: 6px;")
            self.toolbar.setStyleSheet("QFrame { background-color: #ffffff; border-bottom: 2px solid #e0e0e0; }")
            self.camera_count_label.setStyleSheet("color: #1976D2; font-size: 18px; font-weight: bold;")
            self.folder_label.setStyleSheet("color: #666666; font-size: 16px;")
            self.btn_refresh.setStyleSheet("""
                QPushButton { background-color: #607D8B; color: #ffffff; border: none; border-radius: 6px; font-size: 16px; font-weight: bold; padding: 10px 20px; }
                QPushButton:hover { background-color: #546E7A; }
            """)
            self.btn_browse.setStyleSheet("""
                QPushButton { background-color: #1976D2; color: #ffffff; border: none; border-radius: 6px; font-size: 16px; font-weight: bold; padding: 10px 20px; }
                QPushButton:hover { background-color: #1565C0; }
            """)
            self.content.setStyleSheet("background-color: #f5f5f5;")
            self.section_header.setStyleSheet("color: #666666; font-size: 18px; font-weight: bold; letter-spacing: 1px; padding-bottom: 15px;")
            self.scroll_area.setStyleSheet("""
                QScrollArea { border: none; background-color: transparent; }
                QScrollBar:vertical { background-color: #e0e0e0; width: 12px; border-radius: 6px; }
                QScrollBar::handle:vertical { background-color: #BDBDBD; border-radius: 6px; min-height: 40px; }
                QScrollBar::handle:vertical:hover { background-color: #1976D2; }
            """)
            self.footer.setStyleSheet("QFrame { background-color: #ffffff; border-top: 2px solid #e0e0e0; }")
            self.footer_text.setStyleSheet("color: #666666; font-size: 16px;")
            self.version_label.setStyleSheet("color: #9E9E9E; font-size: 14px;")
        
        # Update cards
        for i in range(self.grid_layout.count()):
            item = self.grid_layout.itemAt(i)
            if item and item.widget():
                item.widget().apply_theme(is_dark)


# Keep old class name for compatibility
VideoThumbnail = CameraCard
