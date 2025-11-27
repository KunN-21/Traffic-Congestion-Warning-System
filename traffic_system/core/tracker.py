"""
Vehicle Tracker using DeepSORT
Handles vehicle tracking across frames
"""

import numpy as np
from deep_sort_realtime.deepsort_tracker import DeepSort
from typing import List, Dict, Set

from ..utils.logger import get_logger

logger = get_logger(__name__)


class VehicleTracker:
    """DeepSORT-based vehicle tracker"""
    
    def __init__(self, max_age: int = 30, n_init: int = 10,
                 max_iou_distance: float = 0.7, max_cosine_distance: float = 0.25,
                 nn_budget: int = 70, embedder: str = "mobilenet", 
                 embedder_gpu: bool = True):
        """
        Initialize vehicle tracker
        
        Args:
            max_age: Maximum frames to keep object without detection
            n_init: Frames needed to confirm new object
            max_iou_distance: IOU distance threshold
            max_cosine_distance: Max cosine distance for association
            nn_budget: Maximum size of feature bank
            embedder: Feature extractor model
            embedder_gpu: Use GPU for embeddings
        """
        self.tracker = DeepSort(
            max_age=max_age,
            n_init=n_init,
            max_iou_distance=max_iou_distance,
            max_cosine_distance=max_cosine_distance,
            nn_budget=nn_budget,
            embedder=embedder,
            embedder_gpu=embedder_gpu
        )
        
        self.tracked_vehicles: Dict[int, str] = {}  # track_id -> class_name
        self.current_frame_ids: Set[int] = set()
        
        logger.info(f"DeepSORT tracker initialized")
        logger.debug(f"  max_age={max_age}, n_init={n_init}")
        logger.debug(f"  embedder={embedder}, gpu={embedder_gpu}")
    
    def update(self, detections: List[Dict], frame: np.ndarray) -> List[Dict]:
        """
        Update tracker with new detections
        
        Args:
            detections: List of detections from detector
            frame: Current frame (for feature extraction)
        
        Returns:
            List of tracks with format:
            [{'track_id': int, 'bbox': [x1,y1,x2,y2], 'class': str, 'confirmed': bool}, ...]
        """
        # Convert detections to DeepSORT format
        deepsort_detections = []
        for det in detections:
            # DeepSORT format: ([x1, y1, w, h], confidence, class_name)
            deepsort_detections.append((det['bbox'], det['conf'], det['class']))
        
        # Update tracker
        tracks = self.tracker.update_tracks(deepsort_detections, frame=frame)
        
        # Process tracks
        results = []
        self.current_frame_ids = set()
        
        for track in tracks:
            if not track.is_confirmed():
                continue
            
            track_id = track.track_id
            ltrb = track.to_ltrb()  # [left, top, right, bottom]
            class_name = track.get_det_class()
            
            # Track this vehicle
            self.current_frame_ids.add(track_id)
            if track_id not in self.tracked_vehicles:
                self.tracked_vehicles[track_id] = class_name
            
            results.append({
                'track_id': track_id,
                'bbox': [float(x) for x in ltrb],  # [x1, y1, x2, y2]
                'class': class_name,
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
        # Note: DeepSort doesn't have a reset method, would need to recreate
    
    def update_config(self, max_age: int = None, n_init: int = None,
                     max_iou_distance: float = None, max_cosine_distance: float = None):
        """Update tracker configuration (requires recreation)"""
        # DeepSORT doesn't support runtime config changes
        # Would need to recreate the tracker
        logger.warning("Tracker config update requires reinitialization")
