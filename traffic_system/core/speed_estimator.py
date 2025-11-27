"""
Speed Estimation Module
Estimates vehicle speed using calibration data and tracking
"""

import numpy as np
from typing import Dict, List
from dataclasses import dataclass, field
from collections import deque
import time

from ..utils.logger import get_logger
from ..core.calibration import CalibrationManager

logger = get_logger(__name__)


@dataclass
class TrackHistory:
    """History of a tracked vehicle for speed calculation"""
    track_id: int
    class_name: str
    positions: deque = field(default_factory=lambda: deque(maxlen=30))  # (x, y, timestamp)
    speeds: deque = field(default_factory=lambda: deque(maxlen=10))  # Recent speeds
    last_speed: float = 0.0
    average_speed: float = 0.0
    
    def add_position(self, x: float, y: float, timestamp: float):
        """Add a new position to history"""
        self.positions.append((x, y, timestamp))
    
    def calculate_speed(self, pixels_per_meter: float) -> float:
        """
        Calculate speed in km/h based on recent positions.
        
        Args:
            pixels_per_meter: Calibration factor
        
        Returns:
            Speed in km/h
        """
        if len(self.positions) < 2:
            return 0.0
        
        # Get last two positions
        x1, y1, t1 = self.positions[-2]
        x2, y2, t2 = self.positions[-1]
        
        # Calculate distance in pixels
        distance_pixels = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
        
        # Convert to meters
        distance_meters = distance_pixels / pixels_per_meter if pixels_per_meter > 0 else 0
        
        # Calculate time difference
        time_diff = t2 - t1
        
        if time_diff <= 0:
            return self.last_speed
        
        # Calculate speed in m/s then convert to km/h
        speed_ms = distance_meters / time_diff
        speed_kmh = speed_ms * 3.6
        
        # Apply smoothing - ignore unrealistic speeds
        if speed_kmh > 200:  # Max reasonable speed for traffic
            speed_kmh = self.last_speed
        
        # Store speed
        self.speeds.append(speed_kmh)
        self.last_speed = speed_kmh
        
        # Calculate average speed
        if len(self.speeds) > 0:
            self.average_speed = sum(self.speeds) / len(self.speeds)
        
        return speed_kmh


