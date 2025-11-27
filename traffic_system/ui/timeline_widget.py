"""
Video Timeline Widget
Provides seek bar and timeline controls for video playback
"""

from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QSlider, 
                             QLabel, QPushButton)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen

from ..utils.logger import get_logger

logger = get_logger(__name__)


class VideoTimeline(QWidget):
    """
    Video timeline widget with seek bar and time display.
    
    Features:
    - Draggable seek bar
    - Time display (current/total)
    - Play/Pause button
    - Frame-accurate seeking
    
    Signals:
        position_changed: Emitted when user seeks to new position
        play_pause_clicked: Emitted when play/pause button is clicked
    """
    
    position_changed = pyqtSignal(int)  # frame number
    play_pause_clicked = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.total_frames = 0
        self.current_frame = 0
        self.fps = 30.0
        self.is_playing = False
        
        self._is_seeking = False  # Flag to prevent feedback loops
        
        self.setup_ui()
        
        
    def apply_theme(self, is_dark: bool):
        """Apply theme style"""
        if is_dark:
            self.setStyleSheet("background-color: transparent;")
            self.lbl_time.setStyleSheet("color: #e0e0e0; font-family: monospace; font-size: 14px;")
            self.lbl_frame.setStyleSheet("color: #a0a0a0; font-family: monospace; font-size: 14px;")
            self.lbl_fps.setStyleSheet("color: #a0a0a0; font-family: monospace; font-size: 14px;")
            self.slider.setStyleSheet("""
                QSlider::groove:horizontal {
                    border: 1px solid #3e3e5e;
                    height: 8px;
                    background: #313244;
                    margin: 2px 0;
                    border-radius: 4px;
                }
                QSlider::handle:horizontal {
                    background: #a6e3a1;
                    border: 1px solid #313244;
                    width: 18px;
                    margin: -5px 0;
                    border-radius: 9px;
                }
                QSlider::sub-page:horizontal {
                    background: #a6e3a1;
                    border-radius: 4px;
                }
            """)
            self.btn_play.setStyleSheet("""
                QPushButton {
                    background-color: #a6e3a1;
                    color: #1e1e2e;
                    border: none;
                    border-radius: 5px;
                    font-size: 16px;
                    padding: 5px;
                }
                QPushButton:hover {
                    background-color: #94e2d5;
                }
            """)
        else:
            self.setStyleSheet("background-color: transparent;")
            self.lbl_time.setStyleSheet("color: #333333; font-family: monospace; font-size: 14px;")
            self.lbl_frame.setStyleSheet("color: #666666; font-family: monospace; font-size: 14px;")
            self.lbl_fps.setStyleSheet("color: #666666; font-family: monospace; font-size: 14px;")
            self.slider.setStyleSheet("""
                QSlider::groove:horizontal {
                    border: 1px solid #999999;
                    height: 8px;
                    background: #e0e0e0;
                    margin: 2px 0;
                    border-radius: 4px;
                }
                QSlider::handle:horizontal {
                    background: #1976D2;
                    border: 1px solid #5c5c5c;
                    width: 18px;
                    margin: -5px 0;
                    border-radius: 9px;
                }
                QSlider::sub-page:horizontal {
                    background: #1976D2;
                    border-radius: 4px;
                }
            """)
            self.btn_play.setStyleSheet("""
                QPushButton {
                    background-color: #1976D2;
                    color: white;
                    border: none;
                    border-radius: 5px;
                    font-size: 16px;
                    padding: 5px;
                }
                QPushButton:hover {
                    background-color: #1565C0;
                }
            """)
        
        logger.debug("VideoTimeline initialized")
    
    def setup_ui(self):
        """Setup the UI components"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Timeline slider
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setMinimum(0)
        self.slider.setMaximum(100)
        self.slider.setValue(0)
        # Style set in apply_theme
        
        # Connect slider events
        self.slider.sliderPressed.connect(self._on_slider_pressed)
        self.slider.sliderReleased.connect(self._on_slider_released)
        self.slider.valueChanged.connect(self._on_slider_value_changed)
        
        layout.addWidget(self.slider)
        
        # Controls row
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(10)
        
        # Play/Pause button
        self.btn_play = QPushButton("▶")
        self.btn_play.setFixedWidth(40)
        # Style set in apply_theme
        self.btn_play.clicked.connect(self._on_play_pause)
        controls_layout.addWidget(self.btn_play)
        
        # Time display
        self.lbl_time = QLabel("00:00 / 00:00")
        # Style set in apply_theme
        controls_layout.addWidget(self.lbl_time)
        
        controls_layout.addStretch()
        
        # Frame display
        self.lbl_frame = QLabel("Frame: 0 / 0")
        # Style set in apply_theme
        controls_layout.addWidget(self.lbl_frame)
        
        # FPS display
        self.lbl_fps = QLabel("FPS: --")
        # Style set in apply_theme
        controls_layout.addWidget(self.lbl_fps)
        
        layout.addLayout(controls_layout)
    
    def set_total_frames(self, total_frames: int, fps: float = 30.0):
        """
        Set total frames and FPS.
        
        Args:
            total_frames: Total number of frames in video
            fps: Frames per second
        """
        self.total_frames = total_frames
        self.fps = fps
        self.slider.setMaximum(max(1, total_frames - 1))
        
        self._update_display()
        logger.debug(f"Timeline set: {total_frames} frames at {fps} FPS")
    
    def set_position(self, frame_number: int, fps: float = None):
        """
        Set current position.
        
        Args:
            frame_number: Current frame number
            fps: Optional current FPS to display
        """
        if self._is_seeking:
            return
        
        self.current_frame = frame_number
        
        # Update slider without triggering valueChanged
        self.slider.blockSignals(True)
        self.slider.setValue(frame_number)
        self.slider.blockSignals(False)
        
        if fps is not None:
            self.lbl_fps.setText(f"FPS: {fps:.1f}")
        
        self._update_display()
    
    def set_playing(self, is_playing: bool):
        """
        Update play/pause button state.
        
        Args:
            is_playing: True if video is playing
        """
        self.is_playing = is_playing
        self.btn_play.setText("⏸" if is_playing else "▶")
    
    def _update_display(self):
        """Update time and frame display"""
        # Calculate time
        current_time = self.current_frame / self.fps if self.fps > 0 else 0
        total_time = self.total_frames / self.fps if self.fps > 0 else 0
        
        current_str = self._format_time(current_time)
        total_str = self._format_time(total_time)
        
        self.lbl_time.setText(f"{current_str} / {total_str}")
        self.lbl_frame.setText(f"Frame: {self.current_frame} / {self.total_frames}")
    
    def _format_time(self, seconds: float) -> str:
        """Format seconds as MM:SS"""
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes:02d}:{secs:02d}"
    
    def _on_slider_pressed(self):
        """Handle slider press - start seeking"""
        self._is_seeking = True
    
    def _on_slider_released(self):
        """Handle slider release - emit seek position"""
        self._is_seeking = False
        frame = self.slider.value()
        self.current_frame = frame
        self.position_changed.emit(frame)
        self._update_display()
    
    def _on_slider_value_changed(self, value: int):
        """Handle slider value change during drag"""
        if self._is_seeking:
            self.current_frame = value
            self._update_display()
    
    def _on_play_pause(self):
        """Handle play/pause button click"""
        self.play_pause_clicked.emit()


class VideoProgressBar(QWidget):
    """
    Custom progress bar for video with markers.
    
    Features:
    - Progress indication
    - Clickable to seek
    - Marker support for events/annotations
    """
    
    position_changed = pyqtSignal(float)  # Progress 0-1
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.progress = 0.0  # 0-1
        self.markers = []  # List of (position, color, label)
        
        self.setMinimumHeight(20)
        self.setMaximumHeight(30)
        
        self.setCursor(Qt.CursorShape.PointingHandCursor)
    
    def set_progress(self, progress: float):
        """Set progress (0-1)"""
        self.progress = max(0, min(1, progress))
        self.update()
    
    def add_marker(self, position: float, color: QColor = None, label: str = ""):
        """
        Add a marker at position.
        
        Args:
            position: Position 0-1
            color: Marker color
            label: Marker label
        """
        if color is None:
            color = QColor(255, 0, 0)
        self.markers.append((position, color, label))
        self.update()
    
    def clear_markers(self):
        """Clear all markers"""
        self.markers.clear()
        self.update()
    
    def paintEvent(self, event):
        """Paint the progress bar"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w = self.width()
        h = self.height()
        
        # Background
        painter.fillRect(0, 0, w, h, QColor(50, 50, 50))
        
        # Progress fill
        progress_width = int(w * self.progress)
        painter.fillRect(0, 0, progress_width, h, QColor(76, 175, 80))
        
        # Border
        painter.setPen(QPen(QColor(100, 100, 100), 1))
        painter.drawRect(0, 0, w - 1, h - 1)
        
        # Draw markers
        for pos, color, label in self.markers:
            x = int(w * pos)
            painter.setPen(QPen(color, 2))
            painter.drawLine(x, 0, x, h)
    
    def mousePressEvent(self, event):
        """Handle click to seek"""
        if event.button() == Qt.MouseButton.LeftButton:
            position = event.pos().x() / self.width()
            self.progress = max(0, min(1, position))
            self.position_changed.emit(self.progress)
            self.update()
    
    def mouseMoveEvent(self, event):
        """Handle drag to seek"""
        if event.buttons() & Qt.MouseButton.LeftButton:
            position = event.pos().x() / self.width()
            self.progress = max(0, min(1, position))
            self.position_changed.emit(self.progress)
            self.update()
