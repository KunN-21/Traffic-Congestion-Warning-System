"""
Calibration Manager
Handles 4-point calibration and perspective transformation
Supports both polygon and circular/ellipse modes for roundabouts
"""

import cv2
import numpy as np
import json
import os
from typing import List, Tuple, Optional
from dataclasses import dataclass, asdict, field
from enum import Enum

from ..utils.logger import get_logger

logger = get_logger(__name__)


class CalibrationMode(Enum):
    """Calibration mode types"""
    POLYGON = "polygon"      # 4-point polygon (default)
    CIRCLE = "circle"        # Circle defined by center + radius point
    ELLIPSE = "ellipse"      # Ellipse defined by center + 2 axis points


@dataclass
class LaneData:
    """Data structure for a single lane"""
    lane_id: int
    points: List[Tuple[int, int]]
    road_length_meters: float
    road_width_meters: float
    road_area_meters: float
    polygon: Optional[List[Tuple[int, int]]] = None
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict):
        return cls(**data)


@dataclass
class CalibrationData:
    """Calibration data structure"""
    points: List[Tuple[int, int]]
    road_length_meters: float  # Ls
    road_width_meters: float   # Ws
    road_area_meters: float    # DT = Ls × Ws
    homography_matrix: Optional[List[List[float]]] = None
    traffic_light_roi: Optional[List[Tuple[int, int]]] = None  # Traffic light detection region
    calibration_mode: str = "polygon"  # polygon, circle, or ellipse
    # Circle/ellipse specific data
    center: Optional[Tuple[int, int]] = None
    radius: Optional[int] = None  # For circle mode (pixel radius)
    radius_outer: Optional[float] = None  # Outer radius in meters (r1)
    radius_inner: Optional[float] = None  # Inner radius in meters (r2)
    axes: Optional[Tuple[int, int]] = None  # For ellipse mode (major, minor)
    angle: float = 0.0  # Rotation angle for ellipse
    # Multi-lane support
    num_lanes: int = 1  # Number of lanes
    lanes: Optional[List[dict]] = None  # List of LaneData for each lane
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        data = asdict(self)
        if self.homography_matrix is not None:
            data['homography_matrix'] = self.homography_matrix
        if self.traffic_light_roi is not None:
            data['traffic_light_roi'] = self.traffic_light_roi
        if self.lanes is not None:
            data['lanes'] = self.lanes
        return data
    
    @classmethod
    def from_dict(cls, data: dict):
        """Create from dictionary"""
        if 'homography_matrix' in data and data['homography_matrix']:
            data['homography_matrix'] = data['homography_matrix']
        if 'traffic_light_roi' not in data:
            data['traffic_light_roi'] = None
        if 'calibration_mode' not in data:
            data['calibration_mode'] = 'polygon'
        if 'center' not in data:
            data['center'] = None
        if 'radius' not in data:
            data['radius'] = None
        if 'radius_outer' not in data:
            data['radius_outer'] = None
        if 'radius_inner' not in data:
            data['radius_inner'] = None
        if 'axes' not in data:
            data['axes'] = None
        if 'angle' not in data:
            data['angle'] = 0.0
        if 'num_lanes' not in data:
            data['num_lanes'] = 1
        if 'lanes' not in data:
            data['lanes'] = None
        
        # Remove unexpected fields that might exist in old calibration files
        valid_fields = {'points', 'road_length_meters', 'road_width_meters', 'road_area_meters',
                       'homography_matrix', 'traffic_light_roi', 'calibration_mode',
                       'center', 'radius', 'radius_outer', 'radius_inner', 'axes', 'angle', 
                       'num_lanes', 'lanes'}
        data = {k: v for k, v in data.items() if k in valid_fields}
        
        return cls(**data)


