"""
Settings and Configuration Management
Centralized configuration for the traffic monitoring system
"""

import json
import os
import logging
from dataclasses import dataclass, asdict
from typing import Dict, Tuple

# Use standard logging here to avoid circular import
logger = logging.getLogger("traffic_system.config.settings")


@dataclass
class ModelConfig:
    """YOLO Model Configuration"""
    model_path: str = "Model/best.pt"
    conf_threshold: float = 0.6
    iou_threshold: float = 0.6
    detection_conf_filter: float = 0.4
    imgsz: int = 640  # Inference resolution (can be different from training)
    half: bool = True  # Use FP16 inference
    max_det: int = 100  # Maximum detections per frame
    agnostic_nms: bool = True  # Class-agnostic NMS


@dataclass
class TrackerConfig:
    """BoT-SORT Tracker Configuration"""
    tracker_type: str = "botsort"
    # BoT-SORT parameters
    track_high_thresh: float = 0.5
    track_low_thresh: float = 0.1
    new_track_thresh: float = 0.6
    track_buffer: int = 30
    match_thresh: float = 0.8
    fuse_score: bool = True
    # BoT-SORT specific - GMC and ReID
    gmc_method: str = "sparseOptFlow"  # Options: orb, sift, ecc, sparseOptFlow, None
    proximity_thresh: float = 0.5
    appearance_thresh: float = 0.25
    with_reid: bool = False  # Enable ReID (better tracking with occlusion, slower)
    reid_model: str = "auto"  # ReID model: auto, yolo11n-cls.pt, etc.


@dataclass
class VehicleDimensions:
    """Vehicle dimensions in meters"""
    length: float
    width: float
    height: float
    
    @property
    def footprint_area(self) -> float:
        """Calculate vehicle footprint area (length × width)"""
        return self.length * self.width


@dataclass
class CalibrationConfig:
    """Calibration Configuration"""
    require_real_dimensions: bool = True
    default_road_length: float = 50.0  # Ls in meters
    default_road_width: float = 10.0   # Ws in meters
    use_perspective_transform: bool = True
    enable_save: bool = True
    profiles_dir: str = "calibration_profiles"


@dataclass
class DensityThreshold:
    """Density threshold configuration"""
    level_name: str
    max_percentage: float
    status_text: str
    color_bgr: Tuple[int, int, int]


@dataclass
class VideoConfig:
    """Video Processing Configuration"""
    frame_skip: int = 1
    fps_limit: int = None
    process_resize_width: int = None
    wait_key_ms: int = 30


@dataclass
class DisplayConfig:
    """Display Configuration"""
    info_panel_height: int = 380
    font_scale_title: float = 0.6
    font_scale_text: float = 0.5
    font_scale_value: float = 0.6
    font_scale_status: float = 0.9
    font_thickness: int = 2
    font_thickness_thin: int = 1
    show_vehicle_dimensions: bool = True
    show_area_metrics: bool = True


class Settings:
    """Main Settings Manager"""
    
    # Vietnamese Vehicle Dimensions (Standard)
    VEHICLE_DIMENSIONS = {
        'motorcycle': VehicleDimensions(length=2.05, width=0.725, height=1.102),
        'bicycle': VehicleDimensions(length=1.75, width=0.6, height=1.05),
        'bus': VehicleDimensions(length=12.1, width=2.6, height=4.1),
        'car': VehicleDimensions(length=3.7, width=2.1, height=1.3),
        'truck': VehicleDimensions(length=9.1, width=2.6, height=4.1),
    }
    
    # Vehicle Colors (BGR format for OpenCV)
    VEHICLE_COLORS = {
        'bus': (255, 0, 0),         # Blue
        'car': (0, 255, 0),         # Green
        'motorcycle': (0, 255, 255), # Yellow
        'truck': (255, 0, 255),     # Magenta
        'bicycle': (255, 255, 0)    # Cyan
    }
    
    # Density Thresholds
    DENSITY_THRESHOLDS = [
        DensityThreshold('Thấp', 30.0, 'Thấp', (0, 255, 0)),
        DensityThreshold('Trung bình', 80.0, 'Trung bình', (0, 165, 255)),  # Orange (better visibility)
        DensityThreshold('Cao', float('inf'), 'Cao', (0, 0, 255))
    ]
    
    # Calibration Display
    CALIBRATION_POINT_RADIUS = 6
    CALIBRATION_POINT_COLOR = (0, 255, 0)  # Green
    CALIBRATION_LINE_THICKNESS = 2
    CALIBRATION_TEXT_SCALE = 0.6
    
    def __init__(self, config_file: str = None):
        """Initialize settings"""
        self.config_file = config_file or "traffic_system/config/default_config.json"
        
        # Initialize configurations
        self.model = ModelConfig()
        self.tracker = TrackerConfig()
        self.calibration = CalibrationConfig()
        self.video = VideoConfig()
        self.display = DisplayConfig()
        
        # Load from file if exists
        if os.path.exists(self.config_file):
            self.load()
    
    def get_vehicle_footprint_areas(self) -> Dict[str, float]:
        """Get footprint areas for all vehicle types"""
        return {
            vtype: dims.footprint_area 
            for vtype, dims in self.VEHICLE_DIMENSIONS.items()
        }
    
    def get_density_level(self, percentage: float) -> DensityThreshold:
        """Get density level based on percentage"""
        for threshold in self.DENSITY_THRESHOLDS:
            if percentage < threshold.max_percentage:
                return threshold
        return self.DENSITY_THRESHOLDS[-1]
    
    def to_dict(self) -> dict:
        """Convert settings to dictionary"""
        return {
            'model': asdict(self.model),
            'tracker': asdict(self.tracker),
            'calibration': asdict(self.calibration),
            'video': asdict(self.video),
            'display': asdict(self.display)
        }
    
    def from_dict(self, data: dict):
        """Load settings from dictionary"""
        if 'model' in data:
            self.model = ModelConfig(**data['model'])
        if 'tracker' in data:
            self.tracker = TrackerConfig(**data['tracker'])
        if 'calibration' in data:
            self.calibration = CalibrationConfig(**data['calibration'])
        if 'video' in data:
            self.video = VideoConfig(**data['video'])
        if 'display' in data:
            self.display = DisplayConfig(**data['display'])
    
    def save(self, filepath: str = None):
        """Save settings to JSON file"""
        filepath = filepath or self.config_file
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        
        logger.info(f"Settings saved to: {filepath}")
    
    def load(self, filepath: str = None):
        """Load settings from JSON file"""
        filepath = filepath or self.config_file
        
        if not os.path.exists(filepath):
            logger.warning(f"Config file not found: {filepath}")
            return False
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        self.from_dict(data)
        logger.info(f"Settings loaded from: {filepath}")
        return True
    
    def reset_to_defaults(self):
        """Reset all settings to default values"""
        self.model = ModelConfig()
        self.tracker = TrackerConfig()
        self.calibration = CalibrationConfig()
        self.video = VideoConfig()
        self.display = DisplayConfig()