class SpeedEstimator:
    """
    Estimates vehicle speeds using tracking data and calibration.
    
    The speed estimation works by:
    1. Tracking vehicle positions over time
    2. Using calibration data to convert pixel distances to real-world distances
    3. Calculating speed = distance / time
    4. Applying smoothing for stable readings
    
    Usage:
        estimator = SpeedEstimator(calibration_manager)
        estimator.update(tracks, timestamp)
        speeds = estimator.get_speeds()
    """
    
    def __init__(self, calibration: CalibrationManager):
        """
        Initialize speed estimator.
        
        Args:
            calibration: CalibrationManager with perspective calibration data
        """
        self.calibration = calibration
        self.track_histories: Dict[int, TrackHistory] = {}
        self.pixels_per_meter = 1.0  # Will be calculated from calibration
        self._update_calibration()
        
        logger.info("SpeedEstimator initialized")
    
    def _update_calibration(self):
        """Update pixels per meter ratio from calibration data"""
        if self.calibration.calibration is None:
            self.pixels_per_meter = 1.0
            return
        
        # Calculate pixels per meter from calibration points
        # Assuming points are ordered: top-left, top-right, bottom-right, bottom-left
        points = self.calibration.calibration.points
        
        if len(points) != 4:
            return
        
        # Calculate average width and height in pixels
        top_width = np.sqrt((points[1][0] - points[0][0]) ** 2 + 
                           (points[1][1] - points[0][1]) ** 2)
        bottom_width = np.sqrt((points[2][0] - points[3][0]) ** 2 + 
                               (points[2][1] - points[3][1]) ** 2)
        avg_width_pixels = (top_width + bottom_width) / 2
        
        left_height = np.sqrt((points[3][0] - points[0][0]) ** 2 + 
                              (points[3][1] - points[0][1]) ** 2)
        right_height = np.sqrt((points[2][0] - points[1][0]) ** 2 + 
                               (points[2][1] - points[1][1]) ** 2)
        avg_height_pixels = (left_height + right_height) / 2
        
        # Get real dimensions
        road_width = self.calibration.calibration.road_width_meters
        road_length = self.calibration.calibration.road_length_meters
        
        # Calculate pixels per meter (average of width and height)
        ppm_width = avg_width_pixels / road_width if road_width > 0 else 1
        ppm_height = avg_height_pixels / road_length if road_length > 0 else 1
        
        self.pixels_per_meter = (ppm_width + ppm_height) / 2
        
        logger.info(f"Pixels per meter: {self.pixels_per_meter:.2f}")
    
    def update(self, tracks: List[Dict], timestamp: float = None) -> Dict[int, float]:
        """
        Update speed estimates with new tracking data.
        
        Args:
            tracks: List of track dictionaries from tracker
            timestamp: Current timestamp (uses time.time() if not provided)
        
        Returns:
            Dictionary mapping track_id to speed in km/h
        """
        if timestamp is None:
            timestamp = time.time()
        
        current_track_ids = set()
        speeds = {}
        
        for track in tracks:
            track_id = track['track_id']
            bbox = track['bbox']
            class_name = track.get('class', 'unknown')
            
            current_track_ids.add(track_id)
            
            # Calculate center of bounding box
            center_x = (bbox[0] + bbox[2]) / 2
            center_y = (bbox[1] + bbox[3]) / 2
            
            # Get or create track history
            if track_id not in self.track_histories:
                self.track_histories[track_id] = TrackHistory(
                    track_id=track_id,
                    class_name=class_name
                )
            
            history = self.track_histories[track_id]
            history.add_position(center_x, center_y, timestamp)
            
            # Calculate speed
            speed = history.calculate_speed(self.pixels_per_meter)
            speeds[track_id] = speed
        
        # Clean up old tracks
        tracks_to_remove = []
        for track_id in self.track_histories:
            if track_id not in current_track_ids:
                tracks_to_remove.append(track_id)
        
        for track_id in tracks_to_remove:
            del self.track_histories[track_id]
        
        return speeds
    
    def get_speed(self, track_id: int) -> float:
        """
        Get current speed for a specific track.
        
        Args:
            track_id: Track ID
        
        Returns:
            Speed in km/h, or 0 if track not found
        """
        if track_id in self.track_histories:
            return self.track_histories[track_id].last_speed
        return 0.0
    
    def get_average_speed(self, track_id: int) -> float:
        """
        Get average speed for a specific track.
        
        Args:
            track_id: Track ID
        
        Returns:
            Average speed in km/h
        """
        if track_id in self.track_histories:
            return self.track_histories[track_id].average_speed
        return 0.0
    
    def get_all_speeds(self) -> Dict[int, Dict]:
        """
        Get speed information for all tracked vehicles.
        
        Returns:
            Dictionary with track_id as key and speed info as value
        """
        result = {}
        for track_id, history in self.track_histories.items():
            result[track_id] = {
                'class': history.class_name,
                'current_speed': history.last_speed,
                'average_speed': history.average_speed,
                'track_id': track_id
            }
        return result
    
    def get_traffic_flow_stats(self) -> Dict:
        """
        Get overall traffic flow statistics.
        
        Returns:
            Dictionary with traffic flow metrics
        """
        if not self.track_histories:
            return {
                'average_speed': 0.0,
                'max_speed': 0.0,
                'min_speed': 0.0,
                'vehicle_count': 0,
                'flow_status': 'Không có xe'
            }
        
        speeds = [h.last_speed for h in self.track_histories.values() if h.last_speed > 0]
        
        if not speeds:
            return {
                'average_speed': 0.0,
                'max_speed': 0.0,
                'min_speed': 0.0,
                'vehicle_count': len(self.track_histories),
                'flow_status': 'Xe đứng yên'
            }
        
        avg_speed = sum(speeds) / len(speeds)
        max_speed = max(speeds)
        min_speed = min(speeds)
        
        # Determine flow status
        if avg_speed < 10:
            flow_status = 'Kẹt xe'
        elif avg_speed < 30:
            flow_status = 'Di chuyển chậm'
        elif avg_speed < 50:
            flow_status = 'Bình thường'
        else:
            flow_status = 'Thông thoáng'
        
        return {
            'average_speed': avg_speed,
            'max_speed': max_speed,
            'min_speed': min_speed,
            'vehicle_count': len(self.track_histories),
            'flow_status': flow_status
        }
    
    def reset(self):
        """Reset all tracking histories"""
        self.track_histories.clear()
        logger.info("SpeedEstimator reset")
