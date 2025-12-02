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
from ..utils.logger import get_logger

logger = get_logger(__name__)


class VideoWidget(QWidget):
    """Video display widget with calibration support"""
    
    frame_processed = pyqtSignal(dict)  # Emit statistics
    calibration_complete = pyqtSignal(float, float)  # Emit (road_length, road_width)
    calibration_cancelled = pyqtSignal()  # Emit when calibration is cancelled
    position_changed = pyqtSignal(int, int, float)  # Emit (current_frame, total_frames, fps)
    
    def __init__(self, settings: Settings, calibration: CalibrationManager, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.calibration = calibration
        self.density_calculator = DensityCalculator(settings)
        
        # Video components
        self.cap = None
        self.detector: Optional[VehicleDetector] = None
        self.tracker: Optional[VehicleTracker] = None
        
        # State
        self.is_playing = False
        self.is_calibrating = False
        self.current_frame = None
        self.frame_count = 0
        self.total_frames = 0
        self.video_fps = 30.0
        
        # Drag state for circle calibration
        self.is_dragging_circle = False
        self.drag_center = None
        self.drag_radius = 0
        
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
        self.video_label.mouseMoveEvent = self.mouse_move_event
        self.video_label.mouseReleaseEvent = self.mouse_release_event
        
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
        if not self.tracker:
            return frame
        
        if not self.calibration.calibration:
            return frame
        
        # Check if using YOLO integrated tracker (botsort/bytetrack)
        is_yolo_tracker = hasattr(self.tracker, 'tracker_type') and \
                          self.tracker.tracker_type in ['botsort', 'bytetrack']
        
        if is_yolo_tracker:
            # YOLO tracker: use detector.detect_with_tracking()
            if not self.detector:
                return frame
            
            vehicle_types = list(self.settings.VEHICLE_DIMENSIONS.keys())
            tracker_type = self.tracker.tracker_type  # 'botsort' or 'bytetrack'
            
            # Build tracker config from settings
            tracker_config = {
                'track_high_thresh': self.settings.tracker.track_high_thresh,
                'track_low_thresh': self.settings.tracker.track_low_thresh,
                'new_track_thresh': self.settings.tracker.new_track_thresh,
                'track_buffer': self.settings.tracker.track_buffer,
                'match_thresh': self.settings.tracker.match_thresh,
            }
            
            # Add BoT-SORT specific parameters
            if tracker_type == "botsort":
                tracker_config.update({
                    'gmc_method': getattr(self.settings.tracker, 'gmc_method', 'sparseOptFlow'),
                    'proximity_thresh': getattr(self.settings.tracker, 'proximity_thresh', 0.5),
                    'appearance_thresh': getattr(self.settings.tracker, 'appearance_thresh', 0.25),
                })
            
            # Detect with YOLO's built-in tracking
            detections = self.detector.detect_with_tracking(
                frame, vehicle_types,
                tracker_type=tracker_type,
                persist=True,
                tracker_config=tracker_config
            )
            
            # Filter detections by calibration region
            filtered_detections = []
            for det in detections:
                if self.calibration.is_bbox_in_region(det['bbox']):
                    filtered_detections.append(det)
            
            # Update tracker with pre-tracked detections
            tracks = self.tracker.update(filtered_detections, frame)
        else:
            # DeepSORT: Detect first, then track
            if not self.detector:
                return frame
            
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
            # Tracker output is always in xyxy format [x1, y1, x2, y2]
            bbox = track['bbox']
            x1, y1, x2, y2 = map(int, bbox)
                
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
        
        # Calculate per-lane density if multiple lanes
        lane_densities = {}
        num_lanes = self.calibration.get_num_lanes()
        if num_lanes > 1 and self.calibration.calibration and self.calibration.calibration.lanes:
            for lane_num in range(1, num_lanes + 1):
                # Count vehicles in this lane
                lane_vehicle_counts = {vtype: 0 for vtype in self.settings.VEHICLE_DIMENSIONS.keys()}
                
                for track in tracks:
                    # Get center of bounding box
                    x1, y1, x2, y2 = track['bbox']
                    center_x = (x1 + x2) / 2
                    center_y = (y1 + y2) / 2
                    
                    # Check which lane this vehicle is in
                    vehicle_lane = self.calibration.get_point_lane(center_x, center_y)
                    if vehicle_lane == lane_num:
                        vehicle_type = track['class']
                        if vehicle_type in lane_vehicle_counts:
                            lane_vehicle_counts[vehicle_type] += 1
                
                # Calculate density for this lane
                lane_area = self.calibration.get_lane_area(lane_num)
                lane_occupied_area, lane_density_pct = self.density_calculator.calculate_density(
                    lane_vehicle_counts, lane_area
                )
                
                # Get congestion level for this lane
                lane_level, lane_status, lane_color = self.density_calculator.get_density_level(
                    lane_density_pct
                )
                
                lane_densities[f'lane{lane_num}'] = {
                    'density_percentage': lane_density_pct,
                    'occupied_area': lane_occupied_area,
                    'vehicle_counts': lane_vehicle_counts,
                    'congestion_level': lane_level,
                    'congestion_status': lane_status,
                    'congestion_color': lane_color
                }
        
        # Determine congestion status
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
            'lane_densities': lane_densities  # Per-lane density info
        }
        
        self.frame_processed.emit(stats)
        
        return frame
    

    
    def display_frame(self, frame: np.ndarray):
        """Display frame in label"""
        if frame is None:
            return
        
        # Make a copy to draw on
        display_frame = frame.copy()
        
        # If calibrating road region, draw calibration points
        if self.is_calibrating:
            display_frame = self.calibration.draw_points(display_frame)
            
            # Draw circle preview when dragging
            if self.is_dragging_circle and self.drag_center and self.drag_radius > 0:
                cv2.circle(display_frame, self.drag_center, self.drag_radius, (0, 255, 0), 2)
                # Draw radius line
                edge_point = (self.drag_center[0] + self.drag_radius, self.drag_center[1])
                cv2.line(display_frame, self.drag_center, edge_point, (0, 255, 255), 1)
                # Show radius value
                radius_text = f"R = {self.drag_radius} px"
                cv2.putText(display_frame, radius_text, 
                           (self.drag_center[0] + 10, self.drag_center[1] - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            
            # Draw instruction based on mode
            required = self.calibration.get_required_points()
            current_points = len(self.calibration.get_points())
            points_left = required - current_points
            
            mode = self.calibration.get_mode()
            from ..core.calibration import CalibrationMode
            
            # Get lane info for multi-lane mode
            num_lanes = self.calibration.get_num_lanes()
            current_lane = self.calibration.get_current_lane()
            lane_info = f" - Lan {current_lane}/{num_lanes}" if num_lanes > 1 else ""
            
            if mode == CalibrationMode.CIRCLE:
                if self.is_dragging_circle:
                    text = "Keo chuot de chon BAN KINH - Tha chuot de hoan tat"
                elif current_points == 0:
                    text = "Click va keo de ve VONG TRON (giu chuot keo ra)"
                else:
                    text = "Da chon vong tron"
            elif mode == CalibrationMode.POLYGON:
                if points_left > 0:
                    text = f"Click {points_left} diem nua de hoan tat VUNG QUAN SAT{lane_info}"
                else:
                    text = f"Da chon vung quan sat{lane_info}"
            elif mode == CalibrationMode.ELLIPSE:
                if current_points == 0:
                    text = "Click chon TAM VONG XOAY"
                elif current_points == 1:
                    text = "Click chon diem tren TRUC CHINH"
                elif current_points == 2:
                    text = "Click chon diem tren TRUC PHU"
                else:
                    text = "Da chon elip"
            else:
                text = f"Click {points_left} diem nua{lane_info}"
            
            cv2.putText(display_frame, text, (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        
        # Convert to RGB
        rgb_frame = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
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
        self.calibration.reset()
        self.pause()
        
        # Reset drag state
        self.is_dragging_circle = False
        self.drag_center = None
        self.drag_radius = 0
        
        # Show first frame for calibration
        if self.current_frame is not None:
            self.display_frame(self.current_frame)
    
    def mouse_press_event(self, event):
        """Handle mouse press for calibration"""
        if not self.is_calibrating:
            return
        
        if event.button() == Qt.MouseButton.LeftButton:
            # Get click position relative to image
            click_x, click_y = self._get_image_coords(event.pos())
            
            if click_x is None:
                return
            
            # Ensure within bounds
            if 0 <= click_x < self.current_frame.shape[1] and 0 <= click_y < self.current_frame.shape[0]:
                
                from ..core.calibration import CalibrationMode
                mode = self.calibration.get_mode()
                
                # For circle mode, start drag operation
                if mode == CalibrationMode.CIRCLE and len(self.calibration.get_points()) == 0:
                    self.is_dragging_circle = True
                    self.drag_center = (click_x, click_y)
                    self.drag_radius = 0
                    # Add center point
                    self.calibration.add_point(click_x, click_y)
                    self.display_frame(self.current_frame)
                    return
                
                # Add road calibration point
                complete = self.calibration.add_point(click_x, click_y)
                
                # Update display
                self.display_frame(self.current_frame)
                
                # If points complete, ask for dimensions
                if complete:
                    self.finish_calibration()
    
    def mouse_move_event(self, event):
        """Handle mouse move for circle drag calibration"""
        if not self.is_dragging_circle or self.current_frame is None:
            return
        
        # Get current position
        mouse_x, mouse_y = self._get_image_coords(event.pos())
        
        if mouse_x is None:
            return
        
        # Calculate radius from center
        if self.drag_center:
            dx = mouse_x - self.drag_center[0]
            dy = mouse_y - self.drag_center[1]
            self.drag_radius = int(np.sqrt(dx*dx + dy*dy))
            
            # Update calibration manager's radius for preview
            self.calibration.radius = self.drag_radius
            
            # Update display with circle preview
            self.display_frame(self.current_frame)
    
    def mouse_release_event(self, event):
        """Handle mouse release for circle drag calibration"""
        if not self.is_dragging_circle:
            return
        
        if event.button() == Qt.MouseButton.LeftButton:
            # Get release position
            release_x, release_y = self._get_image_coords(event.pos())
            
            if release_x is not None and self.drag_center:
                # Calculate final radius
                dx = release_x - self.drag_center[0]
                dy = release_y - self.drag_center[1]
                self.drag_radius = int(np.sqrt(dx*dx + dy*dy))
                
                # Minimum radius check
                if self.drag_radius < 10:
                    self.drag_radius = 10
                
                # Add edge point to complete circle
                edge_x = self.drag_center[0] + self.drag_radius
                edge_y = self.drag_center[1]
                complete = self.calibration.add_point(edge_x, edge_y)
                
                logger.debug(f"Circle calibration: center={self.drag_center}, radius={self.drag_radius}, complete={complete}")
                
                self.is_dragging_circle = False
                self.display_frame(self.current_frame)
                
                if complete:
                    self.finish_calibration()
            else:
                # Failed to get coordinates, cancel
                logger.warning("Failed to get release coordinates for circle calibration")
                self._cancel_calibration()
    
    def _get_image_coords(self, pos):
        """Convert widget position to image coordinates"""
        label_size = self.video_label.size()
        pixmap = self.video_label.pixmap()
        
        if pixmap is None or self.current_frame is None:
            return None, None
        
        # Calculate scaling
        pixmap_size = pixmap.size()
        scale_x = self.current_frame.shape[1] / pixmap_size.width()
        scale_y = self.current_frame.shape[0] / pixmap_size.height()
        
        # Calculate offset (image is centered in label)
        offset_x = (label_size.width() - pixmap_size.width()) / 2
        offset_y = (label_size.height() - pixmap_size.height()) / 2
        
        # Get position in image coordinates
        img_x = int((pos.x() - offset_x) * scale_x)
        img_y = int((pos.y() - offset_y) * scale_y)
        
        return img_x, img_y
    
    def finish_calibration(self):
        """Finish calibration by asking for dimensions"""
        from ..core.calibration import CalibrationMode
        
        try:
            mode = self.calibration.get_mode()
            logger.debug(f"Finishing calibration, mode: {mode}, points: {len(self.calibration.get_points())}")
            
            # For circle mode, ask for outer and inner radii
            if mode == CalibrationMode.CIRCLE:
                # Ask for outer radius (r1)
                radius_outer, ok = QInputDialog.getDouble(
                    self,
                    "Bán kính ngoài (r1)",
                    "Nhập bán kính ngoài r1 của vòng xoay (m):",
                    15.0,  # Default outer radius
                    0.1, 500.0, 1
                )
                
                if not ok:
                    self._cancel_calibration()
                    return
                
                # Ask for inner radius (r2)
                radius_inner, ok = QInputDialog.getDouble(
                    self,
                    "Bán kính trong (r2)",
                    f"Nhập bán kính trong r2 của vòng xoay (m):\n(Phải nhỏ hơn r1 = {radius_outer:.1f}m)",
                    5.0,  # Default inner radius
                    0.0, radius_outer - 0.1, 1
                )
                
                if not ok:
                    self._cancel_calibration()
                    return
                
                # Calculate area: π(r1² - r2²)
                import math
                road_area = math.pi * (radius_outer**2 - radius_inner**2)
                
                # Use new method with radii
                success = self.calibration.finalize_calibration_with_radii(radius_outer, radius_inner)
                
                if success:
                    self.is_calibrating = False
                    if self.current_frame is not None:
                        self.display_frame(self.current_frame)
                    # Emit radii as length/width for display purposes
                    self.calibration_complete.emit(radius_outer, radius_inner)
                else:
                    # Calibration failed - show error and cancel
                    QMessageBox.warning(
                        self,
                        "Lỗi Hiệu Chỉnh",
                        "Không thể hoàn thành hiệu chỉnh vòng tròn.\nVui lòng thử lại."
                    )
                    self._cancel_calibration()
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
                self._cancel_calibration()
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
                self._cancel_calibration()
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
            self.calibration_cancelled.emit()
    
    def _cancel_calibration(self):
        """Cancel calibration and reset state"""
        self.calibration.reset()
        self.is_calibrating = False
        self.is_dragging_circle = False
        self.drag_center = None
        self.drag_radius = 0
        if self.current_frame is not None:
            self.display_frame(self.current_frame)
        self.calibration_cancelled.emit()
        logger.info("Calibration cancelled by user")
    
    def closeEvent(self, event):
        """Clean up on close"""
        # Reset calibration state
        self.is_calibrating = False
        
        self.pause()
        if self.cap:
            self.cap.release()
        event.accept()
