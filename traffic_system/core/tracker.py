"""
Vehicle Tracker using BoT-SORT
Handles vehicle tracking across frames using YOLO's built-in BoT-SORT tracker
"""

import numpy as np
from typing import List, Dict, Set

from ..utils.logger import get_logger

logger = get_logger(__name__)


class VehicleTracker:
    """Vehicle tracker using BoT-SORT (YOLO built-in)"""
    
    def __init__(self, tracker_type: str = "botsort", 
                 track_buffer: int = 30, match_thresh: float = 0.8,
                 **kwargs):
        """
        Initialize vehicle tracker
        
        Args:
            tracker_type: Type of tracker (always 'botsort')
            track_buffer: Buffer size for tracker
            match_thresh: Match threshold for tracking
            **kwargs: Additional arguments (ignored for compatibility)
        """
        self.tracker_type = "botsort"  # Always use BoT-SORT
        self.tracked_vehicles: Dict[int, str] = {}  # track_id -> class_name
        self.current_frame_ids: Set[int] = set()
        
        # Store config for YOLO tracker
        self.yolo_tracker_config = {
            'tracker_type': 'botsort',
            'track_buffer': track_buffer,
            'match_thresh': match_thresh
        }
        logger.info(f"BoT-SORT tracker configured (YOLO built-in)")
        logger.debug(f"  track_buffer={track_buffer}, match_thresh={match_thresh}")
    
    def is_yolo_tracker(self) -> bool:
        """Check if using YOLO's built-in tracker"""
        return True  # Always using YOLO tracker

    def update(self, detections: List[Dict], frame: np.ndarray) -> List[Dict]:
        """
        Update tracker with new detections
        
        Args:
            detections: List of detections from detector (already tracked by YOLO)
            frame: Current frame (not used, kept for compatibility)
        
        Returns:
            List of tracks with format:
            [{'track_id': int, 'bbox': [x1,y1,x2,y2], 'class': str, 'confirmed': bool}, ...]
        """
        results = []
        self.current_frame_ids = set()
        
        for det in detections:
            track_id = det.get('track_id', -1)
            if track_id >= 0:
                self.current_frame_ids.add(track_id)
                if track_id not in self.tracked_vehicles:
                    self.tracked_vehicles[track_id] = det['class']
                
                # Convert bbox from xywh to xyxy format for consistency
                bbox = det['bbox']
                x1, y1, w, h = bbox[0], bbox[1], bbox[2], bbox[3]
                bbox_xyxy = [x1, y1, x1 + w, y1 + h]
                
                results.append({
                    'track_id': track_id,
                    'bbox': bbox_xyxy,  # Now in xyxy format
                    'class': det['class'],
                    'confirmed': True
                })
        return results
    
    def get_vehicle_counts(self, tracks: List[Dict]) -> Dict[str, int]:
        """
        Count vehicles by type in current frame
        
        Args:
            tracks: List of tracks from update()
        
        Returns:
            Dictionary with vehicle counts by type (all vehicle types included)
        """
        # Initialize all vehicle types to 0
        counts = {
            'motorcycle': 0,
            'bicycle': 0,
            'car': 0,
            'bus': 0,
            'truck': 0
        }
        
        # Count actual detections
        for track in tracks:
            class_name = track['class']
            if class_name in counts:
                counts[class_name] += 1
        
        return counts
    
    def get_total_unique_vehicles(self) -> int:
        """Get total number of unique vehicles tracked"""
        return len(self.tracked_vehicles)
    
    def reset(self):
        """Reset tracker state"""
        self.tracked_vehicles.clear()
        self.current_frame_ids.clear()
    
    def update_config(self, track_buffer: int = None, match_thresh: float = None):
        """Update tracker configuration"""
        if track_buffer is not None:
            self.yolo_tracker_config['track_buffer'] = track_buffer
        if match_thresh is not None:
            self.yolo_tracker_config['match_thresh'] = match_thresh
        logger.info("Tracker config updated (will apply on next video)")

