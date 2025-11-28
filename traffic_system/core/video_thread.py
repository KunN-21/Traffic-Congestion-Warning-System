"""
Video Processing Thread
Handles video processing in a separate thread for better performance
"""

import cv2
import numpy as np
import time
from typing import Optional, Dict, List
from dataclasses import dataclass
from queue import Queue, Empty
from threading import Thread, Event

from PyQt6.QtCore import QObject, pyqtSignal

from ..utils.logger import get_logger, PerformanceLogger
from ..config.settings import Settings
from ..core.detector import VehicleDetector
from ..core.tracker import VehicleTracker
from ..core.calibration import CalibrationManager
from ..core.density_calculator import DensityCalculator

logger = get_logger(__name__)
perf_logger = PerformanceLogger("video_thread")


@dataclass
class FrameData:
    """Data container for processed frame"""
    frame: np.ndarray
    frame_number: int
    timestamp: float
    tracks: List[Dict]
    vehicle_counts: Dict[str, int]
    occupied_area: float
    density_percentage: float
    congestion_level: str
    congestion_status: str
    congestion_color: tuple
    fps: float


class VideoProcessingThread(QObject):
    """
    Threaded video processor for better performance.
    
    Features:
    - Separate thread for video reading
    - Separate thread for detection/tracking
    - Frame queue for smooth playback
    - Performance metrics
    
    Signals:
        frame_ready: Emitted when a processed frame is ready
        stats_updated: Emitted with statistics update
        processing_finished: Emitted when video ends
        error_occurred: Emitted on error
    """
    
    # Signals
    frame_ready = pyqtSignal(np.ndarray, dict)  # frame, stats
    stats_updated = pyqtSignal(dict)
    processing_finished = pyqtSignal()
    error_occurred = pyqtSignal(str)
    position_changed = pyqtSignal(int, int)  # current_frame, total_frames
    
    def __init__(self, settings: Settings, calibration: CalibrationManager):
        super().__init__()
        self.settings = settings
        self.calibration = calibration
        self.density_calculator = DensityCalculator(settings)
        
        # Components
        self.detector: Optional[VehicleDetector] = None
        self.tracker: Optional[VehicleTracker] = None
        self.cap: Optional[cv2.VideoCapture] = None
        
        # Threading
        self._stop_event = Event()
        self._pause_event = Event()
        self._processing_thread: Optional[Thread] = None
        
        # Frame queue for buffering
        self._frame_queue: Queue = Queue(maxsize=30)
        
        # State
        self.is_running = False
        self.is_paused = False
        self.current_frame_number = 0
        self.total_frames = 0
        self.video_fps = 30.0
        
        # Performance tracking
        self._frame_times: List[float] = []
        self._last_fps_update = time.time()
        self._current_fps = 0.0
        
        logger.info("VideoProcessingThread initialized")
    
    def set_components(self, detector: VehicleDetector, tracker: VehicleTracker):
        """Set detector and tracker components"""
        self.detector = detector
        self.tracker = tracker
        logger.info("Detector and tracker set for video processing")
    
    def load_video(self, video_path: str) -> bool:
        """
        Load video file.
        
        Args:
            video_path: Path to video file
        
        Returns:
            True if video loaded successfully
        """
        try:
            if self.cap is not None:
                self.cap.release()
            
            self.cap = cv2.VideoCapture(video_path)
            
            if not self.cap.isOpened():
                logger.error(f"Failed to open video: {video_path}")
                return False
            
            self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
            self.video_fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
            self.current_frame_number = 0
            
            logger.info(f"Video loaded: {video_path}")
            logger.info(f"  Total frames: {self.total_frames}")
            logger.info(f"  FPS: {self.video_fps:.2f}")
            
            return True
            
        except Exception as e:
            logger.exception(f"Error loading video: {e}")
            return False
    
    def start(self):
        """Start video processing in background thread"""
        if self.is_running:
            logger.warning("Video processing already running")
            return
        
        if self.cap is None or not self.cap.isOpened():
            logger.error("No video loaded")
            self.error_occurred.emit("No video loaded")
            return
        
        if self.detector is None or self.tracker is None:
            logger.error("Detector/Tracker not initialized")
            self.error_occurred.emit("Detector/Tracker not initialized")
            return
        
        self._stop_event.clear()
        self._pause_event.clear()
        self.is_running = True
        self.is_paused = False
        
        self._processing_thread = Thread(target=self._processing_loop, daemon=True)
        self._processing_thread.start()
        
        logger.info("Video processing started")
    
    def pause(self):
        """Pause video processing"""
        if self.is_running and not self.is_paused:
            self._pause_event.set()
            self.is_paused = True
            logger.info("Video processing paused")
    
    def resume(self):
        """Resume video processing"""
        if self.is_running and self.is_paused:
            self._pause_event.clear()
            self.is_paused = False
            logger.info("Video processing resumed")
    
    def stop(self):
        """Stop video processing"""
        if self.is_running:
            self._stop_event.set()
            self._pause_event.clear()  # Unblock if paused
            
            if self._processing_thread:
                self._processing_thread.join(timeout=2.0)
            
            self.is_running = False
            self.is_paused = False
            
            logger.info("Video processing stopped")
    
    def seek(self, frame_number: int):
        """
        Seek to specific frame.
        
        Args:
            frame_number: Target frame number
        """
        if self.cap is None:
            return
        
        was_running = self.is_running
        if was_running:
            self.pause()
        
        # Clear frame queue
        while not self._frame_queue.empty():
            try:
                self._frame_queue.get_nowait()
            except Empty:
                break
        
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        self.current_frame_number = frame_number
        
        logger.debug(f"Seeked to frame {frame_number}")
        
        if was_running:
            self.resume()
    
    def get_frame_at(self, frame_number: int) -> Optional[np.ndarray]:
        """Get frame at specific position without advancing"""
        if self.cap is None:
            return None
        
        current_pos = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES))
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        
        ret, frame = self.cap.read()
        
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, current_pos)
        
        return frame if ret else None
    
    def _processing_loop(self):
        """Main processing loop running in thread"""
        frame_interval = 1.0 / self.video_fps
        if self.settings.video.fps_limit:
            frame_interval = max(frame_interval, 1.0 / self.settings.video.fps_limit)
        
        last_frame_time = time.time()
        
        try:
            while not self._stop_event.is_set():
                # Check for pause
                while self._pause_event.is_set() and not self._stop_event.is_set():
                    time.sleep(0.1)
                
                if self._stop_event.is_set():
                    break
                
                # Frame timing
                current_time = time.time()
                elapsed = current_time - last_frame_time
                
                if elapsed < frame_interval:
                    time.sleep(frame_interval - elapsed)
                
                last_frame_time = time.time()
                
                # Read frame
                perf_logger.start("read_frame")
                ret, frame = self.cap.read()
                perf_logger.end("read_frame")
                
                if not ret:
                    # Try to loop video
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    self.current_frame_number = 0
                    continue
                
                self.current_frame_number += 1
                
                # Skip frames if configured
                if self.settings.video.frame_skip > 1:
                    if self.current_frame_number % self.settings.video.frame_skip != 0:
                        continue
                
                # Process frame
                processed_frame, stats = self._process_frame(frame)
                
                # Calculate FPS
                self._update_fps()
                stats['fps'] = self._current_fps
                
                # Emit signals
                self.frame_ready.emit(processed_frame, stats)
                self.position_changed.emit(self.current_frame_number, self.total_frames)
                
        except Exception as e:
            logger.exception(f"Error in processing loop: {e}")
            self.error_occurred.emit(str(e))
        
        finally:
            self.is_running = False
            self.processing_finished.emit()
            logger.info("Processing loop ended")
    
    def _process_frame(self, frame: np.ndarray) -> tuple:
        """
        Process single frame with detection and tracking.
        
        Args:
            frame: Input frame
        
        Returns:
            Tuple of (processed_frame, stats_dict)
        """
        if not self.calibration.calibration:
            return frame, {}
        
        # Resize frame if configured
        if self.settings.video.process_resize_width:
            height = int(frame.shape[0] * self.settings.video.process_resize_width / frame.shape[1])
            frame = cv2.resize(frame, (self.settings.video.process_resize_width, height))
        
        # Detection and Tracking
        vehicle_types = list(self.settings.VEHICLE_DIMENSIONS.keys())
        
        # Check if using YOLO's built-in tracker (BoT-SORT or ByteTrack)
        if self.tracker.is_yolo_tracker():
            perf_logger.start("detection_tracking")
            tracker_type = self.tracker.tracker_type  # 'botsort' or 'bytetrack'
            
            # Build tracker config from settings
            tracker_config = {
                'track_high_thresh': self.settings.tracker.track_high_thresh,
                'track_low_thresh': self.settings.tracker.track_low_thresh,
                'new_track_thresh': self.settings.tracker.new_track_thresh,
                'track_buffer': self.settings.tracker.track_buffer,
                'match_thresh': self.settings.tracker.match_thresh,
                'fuse_score': self.settings.tracker.fuse_score,
            }
            
            # Add BoT-SORT specific parameters
            if tracker_type == "botsort":
                tracker_config.update({
                    'gmc_method': self.settings.tracker.gmc_method,
                    'proximity_thresh': self.settings.tracker.proximity_thresh,
                    'appearance_thresh': self.settings.tracker.appearance_thresh,
                    'with_reid': self.settings.tracker.with_reid,
                    'model': self.settings.tracker.reid_model if self.settings.tracker.with_reid else 'auto',
                })
            
            detections = self.detector.detect_with_tracking(
                frame, vehicle_types, 
                tracker_type=tracker_type, 
                persist=True,
                tracker_config=tracker_config
            )
            perf_logger.end("detection_tracking")
            
            # Filter by calibration region
            filtered_detections = []
            for det in detections:
                if self.calibration.is_bbox_in_region(det['bbox']):
                    filtered_detections.append(det)
            
            # Update tracker with pre-tracked detections
            perf_logger.start("tracking")
            tracks = self.tracker.update(filtered_detections, frame)
            perf_logger.end("tracking")
        else:
            # Use DeepSORT tracking
            perf_logger.start("detection")
            detections = self.detector.detect(frame, vehicle_types)
            perf_logger.end("detection")
            
            # Filter by calibration region
            filtered_detections = []
            for det in detections:
                if self.calibration.is_bbox_in_region(det['bbox']):
                    filtered_detections.append(det)
            
            # Tracking
            perf_logger.start("tracking")
            tracks = self.tracker.update(filtered_detections, frame)
            perf_logger.end("tracking")
        
        # Draw tracks
        for track in tracks:
            # Tracker output is always in xyxy format [x1, y1, x2, y2]
            bbox = track['bbox']
            x1, y1, x2, y2 = map(int, bbox)
                
            class_name = track['class']
            track_id = track['track_id']
            
            color = self.settings.VEHICLE_COLORS.get(class_name, (255, 255, 255))
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            
            label = f"{class_name} #{track_id}"
            cv2.putText(frame, label, (x1, y1 - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        
        # Draw detection region
        frame = self.calibration.draw_region(frame)
        
        # Calculate density
        vehicle_counts = self.tracker.get_vehicle_counts(tracks)
        road_area = self.calibration.get_road_area()
        occupied_area, density_percentage = self.density_calculator.calculate_density(
            vehicle_counts, road_area
        )
        
        # Get congestion level
        level_name, status_text, color_bgr = self.density_calculator.get_density_level(
            density_percentage
        )
        
        stats = {
            'vehicle_counts': vehicle_counts,
            'occupied_area': occupied_area,
            'density_percentage': density_percentage,
            'congestion_level': level_name,
            'congestion_status': status_text,
            'congestion_color': color_bgr,
            'frame_number': self.current_frame_number,
            'total_frames': self.total_frames
        }
        
        return frame, stats
    
    def _update_fps(self):
        """Update FPS calculation"""
        current_time = time.time()
        self._frame_times.append(current_time)
        
        # Keep only last second of frame times
        while self._frame_times and self._frame_times[0] < current_time - 1.0:
            self._frame_times.pop(0)
        
        if len(self._frame_times) > 1:
            self._current_fps = len(self._frame_times)
    
    def get_progress(self) -> float:
        """Get current progress as percentage"""
        if self.total_frames == 0:
            return 0.0
        return (self.current_frame_number / self.total_frames) * 100
    
    def cleanup(self):
        """Cleanup resources"""
        self.stop()
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        logger.info("VideoProcessingThread cleaned up")
