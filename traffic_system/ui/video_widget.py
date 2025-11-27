"""
Video Widget with Calibration Support
Displays video and handles calibration interaction
"""

import cv2
import numpy as np
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QInputDialog, QMessageBox
from PyQt6.QtCore import QTimer, pyqtSignal, Qt
from PyQt6.QtGui import QImage, QPixmap
from typing import Optional
import time

from ..config.settings import Settings
from ..core.detector import VehicleDetector
from ..core.tracker import VehicleTracker
from ..core.calibration import CalibrationManager
from ..core.density_calculator import DensityCalculator
from ..core.traffic_light_detector import TrafficLightDetector
from ..utils.logger import get_logger

logger = get_logger(__name__)


class VideoWidget(QWidget):
    """Video display widget with calibration support"""
    
    frame_processed = pyqtSignal(dict)  # Emit statistics
    calibration_complete = pyqtSignal(float, float)  # Emit (road_length, road_width)
    position_changed = pyqtSignal(int, int, float)  # Emit (current_frame, total_frames, fps)
    traffic_light_calibration_complete = pyqtSignal()  # Emit when traffic light ROI is set
    
    def __init__(self, settings: Settings, calibration: CalibrationManager, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.calibration = calibration
        self.density_calculator = DensityCalculator(settings)
        
        # Traffic light detector
        self.traffic_light_detector = TrafficLightDetector()
        
        # Video components
        self.cap = None
        self.detector: Optional[VehicleDetector] = None
        self.tracker: Optional[VehicleTracker] = None
        
        # State
        self.is_playing = False
        self.is_calibrating = False
        self.is_calibrating_traffic_light = False  # New state for traffic light calibration
        self.current_frame = None
        self.frame_count = 0
        self.total_frames = 0
        self.video_fps = 30.0
        
        # FPS calculation
        self.last_frame_time = time.time()
        self.actual_fps = 0.0
        
        # Timer for video playback
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        
        self.setup_ui()
        logger.debug("VideoWidget initialized")
    
    def setup_ui(self):
        """Setup UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Video display label
        self.video_label = QLabel()
        self.video_label.setStyleSheet("background-color: black;")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setScaledContents(False)
        self.video_label.setMinimumSize(800, 600)
        
        # Enable mouse tracking for calibration
        self.video_label.setMouseTracking(True)
        self.video_label.mousePressEvent = self.mouse_press_event
        
        layout.addWidget(self.video_label)
    
    def load_video(self, video_path: str, detector: VehicleDetector, tracker: VehicleTracker):
        """Load video file"""
        self.detector = detector
        self.tracker = tracker
        
        if self.cap:
            self.cap.release()
        
        self.cap = cv2.VideoCapture(video_path)
        
        if not self.cap.isOpened():
            logger.error(f"Error opening video: {video_path}")
            return False
        
        # Get video info
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.video_fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
        
        logger.info(f"Loaded video: {video_path} ({self.total_frames} frames, {self.video_fps:.1f} fps)")
        
        # Get first frame
        ret, frame = self.cap.read()
        if ret:
            self.current_frame = frame
            self.display_frame(frame)
        
        self.frame_count = 0
        return True
    
    def get_video_fps(self) -> float:
        """Get video FPS"""
        return self.video_fps
    
    def seek_to_frame(self, frame_number: int):
        """Seek to specific frame"""
        if self.cap:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            self.frame_count = frame_number
            ret, frame = self.cap.read()
            if ret:
                self.current_frame = frame.copy()
                if self.is_playing:
                    # Process and display
                    processed_frame = self.process_frame(frame)
                    self.display_frame(processed_frame)
                else:
                    self.display_frame(frame)
            logger.debug(f"Seeked to frame {frame_number}")
    
    def play(self):
        """Start playback"""
        if self.cap and not self.is_playing:
            self.is_playing = True
            fps = self.cap.get(cv2.CAP_PROP_FPS) or 30
            if self.settings.video.fps_limit:
                fps = min(fps, self.settings.video.fps_limit)
            self.timer.start(int(1000 / fps))
    
    def pause(self):
        """Pause playback"""
        self.is_playing = False
        self.timer.stop()
    
    def stop(self):
        """Stop playback"""
        self.is_playing = False
        self.timer.stop()
        if self.cap:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self.cap.read()
            if ret:
                self.current_frame = frame
                self.display_frame(frame)
        self.frame_count = 0
    
    def update_frame(self):
        """Update frame during playback"""
        if not self.cap or not self.is_playing:
            return
        
        ret, frame = self.cap.read()
        if not ret:
            # Loop video
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            self.frame_count = 0
            return
        
        self.frame_count += 1
        
        # Calculate actual FPS
        current_time = time.time()
        elapsed = current_time - self.last_frame_time
        if elapsed > 0:
            self.actual_fps = 1.0 / elapsed
        self.last_frame_time = current_time
        
        # Skip frames if configured
        if self.settings.video.frame_skip > 1:
            if self.frame_count % self.settings.video.frame_skip != 0:
                return
        
        self.current_frame = frame.copy()
        
        # Process frame
        processed_frame = self.process_frame(frame)
        self.display_frame(processed_frame)
        
        # Emit position change
        self.position_changed.emit(self.frame_count, self.total_frames, self.actual_fps)
    
    def process_frame(self, frame: np.ndarray) -> np.ndarray:
        """Process frame with detection and tracking"""
        if not self.detector or not self.tracker:
            return frame
        
        if not self.calibration.calibration:
            return frame
        
        # Check traffic light state first
        traffic_light_state = None
        skip_congestion = False
        if self.traffic_light_detector.is_enabled:
            traffic_light_state = self.traffic_light_detector.detect(frame)
            skip_congestion = traffic_light_state.should_skip_congestion_check
            # Draw traffic light ROI
            frame = self.traffic_light_detector.draw_roi(frame, traffic_light_state)
        
        # Detect vehicles
        vehicle_types = list(self.settings.VEHICLE_DIMENSIONS.keys())
        detections = self.detector.detect(frame, vehicle_types)
        
        # Filter detections by calibration region
        filtered_detections = []
        for det in detections:
            if self.calibration.is_bbox_in_region(det['bbox']):
                filtered_detections.append(det)
        
        # Track vehicles
        tracks = self.tracker.update(filtered_detections, frame)
        
        # Draw tracks
        for track in tracks:
            x1, y1, x2, y2 = map(int, track['bbox'])
            class_name = track['class']
            track_id = track['track_id']
            
            # Get color
            color = self.settings.VEHICLE_COLORS.get(class_name, (255, 255, 255))
            
            # Draw bounding box
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            
            # Draw label with background
            label = f"{class_name} #{track_id}"
            (text_w, text_h), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)
            
            # Draw background box
            cv2.rectangle(frame, (x1, y1 - text_h - 8), (x1 + text_w, y1), color, -1)
            
            # Draw text (white or black depending on brightness, but white on colored bg usually works)
            # Use black text for better contrast on bright colors
            text_color = (0, 0, 0) if sum(color) > 300 else (255, 255, 255)
            cv2.putText(frame, label, (x1, y1 - 4),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, text_color, 1)
        
        # Draw detection region
        frame = self.calibration.draw_region(frame)
        
        # Calculate density
        vehicle_counts = self.tracker.get_vehicle_counts(tracks)
        road_area = self.calibration.get_road_area()
        occupied_area, density_percentage = self.density_calculator.calculate_density(
            vehicle_counts, road_area
        )
        
        # Determine congestion status
        if skip_congestion:
            # Red/Yellow light detected - don't report congestion
            level_name = "NORMAL"
            if traffic_light_state.is_red:
                status_text = "DEN DO - Khong xet ket xe"
                color_bgr = (0, 0, 255)  # Red
            else:
                status_text = "DEN VANG - Khong xet ket xe"
                color_bgr = (0, 255, 255)  # Yellow
        else:
            # Normal congestion detection
            level_name, status_text, color_bgr = self.density_calculator.get_density_level(
                density_percentage
            )
        
        # Emit statistics to side panel (no overlay on video)
        stats = {
            'vehicle_counts': vehicle_counts,
            'occupied_area': occupied_area,
            'density_percentage': density_percentage,
            'congestion_level': level_name,
            'congestion_status': status_text,
            'congestion_color': color_bgr,
            'tracks': tracks,  # Full tracks for speed estimation
            'traffic_light_active': skip_congestion,  # Whether traffic light is red/yellow
            'traffic_light_state': traffic_light_state.dominant_color if traffic_light_state else None
        }
        
        self.frame_processed.emit(stats)
        
        return frame
    

    
    def display_frame(self, frame: np.ndarray):
        """Display frame in label"""
        if frame is None:
            return
        
        # If calibrating road region, draw calibration points
        if self.is_calibrating:
            frame = self.calibration.draw_points(frame)
            
            # Draw instruction based on mode
            required = self.calibration.get_required_points()
            current_points = len(self.calibration.get_points())
            points_left = required - current_points
            
            if points_left > 0:
                mode = self.calibration.get_mode()
                from ..core.calibration import CalibrationMode
                
                if mode == CalibrationMode.POLYGON:
                    text = f"Click {points_left} diem nua de hoan tat VUNG QUAN SAT"
                elif mode == CalibrationMode.CIRCLE:
                    if current_points == 0:
                        text = "Click chon TAM VONG XOAY"
                    else:
                        text = "Click chon diem tren BAN KINH"
                elif mode == CalibrationMode.ELLIPSE:
                    if current_points == 0:
                        text = "Click chon TAM VONG XOAY"
                    elif current_points == 1:
                        text = "Click chon diem tren TRUC CHINH"
                    else:
                        text = "Click chon diem tren TRUC PHU"
                else:
                    text = f"Click {points_left} diem nua"
                
                cv2.putText(frame, text, (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        
        # If calibrating traffic light ROI
        elif self.is_calibrating_traffic_light:
            frame = self.traffic_light_detector.draw_points(frame)
            
            # Draw instruction
            points_left = 4 - len(self.traffic_light_detector.get_points())
            if points_left > 0:
                text = f"Click {points_left} diem nua de chon VUNG DEN GIAO THONG"
                cv2.putText(frame, text, (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 255), 2)
        
        # Convert to RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_frame.shape
        bytes_per_line = ch * w
        
        # Create QImage
        qt_image = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        
        # Scale to fit label while maintaining aspect ratio
        pixmap = QPixmap.fromImage(qt_image)
        scaled_pixmap = pixmap.scaled(
            self.video_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        
        self.video_label.setPixmap(scaled_pixmap)
    
    def start_calibration(self):
        """Start calibration mode"""
        self.is_calibrating = True
        self.is_calibrating_traffic_light = False
        self.calibration.reset()
        self.pause()
        
        # Show first frame for calibration
        if self.current_frame is not None:
            self.display_frame(self.current_frame)
    
    def start_traffic_light_calibration(self):
        """Start traffic light ROI calibration mode"""
        self.is_calibrating_traffic_light = True
        self.is_calibrating = False
        self.traffic_light_detector.reset()
        self.pause()
        
        # Show first frame for calibration
        if self.current_frame is not None:
            self.display_frame(self.current_frame)
    
    def clear_traffic_light_roi(self):
        """Clear traffic light ROI"""
        self.traffic_light_detector.clear_roi()
        if self.current_frame is not None:
            self.display_frame(self.current_frame)
    
    def mouse_press_event(self, event):
        """Handle mouse press for calibration"""
        if not self.is_calibrating and not self.is_calibrating_traffic_light:
            return
        
        if event.button() == Qt.MouseButton.LeftButton:
            # Get click position relative to image
            label_size = self.video_label.size()
            pixmap = self.video_label.pixmap()
            
            if pixmap is None:
                return
            
            # Calculate scaling
            pixmap_size = pixmap.size()
            scale_x = self.current_frame.shape[1] / pixmap_size.width()
            scale_y = self.current_frame.shape[0] / pixmap_size.height()
            
            # Calculate offset (image is centered in label)
            offset_x = (label_size.width() - pixmap_size.width()) / 2
            offset_y = (label_size.height() - pixmap_size.height()) / 2
            
            # Get click position in image coordinates
            click_x = int((event.pos().x() - offset_x) * scale_x)
            click_y = int((event.pos().y() - offset_y) * scale_y)
            
            # Ensure within bounds
            if 0 <= click_x < self.current_frame.shape[1] and 0 <= click_y < self.current_frame.shape[0]:
                
                if self.is_calibrating:
                    # Add road calibration point
                    complete = self.calibration.add_point(click_x, click_y)
                    
                    # Update display
                    self.display_frame(self.current_frame)
                    
                    # If 4 points added, ask for dimensions
                    if complete:
                        self.finish_calibration()
                
                elif self.is_calibrating_traffic_light:
                    # Add traffic light ROI point
                    complete = self.traffic_light_detector.add_point(click_x, click_y)
                    
                    # Update display
                    self.display_frame(self.current_frame)
                    
                    # If 4 points added, finish
                    if complete:
                        self.finish_traffic_light_calibration()
    
    def finish_calibration(self):
        """Finish calibration by asking for dimensions"""
        from ..core.calibration import CalibrationMode
        
        try:
            mode = self.calibration.get_mode()
            
            # For circle mode, ask for area directly
            if mode == CalibrationMode.CIRCLE:
                road_area, ok = QInputDialog.getDouble(
                    self,
                    "Diện tích vòng xoay",
                    "Nhập diện tích thực tế của vùng vòng xoay (m²):",
                    200.0,  # Default area
                    1.0, 10000.0, 1
                )
                
                if not ok:
                    self.calibration.reset()
                    self.is_calibrating = False
                    if self.current_frame is not None:
                        self.display_frame(self.current_frame)
                    return
                
                # For circle, we pass area as both length and width
                # The finalize_calibration will handle it
                success = self.calibration.finalize_calibration_with_area(road_area)
                
                if success:
                    self.is_calibrating = False
                    if self.current_frame is not None:
                        self.display_frame(self.current_frame)
                    self.calibration_complete.emit(road_area, 0)  # 0 for width since we use area
                return
            
            # For other modes, ask for dimensions
            if mode == CalibrationMode.ELLIPSE:
                length_prompt = "Nhập chiều dài trục chính (a) tính bằng mét:"
                length_title = "Trục chính elip (a)"
                width_prompt = "Nhập chiều dài trục phụ (b) tính bằng mét:"
                width_title = "Trục phụ elip (b)"
            else:
                length_prompt = "Nhập chiều dài thực tế (Ls) tính bằng mét:"
                length_title = "Chiều dài đường (Ls)"
                width_prompt = "Nhập chiều rộng thực tế (Ws) tính bằng mét:"
                width_title = "Chiều rộng đường (Ws)"
            
            road_length, ok = QInputDialog.getDouble(
                self,
                length_title,
                length_prompt,
                self.settings.calibration.default_road_length,
                1.0, 1000.0, 1
            )
            
            if not ok:
                self.calibration.reset()
                self.is_calibrating = False
                if self.current_frame is not None:
                    self.display_frame(self.current_frame)
                return
            
            # Ask for road width
            road_width, ok = QInputDialog.getDouble(
                self,
                width_title,
                width_prompt,
                self.settings.calibration.default_road_width,
                1.0, 100.0, 1
            )
            
            if not ok:
                self.calibration.reset()
                self.is_calibrating = False
                if self.current_frame is not None:
                    self.display_frame(self.current_frame)
                return
            
            # Finalize calibration
            success = self.calibration.finalize_calibration(
                road_length, road_width,
                self.settings.calibration.use_perspective_transform
            )
            
            if success:
                self.is_calibrating = False
                if self.current_frame is not None:
                    self.display_frame(self.current_frame)
                self.calibration_complete.emit(road_length, road_width)
        
        except RuntimeError as e:
            # Handle case when widget is deleted during dialog
            logger.warning(f"Calibration interrupted: {e}")
            self.is_calibrating = False
    
    def finish_traffic_light_calibration(self):
        """Finish traffic light ROI calibration"""
        self.is_calibrating_traffic_light = False
        
        QMessageBox.information(
            self,
            "Hoàn tất",
            "Đã thiết lập vùng phát hiện đèn giao thông!\n\n"
            "Khi phát hiện đèn đỏ hoặc vàng, hệ thống sẽ\n"
            "không cảnh báo kẹt xe để tránh nhầm lẫn."
        )
        
        if self.current_frame is not None:
            self.display_frame(self.current_frame)
        
        self.traffic_light_calibration_complete.emit()
        logger.info("Traffic light ROI calibration complete")
    
    def get_traffic_light_detector(self) -> TrafficLightDetector:
        """Get traffic light detector instance"""
        return self.traffic_light_detector
    
    def set_traffic_light_roi(self, points: list):
        """Set traffic light ROI from saved config"""
        if points and len(points) == 4:
            self.traffic_light_detector.set_roi([tuple(p) for p in points])
    
    def closeEvent(self, event):
        """Clean up on close"""
        # Reset calibration state
        self.is_calibrating = False
        self.is_calibrating_traffic_light = False
        
        self.pause()
        if self.cap:
            self.cap.release()
        event.accept()
