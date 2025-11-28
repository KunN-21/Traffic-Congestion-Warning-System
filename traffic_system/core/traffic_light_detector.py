"""
Traffic Light Detector
Detects red/green/yellow traffic lights using color analysis in a user-defined ROI
"""

import cv2
import numpy as np
from typing import Optional, Tuple, List
from dataclasses import dataclass

from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class TrafficLightState:
    """Traffic light state data"""
    is_red: bool = False
    is_yellow: bool = False
    is_green: bool = False
    confidence: float = 0.0
    dominant_color: str = "unknown"
    
    @property
    def should_skip_congestion_check(self) -> bool:
        """Return True if we should skip congestion detection (red or yellow light)"""
        return self.is_red or self.is_yellow


class TrafficLightDetector:
    """
    Detects traffic light color in a specified region of interest (ROI).
    Uses color-based detection with HSV color space.
    """
    
    def __init__(self):
        """Initialize traffic light detector"""
        self.roi_points: List[Tuple[int, int]] = []  # 4 points defining the ROI
        self.roi_polygon: Optional[np.ndarray] = None
        self.is_enabled = False
        
        # Color ranges in HSV
        # Red has two ranges (wraps around 0)
        self.red_lower1 = np.array([0, 100, 100])
        self.red_upper1 = np.array([10, 255, 255])
        self.red_lower2 = np.array([160, 100, 100])
        self.red_upper2 = np.array([180, 255, 255])
        
        # Yellow range
        self.yellow_lower = np.array([15, 100, 100])
        self.yellow_upper = np.array([35, 255, 255])
        
        # Green range
        self.green_lower = np.array([40, 100, 100])
        self.green_upper = np.array([80, 255, 255])
        
        # Detection threshold (minimum percentage of colored pixels)
        self.detection_threshold = 0.05  # 5%
        
        logger.debug("TrafficLightDetector initialized")
    
    def set_roi(self, points: List[Tuple[int, int]]) -> bool:
        """
        Set the region of interest for traffic light detection.
        
        Args:
            points: List of 4 points defining the ROI (clockwise or counter-clockwise)
        
        Returns:
            True if successful
        """
        if len(points) != 4:
            logger.error("Need exactly 4 points for traffic light ROI")
            return False
        
        self.roi_points = points.copy()
        self.roi_polygon = np.array(points, dtype=np.int32)
        self.is_enabled = True
        
        logger.info(f"Traffic light ROI set: {points}")
        return True
    
    def clear_roi(self):
        """Clear the ROI and disable detection"""
        self.roi_points = []
        self.roi_polygon = None
        self.is_enabled = False
        logger.info("Traffic light ROI cleared")
    
    def detect(self, frame: np.ndarray) -> TrafficLightState:
        """
        Detect traffic light color in the ROI.
        
        Args:
            frame: BGR image frame
        
        Returns:
            TrafficLightState with detection results
        """
        if not self.is_enabled or self.roi_polygon is None:
            return TrafficLightState()
        
        # Create mask for ROI
        mask = np.zeros(frame.shape[:2], dtype=np.uint8)
        cv2.fillPoly(mask, [self.roi_polygon], 255)
        
        # Extract ROI
        roi = cv2.bitwise_and(frame, frame, mask=mask)
        
        # Convert to HSV
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        
        # Count pixels for each color in the ROI area only
        roi_pixel_count = cv2.countNonZero(mask)
        if roi_pixel_count == 0:
            return TrafficLightState()
        
        # Detect red (combine two ranges)
        red_mask1 = cv2.inRange(hsv, self.red_lower1, self.red_upper1)
        red_mask2 = cv2.inRange(hsv, self.red_lower2, self.red_upper2)
        red_mask = cv2.bitwise_or(red_mask1, red_mask2)
        red_mask = cv2.bitwise_and(red_mask, mask)
        red_count = cv2.countNonZero(red_mask)
        
        # Detect yellow
        yellow_mask = cv2.inRange(hsv, self.yellow_lower, self.yellow_upper)
        yellow_mask = cv2.bitwise_and(yellow_mask, mask)
        yellow_count = cv2.countNonZero(yellow_mask)
        
        # Detect green
        green_mask = cv2.inRange(hsv, self.green_lower, self.green_upper)
        green_mask = cv2.bitwise_and(green_mask, mask)
        green_count = cv2.countNonZero(green_mask)
        
        # Calculate percentages
        red_pct = red_count / roi_pixel_count
        yellow_pct = yellow_count / roi_pixel_count
        green_pct = green_count / roi_pixel_count
        
        # Determine dominant color
        state = TrafficLightState()
        
        max_pct = max(red_pct, yellow_pct, green_pct)
        
        if max_pct >= self.detection_threshold:
            if red_pct == max_pct:
                state.is_red = True
                state.dominant_color = "red"
                state.confidence = red_pct
            elif yellow_pct == max_pct:
                state.is_yellow = True
                state.dominant_color = "yellow"
                state.confidence = yellow_pct
            elif green_pct == max_pct:
                state.is_green = True
                state.dominant_color = "green"
                state.confidence = green_pct
        
        return state
    
    def draw_roi(self, frame: np.ndarray, state: Optional[TrafficLightState] = None) -> np.ndarray:
        """
        Draw the traffic light ROI on the frame.
        
        Args:
            frame: BGR image frame
            state: Optional traffic light state to color the ROI accordingly
        
        Returns:
            Frame with ROI drawn
        """
        if not self.is_enabled or self.roi_polygon is None:
            return frame
        
        result = frame.copy()
        
        # Determine color based on state
        if state:
            if state.is_red:
                color = (0, 0, 255)  # Red
                label = f"DO - {state.confidence*100:.0f}%"
            elif state.is_yellow:
                color = (0, 255, 255)  # Yellow
                label = f"VANG - {state.confidence*100:.0f}%"
            elif state.is_green:
                color = (0, 255, 0)  # Green
                label = f"XANH - {state.confidence*100:.0f}%"
            else:
                color = (128, 128, 128)  # Gray
                label = "KHONG XAC DINH"
        else:
            color = (255, 0, 255)  # Magenta for unchecked
            label = "DEN GIAO THONG"
        
        # Draw polygon
        cv2.polylines(result, [self.roi_polygon], True, color, 2)
        
        # Draw label
        if len(self.roi_points) > 0:
            # Get top-left point for label
            min_x = min(p[0] for p in self.roi_points)
            min_y = min(p[1] for p in self.roi_points)
            
            # Draw background for text
            (text_w, text_h), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            cv2.rectangle(result, (min_x, min_y - text_h - 10), (min_x + text_w + 10, min_y), color, -1)
            cv2.putText(result, label, (min_x + 5, min_y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        return result
    
    def add_point(self, x: int, y: int) -> bool:
        """
        Add a point for ROI definition.
        
        Args:
            x, y: Point coordinates
        
        Returns:
            True if ROI is complete (4 points added)
        """
        if len(self.roi_points) < 4:
            self.roi_points.append((x, y))
            logger.debug(f"Traffic light ROI point {len(self.roi_points)}: ({x}, {y})")
            
            if len(self.roi_points) == 4:
                self.roi_polygon = np.array(self.roi_points, dtype=np.int32)
                self.is_enabled = True
                return True
        return False
    
    def draw_points(self, frame: np.ndarray) -> np.ndarray:
        """Draw ROI points during calibration"""
        result = frame.copy()
        
        color = (255, 0, 255)  # Magenta
        
        # Draw points
        for i, point in enumerate(self.roi_points):
            cv2.circle(result, point, 6, color, -1)
            cv2.putText(result, f"T{i+1}", (point[0] + 10, point[1] - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        
        # Draw lines between points
        if len(self.roi_points) >= 2:
            for i in range(len(self.roi_points) - 1):
                cv2.line(result, self.roi_points[i], self.roi_points[i + 1], color, 2)
            
            # Close polygon if 4 points
            if len(self.roi_points) == 4:
                cv2.line(result, self.roi_points[3], self.roi_points[0], color, 2)
        
        return result
    
    def get_points(self) -> List[Tuple[int, int]]:
        """Get current ROI points"""
        return self.roi_points.copy()
    
    def reset(self):
        """Reset ROI points (but keep enabled state)"""
        self.roi_points = []
        self.roi_polygon = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for saving"""
        return {
            'roi_points': self.roi_points,
            'is_enabled': self.is_enabled
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'TrafficLightDetector':
        """Create from dictionary"""
        detector = cls()
        if data.get('roi_points'):
            detector.set_roi([tuple(p) for p in data['roi_points']])
        return detector