class CalibrationManager:
    """Manages calibration process and data"""
    
    def __init__(self, profiles_dir: str = "calibration_profiles"):
        """Initialize calibration manager"""
        self.profiles_dir = profiles_dir
        self.calibration: Optional[CalibrationData] = None
        self.calibration_points: List[Tuple[int, int]] = []
        self.polygon: Optional[np.ndarray] = None
        self.mode: CalibrationMode = CalibrationMode.POLYGON
        
        # Circle/ellipse specific
        self.center: Optional[Tuple[int, int]] = None
        self.radius: Optional[int] = None
        self.axes: Optional[Tuple[int, int]] = None  # (major, minor) axes
        self.angle: float = 0.0
        
        # Multi-lane support
        self.num_lanes: int = 1
        self.current_lane: int = 0  # 0-indexed
        self.lanes_data: List[dict] = []  # Stores LaneData for each completed lane
        self.all_polygons: List[np.ndarray] = []  # Polygons for all lanes
        
        # Ensure profiles directory exists
        os.makedirs(profiles_dir, exist_ok=True)
    
    def set_mode(self, mode: CalibrationMode):
        """Set calibration mode"""
        self.mode = mode
        self.reset()
        logger.info(f"Calibration mode set to: {mode.value}")
    
    def set_num_lanes(self, num_lanes: int):
        """Set number of lanes for calibration"""
        self.num_lanes = max(1, min(num_lanes, 2))  # Limit 1-2 lanes
        self.reset()
        logger.info(f"Number of lanes set to: {self.num_lanes}")
    
    def get_num_lanes(self) -> int:
        """Get number of lanes"""
        return self.num_lanes
    
    def get_current_lane(self) -> int:
        """Get current lane being calibrated (1-indexed for display)"""
        return self.current_lane + 1
    
    def is_all_lanes_calibrated(self) -> bool:
        """Check if all lanes have been calibrated"""
        return len(self.lanes_data) >= self.num_lanes
    
    def set_mode(self, mode: CalibrationMode):
        """Set calibration mode"""
        self.mode = mode
        self.reset()
        logger.info(f"Calibration mode set to: {mode.value}")
    
    def get_mode(self) -> CalibrationMode:
        """Get current calibration mode"""
        return self.mode
    
    def get_required_points(self) -> int:
        """Get number of points required for current mode"""
        if self.mode == CalibrationMode.POLYGON:
            return 4
        elif self.mode == CalibrationMode.CIRCLE:
            return 2  # Center + edge point
        elif self.mode == CalibrationMode.ELLIPSE:
            return 3  # Center + 2 axis endpoints
        return 4
    
    def add_point(self, x: int, y: int) -> bool:
        """
        Add calibration point
        
        Args:
            x, y: Point coordinates
        
        Returns:
            True if calibration is complete (required points added)
        """
        required = self.get_required_points()
        
        if len(self.calibration_points) < required:
            self.calibration_points.append((x, y))
            logger.debug(f"Point {len(self.calibration_points)}: ({x}, {y})")
            
            # Update circle/ellipse parameters as points are added
            if self.mode == CalibrationMode.CIRCLE:
                if len(self.calibration_points) == 1:
                    self.center = (x, y)
                elif len(self.calibration_points) == 2:
                    # Calculate radius from center to edge point
                    self.radius = int(np.sqrt(
                        (x - self.center[0])**2 + (y - self.center[1])**2
                    ))
                    return True
                    
            elif self.mode == CalibrationMode.ELLIPSE:
                if len(self.calibration_points) == 1:
                    self.center = (x, y)
                elif len(self.calibration_points) == 3:
                    # Calculate ellipse from center and 2 axis points
                    self._calculate_ellipse_from_points()
                    return True
            
            elif self.mode == CalibrationMode.POLYGON:
                if len(self.calibration_points) == 4:
                    return True
        
        return False
    
    def _calculate_ellipse_from_points(self):
        """Calculate ellipse axes from center and 2 points"""
        if len(self.calibration_points) < 3:
            return
        
        center = self.calibration_points[0]
        p1 = self.calibration_points[1]
        p2 = self.calibration_points[2]
        
        self.center = center
        
        # Calculate distances from center to each point
        d1 = np.sqrt((p1[0] - center[0])**2 + (p1[1] - center[1])**2)
        d2 = np.sqrt((p2[0] - center[0])**2 + (p2[1] - center[1])**2)
        
        # Major axis is the longer one
        if d1 >= d2:
            major = int(d1)
            minor = int(d2)
            # Calculate angle from center to major axis point
            self.angle = np.degrees(np.arctan2(p1[1] - center[1], p1[0] - center[0]))
        else:
            major = int(d2)
            minor = int(d1)
            self.angle = np.degrees(np.arctan2(p2[1] - center[1], p2[0] - center[0]))
        
        self.axes = (major, minor)
    
    def finalize_calibration_with_radii(self, radius_outer: float, radius_inner: float) -> bool:
        """
        Finalize calibration with two radii for annulus (donut) shape
        
        Args:
            radius_outer: Outer radius r1 in meters
            radius_inner: Inner radius r2 in meters
        
        Returns:
            True if successful
        """
        required = self.get_required_points()
        if len(self.calibration_points) != required:
            logger.error(f"Need exactly {required} points for {self.mode.value} calibration")
            return False
        
        # Calculate area: π(r1² - r2²)
        road_area = np.pi * (radius_outer**2 - radius_inner**2)
        
        # Create polygon for detection region
        if self.mode == CalibrationMode.CIRCLE:
            self.polygon = self._create_circle_polygon()
        elif self.mode == CalibrationMode.ELLIPSE:
            self.polygon = self._create_ellipse_polygon()
        else:
            self.polygon = np.array(self.calibration_points, dtype=np.int32)
        
        # Add to lanes_data for multi-lane support
        lane_data = {
            'lane_id': self.current_lane + 1,
            'points': self.calibration_points.copy(),
            'road_length_meters': radius_outer,
            'road_width_meters': radius_inner,
            'road_area_meters': road_area,
            'polygon': self.polygon.tolist() if self.polygon is not None else None
        }
        self.lanes_data.append(lane_data)
        self.all_polygons.append(self.polygon)
        
        # Create calibration data with radii
        self.calibration = CalibrationData(
            points=self.calibration_points.copy(),
            road_length_meters=radius_outer,  # Store r1 in length field
            road_width_meters=radius_inner,   # Store r2 in width field
            road_area_meters=road_area,
            homography_matrix=None,
            calibration_mode=self.mode.value,
            center=self.center,
            radius=self.radius,
            radius_outer=radius_outer,
            radius_inner=radius_inner,
            axes=self.axes,
            angle=self.angle,
            num_lanes=self.num_lanes,
            lanes=self.lanes_data.copy()
        )
        
        logger.info(f"Calibration complete! Mode: {self.mode.value}")
        logger.info(f"  Outer radius (r1): {radius_outer:.2f} m")
        logger.info(f"  Inner radius (r2): {radius_inner:.2f} m")
        logger.info(f"  Road Area (DT): {road_area:.2f} m² = π×({radius_outer:.2f}² - {radius_inner:.2f}²)")
        
        return True
    
    def finalize_calibration_with_area(self, road_area: float) -> bool:
        """
        Finalize calibration with direct area input (for circle mode) - Legacy support
        
        Args:
            road_area: Area in square meters
        
        Returns:
            True if successful
        """
        required = self.get_required_points()
        if len(self.calibration_points) != required:
            logger.error(f"Need exactly {required} points for {self.mode.value} calibration")
            return False
        
        # Create calibration data with area directly
        self.calibration = CalibrationData(
            points=self.calibration_points.copy(),
            road_length_meters=0,  # Not used for circle
            road_width_meters=0,   # Not used for circle
            road_area_meters=road_area,
            homography_matrix=None,
            calibration_mode=self.mode.value,
            center=self.center,
            radius=self.radius,
            radius_outer=None,
            radius_inner=None,
            axes=self.axes,
            angle=self.angle
        )
        
        # Create polygon for detection region
        if self.mode == CalibrationMode.CIRCLE:
            self.polygon = self._create_circle_polygon()
        elif self.mode == CalibrationMode.ELLIPSE:
            self.polygon = self._create_ellipse_polygon()
        else:
            self.polygon = np.array(self.calibration_points, dtype=np.int32)
        
        logger.info(f"Calibration complete! Mode: {self.mode.value}")
        logger.info(f"  Road Area (DT): {road_area:.2f} m²")
        
        return True
    
    def finalize_calibration(self, road_length: float, road_width: float, 
                           use_perspective: bool = True) -> bool:
        """
        Finalize calibration with real-world dimensions
        
        Args:
            road_length: Ls in meters
            road_width: Ws in meters
            use_perspective: Calculate homography matrix (only for polygon mode)
        
        Returns:
            True if calibration is complete, False if more lanes need calibration
        """
        required = self.get_required_points()
        if len(self.calibration_points) != required:
            logger.error(f"Need exactly {required} points for {self.mode.value} calibration")
            return False
        
        # Calculate road area based on mode
        if self.mode == CalibrationMode.CIRCLE:
            # For circle, use πr² with real-world dimensions
            road_area = road_length * road_width  # User provides diameter as length/width
        elif self.mode == CalibrationMode.ELLIPSE:
            # For ellipse, use π*a*b
            road_area = road_length * road_width
        else:
            road_area = road_length * road_width
        
        # Create polygon for this lane
        if self.mode == CalibrationMode.POLYGON:
            polygon = np.array(self.calibration_points, dtype=np.int32)
        elif self.mode == CalibrationMode.CIRCLE:
            polygon = self._create_circle_polygon()
        elif self.mode == CalibrationMode.ELLIPSE:
            polygon = self._create_ellipse_polygon()
        else:
            polygon = np.array(self.calibration_points, dtype=np.int32)
        
        # Save current lane data
        lane_data = {
            'lane_id': self.current_lane + 1,
            'points': self.calibration_points.copy(),
            'road_length_meters': road_length,
            'road_width_meters': road_width,
            'road_area_meters': road_area,
            'polygon': polygon.tolist() if polygon is not None else None
        }
        self.lanes_data.append(lane_data)
        self.all_polygons.append(polygon)
        
        logger.info(f"Lane {self.current_lane + 1}/{self.num_lanes} calibrated")
        logger.info(f"  Road Length (Ls): {road_length:.2f} m")
        logger.info(f"  Road Width (Ws): {road_width:.2f} m")
        logger.info(f"  Road Area (DT): {road_area:.2f} m²")
        
        # Check if all lanes are done
        if len(self.lanes_data) >= self.num_lanes:
            # All lanes calibrated - create final calibration data
            total_area = sum(lane['road_area_meters'] for lane in self.lanes_data)
            
            # Calculate homography if requested (only for polygon, first lane)
            homography = None
            if use_perspective and self.mode == CalibrationMode.POLYGON and len(self.lanes_data) > 0:
                first_lane = self.lanes_data[0]
                homography = self._calculate_homography(
                    first_lane['road_length_meters'], 
                    first_lane['road_width_meters']
                )
            
            # Use first lane's points as primary points for backward compatibility
            first_lane = self.lanes_data[0]
            self.calibration = CalibrationData(
                points=first_lane['points'],
                road_length_meters=first_lane['road_length_meters'],
                road_width_meters=first_lane['road_width_meters'],
                road_area_meters=total_area,  # Total area of all lanes
                homography_matrix=homography.tolist() if homography is not None else None,
                calibration_mode=self.mode.value,
                center=self.center,
                radius=self.radius,
                axes=self.axes,
                angle=self.angle,
                num_lanes=self.num_lanes,
                lanes=self.lanes_data.copy()
            )
            
            # Combine all polygons - use first polygon as primary
            self.polygon = self.all_polygons[0] if len(self.all_polygons) > 0 else None
            
            logger.info(f"All {self.num_lanes} lanes calibrated! Total area: {total_area:.2f} m²")
            return True
        else:
            # Move to next lane
            self.current_lane += 1
            self.calibration_points = []
            self.center = None
            self.radius = None
            self.axes = None
            self.angle = 0.0
            logger.info(f"Ready for lane {self.current_lane + 1}/{self.num_lanes}")
            return False  # Not complete yet
    
    def _create_circle_polygon(self, num_points: int = 64) -> np.ndarray:
        """Create polygon approximation of circle"""
        if self.center is None or self.radius is None:
            return np.array([], dtype=np.int32)
        
        angles = np.linspace(0, 2 * np.pi, num_points, endpoint=False)
        points = []
        for angle in angles:
            x = int(self.center[0] + self.radius * np.cos(angle))
            y = int(self.center[1] + self.radius * np.sin(angle))
            points.append([x, y])
        
        return np.array(points, dtype=np.int32)
    
    def _create_ellipse_polygon(self, num_points: int = 64) -> np.ndarray:
        """Create polygon approximation of ellipse"""
        if self.center is None or self.axes is None:
            return np.array([], dtype=np.int32)
        
        major, minor = self.axes
        angle_rad = np.radians(self.angle)
        
        angles = np.linspace(0, 2 * np.pi, num_points, endpoint=False)
        points = []
        
        for a in angles:
            # Ellipse parametric equations
            x = major * np.cos(a)
            y = minor * np.sin(a)
            
            # Rotate by angle
            x_rot = x * np.cos(angle_rad) - y * np.sin(angle_rad)
            y_rot = x * np.sin(angle_rad) + y * np.cos(angle_rad)
            
            # Translate to center
            px = int(self.center[0] + x_rot)
            py = int(self.center[1] + y_rot)
            points.append([px, py])
        
        return np.array(points, dtype=np.int32)
    
    def _calculate_homography(self, road_length: float, road_width: float) -> np.ndarray:
        """Calculate perspective transformation matrix"""
        # Source points: the 4 calibration points in image
        src_points = np.float32(self.calibration_points)
        
        # Destination points: rectangle with real-world aspect ratio
        aspect_ratio = road_width / road_length
        
        # Use 400 pixels for length dimension
        dst_height = 400
        dst_width = int(dst_height * aspect_ratio)
        
        dst_points = np.float32([
            [0, 0],                      # Top-left
            [dst_width, 0],              # Top-right
            [dst_width, dst_height],     # Bottom-right
            [0, dst_height]              # Bottom-left
        ])
        
        # Calculate homography matrix
        homography, _ = cv2.findHomography(src_points, dst_points)
        return homography
    
    def is_point_in_region(self, x: float, y: float) -> bool:
        """Check if point is inside any calibration region (any lane)"""
        if self.polygon is None and len(self.all_polygons) == 0:
            return True
        
        # Check in primary polygon
        if self.polygon is not None:
            if cv2.pointPolygonTest(self.polygon, (float(x), float(y)), False) >= 0:
                return True
        
        # Check in all lane polygons
        for polygon in self.all_polygons:
            if polygon is not None:
                if cv2.pointPolygonTest(polygon, (float(x), float(y)), False) >= 0:
                    return True
        
        return False
    
    def get_point_lane(self, x: float, y: float) -> int:
        """
        Get which lane the point belongs to
        
        Returns:
            Lane number (1-based), or 0 if not in any lane
        """
        # Check in all lane polygons
        for lane_idx, polygon in enumerate(self.all_polygons):
            if polygon is not None:
                if cv2.pointPolygonTest(polygon, (float(x), float(y)), False) >= 0:
                    return lane_idx + 1  # 1-based lane number
        
        # Check in primary polygon (for backward compatibility with single lane)
        if self.polygon is not None:
            if cv2.pointPolygonTest(self.polygon, (float(x), float(y)), False) >= 0:
                return 1
        
        return 0
    
    def is_bbox_in_region(self, bbox: List[float]) -> bool:
        """
        Check if bounding box center is in calibration region
        
        Args:
            bbox: [x1, y1, width, height] (xywh format from detector)
        
        Returns:
            True if center is in region
        """
        if self.polygon is None:
            return True
        
        # Calculate center from xywh format
        if len(bbox) == 4:
            # xywh format - bbox[2] is width, bbox[3] is height
            center_x = bbox[0] + bbox[2] / 2
            center_y = bbox[1] + bbox[3] / 2
        else:
            return True
        
        return self.is_point_in_region(center_x, center_y)
    
    def save_profile(self, video_name: str) -> bool:
        """Save calibration profile to JSON file"""
        if self.calibration is None:
            logger.warning("No calibration data to save")
            return False
        
        filepath = os.path.join(self.profiles_dir, f"{video_name}_calibration.json")
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.calibration.to_dict(), f, indent=2)
        
        logger.info(f"Calibration profile saved: {filepath}")
        return True
    
    def load_profile(self, video_name: str) -> bool:
        """Load calibration profile from JSON file"""
        filepath = os.path.join(self.profiles_dir, f"{video_name}_calibration.json")
        
        if not os.path.exists(filepath):
            logger.debug(f"Profile not found: {filepath}")
            return False
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        self.calibration = CalibrationData.from_dict(data)
        self.calibration_points = self.calibration.points.copy()
        
        # Restore mode and shape parameters
        self.mode = CalibrationMode(self.calibration.calibration_mode)
        self.center = tuple(self.calibration.center) if self.calibration.center else None
        self.radius = self.calibration.radius
        self.axes = tuple(self.calibration.axes) if self.calibration.axes else None
        self.angle = self.calibration.angle
        
        # Restore multi-lane data
        self.num_lanes = self.calibration.num_lanes
        self.lanes_data = self.calibration.lanes if self.calibration.lanes else []
        self.current_lane = len(self.lanes_data)
        
        # Recreate polygons for all lanes
        self.all_polygons = []
        if self.lanes_data:
            for lane in self.lanes_data:
                if lane.get('polygon'):
                    polygon = np.array(lane['polygon'], dtype=np.int32)
                    self.all_polygons.append(polygon)
        
        # Recreate primary polygon based on mode
        if self.mode == CalibrationMode.POLYGON:
            self.polygon = np.array(self.calibration_points, dtype=np.int32)
        elif self.mode == CalibrationMode.CIRCLE:
            self.polygon = self._create_circle_polygon()
        elif self.mode == CalibrationMode.ELLIPSE:
            self.polygon = self._create_ellipse_polygon()
        
        logger.info(f"Calibration profile loaded: {filepath} (mode: {self.mode.value}, lanes: {self.num_lanes})")
        return True
    
    def reset(self):
        """Reset calibration data"""
        self.calibration = None
        self.calibration_points = []
        self.polygon = None
        self.center = None
        self.radius = None
        self.axes = None
        self.angle = 0.0
        # Reset multi-lane data
        self.current_lane = 0
        self.lanes_data = []
        self.all_polygons = []
        # Keep num_lanes and mode
    
    def get_road_area(self) -> float:
        """Get calibrated road area (DT)"""
        if self.calibration:
            return self.calibration.road_area_meters
        return 0.0
    
    def get_lane_area(self, lane_number: int) -> float:
        """
        Get area of a specific lane
        
        Args:
            lane_number: Lane number (1-based)
        
        Returns:
            Area in square meters, or 0 if lane doesn't exist
        """
        if self.calibration and self.calibration.lanes:
            for lane in self.calibration.lanes:
                if lane['lane_id'] == lane_number:
                    return lane['road_area_meters']
        
        # Fallback for single lane
        if lane_number == 1 and self.calibration:
            return self.calibration.road_area_meters
        
        return 0.0
    
    def get_points(self) -> List[Tuple[int, int]]:
        """Get calibration points"""
        return self.calibration_points.copy()
    
    def draw_points(self, frame: np.ndarray, radius: int = 6, 
                   color: Tuple[int, int, int] = (0, 255, 0), 
                   thickness: int = 2) -> np.ndarray:
        """Draw calibration points on frame based on current mode"""
        result = frame.copy()
        
        # Define colors for different lanes
        lane_colors = [
            (0, 255, 0),      # Green - Lane 1
            (255, 165, 0),    # Orange - Lane 2
            (255, 0, 255),    # Magenta - Lane 3
            (0, 255, 255)     # Cyan - Lane 4
        ]
        
        # Draw completed lanes
        for lane_idx, lane in enumerate(self.lanes_data):
            lane_color = lane_colors[lane_idx % len(lane_colors)]
            points = lane['points']
            
            if self.mode == CalibrationMode.POLYGON:
                # Draw points
                for i, point in enumerate(points):
                    cv2.circle(result, tuple(point), radius, lane_color, -1)
                    cv2.putText(result, f"L{lane_idx+1}P{i+1}", 
                               (point[0] + 10, point[1] - 10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, lane_color, thickness)
                
                # Draw lines between points
                if len(points) >= 2:
                    for i in range(len(points) - 1):
                        cv2.line(result, tuple(points[i]), tuple(points[i + 1]), 
                                lane_color, thickness)
                    
                    # Close polygon if 4 points
                    if len(points) == 4:
                        cv2.line(result, tuple(points[3]), tuple(points[0]), 
                                lane_color, thickness)
        
        # Draw current lane being calibrated
        current_color = lane_colors[self.current_lane % len(lane_colors)]
        
        if self.mode == CalibrationMode.POLYGON:
            # Draw points
            for i, point in enumerate(self.calibration_points):
                cv2.circle(result, point, radius, current_color, -1)
                cv2.putText(result, f"L{self.current_lane+1}P{i+1}", 
                           (point[0] + 10, point[1] - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, current_color, thickness)
            
            # Draw lines between points
            if len(self.calibration_points) >= 2:
                for i in range(len(self.calibration_points) - 1):
                    cv2.line(result, self.calibration_points[i], 
                            self.calibration_points[i + 1], current_color, thickness)
                
                # Close polygon if 4 points
                if len(self.calibration_points) == 4:
                    cv2.line(result, self.calibration_points[3], 
                            self.calibration_points[0], current_color, thickness)
        
        elif self.mode == CalibrationMode.CIRCLE:
            # Draw center point
            if len(self.calibration_points) >= 1:
                cv2.circle(result, self.calibration_points[0], radius, current_color, -1)
                cv2.putText(result, "Center", (self.calibration_points[0][0] + 10, 
                           self.calibration_points[0][1] - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, current_color, thickness)
            
            # Draw circle preview
            if len(self.calibration_points) == 2:
                cv2.circle(result, self.calibration_points[1], radius, (255, 165, 0), -1)
                cv2.putText(result, "Edge", (self.calibration_points[1][0] + 10, 
                           self.calibration_points[1][1] - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 165, 0), thickness)
                
                if self.radius:
                    cv2.circle(result, self.center, self.radius, current_color, thickness)
        
        elif self.mode == CalibrationMode.ELLIPSE:
            # Draw center point
            if len(self.calibration_points) >= 1:
                cv2.circle(result, self.calibration_points[0], radius, current_color, -1)
                cv2.putText(result, "Center", (self.calibration_points[0][0] + 10, 
                           self.calibration_points[0][1] - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, current_color, thickness)
            
            # Draw axis points
            if len(self.calibration_points) >= 2:
                cv2.circle(result, self.calibration_points[1], radius, (255, 165, 0), -1)
                cv2.putText(result, "Axis1", (self.calibration_points[1][0] + 10, 
                           self.calibration_points[1][1] - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 165, 0), thickness)
                cv2.line(result, self.calibration_points[0], self.calibration_points[1], 
                        (255, 165, 0), 1)
            
            if len(self.calibration_points) == 3:
                cv2.circle(result, self.calibration_points[2], radius, (0, 165, 255), -1)
                cv2.putText(result, "Axis2", (self.calibration_points[2][0] + 10, 
                           self.calibration_points[2][1] - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), thickness)
                cv2.line(result, self.calibration_points[0], self.calibration_points[2], 
                        (0, 165, 255), 1)
                
                # Draw ellipse preview
                if self.axes:
                    cv2.ellipse(result, self.center, self.axes, self.angle, 
                               0, 360, current_color, thickness)
        
        return result
    
    def draw_region(self, frame: np.ndarray, 
                   color: Tuple[int, int, int] = (0, 255, 255),
                   alpha: float = 0.3) -> np.ndarray:
        """Draw detection region overlay for all lanes with semi-transparent fill"""
        overlay = frame.copy()
        result = frame.copy()
        
        # Define colors for different lanes
        lane_colors = [
            (0, 255, 0),      # Green - Lane 1
            (255, 165, 0),    # Orange - Lane 2
        ]
        
        # Draw all lane polygons with filled background
        for lane_idx, polygon in enumerate(self.all_polygons):
            if polygon is not None and len(polygon) > 0:
                lane_color = lane_colors[lane_idx % len(lane_colors)]
                
                # Fill polygon with semi-transparent color
                cv2.fillPoly(overlay, [polygon], lane_color)
                
                # Draw outline
                cv2.polylines(result, [polygon], True, lane_color, 2)
                
                # Add lane label
                if len(polygon) > 0:
                    # Find center of polygon
                    M = cv2.moments(polygon)
                    if M["m00"] != 0:
                        cx = int(M["m10"] / M["m00"])
                        cy = int(M["m01"] / M["m00"])
                        cv2.putText(result, f"Lane {lane_idx+1}", (cx-30, cy),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, lane_color, 2)
        
        # Draw primary polygon if exists (for backward compatibility)
        if self.polygon is not None and len(self.polygon) > 0 and len(self.all_polygons) == 0:
            if self.mode == CalibrationMode.CIRCLE and self.center and self.radius:
                cv2.circle(overlay, self.center, self.radius, color, -1)
                cv2.circle(result, self.center, self.radius, color, 2)
            elif self.mode == CalibrationMode.ELLIPSE and self.center and self.axes:
                cv2.ellipse(overlay, self.center, self.axes, self.angle, 0, 360, color, -1)
                cv2.ellipse(result, self.center, self.axes, self.angle, 0, 360, color, 2)
            else:
                cv2.fillPoly(overlay, [self.polygon], color)
                cv2.polylines(result, [self.polygon], True, color, 2)
        
        # Blend overlay with result (semi-transparent fill)
        cv2.addWeighted(overlay, 0.2, result, 0.8, 0, result)
        
        return result
