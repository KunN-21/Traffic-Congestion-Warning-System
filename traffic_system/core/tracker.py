"""
Vehicle Tracker supporting multiple tracking algorithms
Handles vehicle tracking across frames
"""

import numpy as np
from deep_sort_realtime.deepsort_tracker import DeepSort
from typing import List, Dict, Set, Optional

from ..utils.logger import get_logger

logger = get_logger(__name__)


class VehicleTracker:
    """Multi-algorithm vehicle tracker supporting DeepSORT, BoT-SORT, ByteTrack"""
    
    def __init__(self, tracker_type: str = "deepsort", max_age: int = 30, n_init: int = 10,
                 max_iou_distance: float = 0.7, max_cosine_distance: float = 0.25,
                 nn_budget: int = 70, embedder: str = "mobilenet", 
                 embedder_gpu: bool = True,
                 track_buffer: int = 30, match_thresh: float = 0.8):
        """
        Initialize vehicle tracker
        
        Args:
            tracker_type: Type of tracker ('deepsort', 'deepsort_osnet', 'deepsort_mobilenet', 'botsort', 'bytetrack')
            max_age: Maximum frames to keep object without detection
            n_init: Frames needed to confirm new object
            max_iou_distance: IOU distance threshold
            max_cosine_distance: Max cosine distance for association
            nn_budget: Maximum size of feature bank
            embedder: Feature extractor model
            embedder_gpu: Use GPU for embeddings
            track_buffer: Buffer size for YOLO trackers
            match_thresh: Match threshold for YOLO trackers
        """
        self.tracker_type = tracker_type
        self.tracked_vehicles: Dict[int, str] = {}  # track_id -> class_name
        self.current_frame_ids: Set[int] = set()
        self.tracker = None
        self.yolo_model = None
        
        # Initialize based on tracker type
        if tracker_type in ["deepsort", "deepsort_mobilenet"]:
            self.tracker = DeepSort(
                max_age=max_age,
                n_init=n_init,
                max_iou_distance=max_iou_distance,
                max_cosine_distance=max_cosine_distance,
                nn_budget=nn_budget,
                embedder="mobilenet",
                embedder_gpu=embedder_gpu
            )
            logger.info(f"DeepSORT tracker initialized (embedder: mobilenet)")
            
        elif tracker_type in ["botsort", "bytetrack"]:
            # For YOLO built-in trackers, we'll use them during detection
            # Store config for later use
            self.yolo_tracker_config = {
                'tracker_type': tracker_type,
                'track_buffer': track_buffer,
                'match_thresh': match_thresh
            }
            logger.info(f"{tracker_type.upper()} tracker configured (will use YOLO's built-in tracker)")
        else:
            # Default to DeepSORT
            self.tracker = DeepSort(
                max_age=max_age,
                n_init=n_init,
                max_iou_distance=max_iou_distance,
                max_cosine_distance=max_cosine_distance,
                nn_budget=nn_budget,
                embedder=embedder,
                embedder_gpu=embedder_gpu
            )
            logger.warning(f"Unknown tracker type '{tracker_type}', defaulting to DeepSORT")
        
        logger.debug(f"  max_age={max_age}, n_init={n_init}")
        logger.debug(f"  embedder_gpu={embedder_gpu}")
    
    def is_yolo_tracker(self) -> bool:
        """Check if using YOLO's built-in tracker"""
        return self.tracker_type in ["botsort", "bytetrack"]

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
        # If using YOLO tracker, detections should already have track_id
        if self.is_yolo_tracker():
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
        
        # DeepSORT tracking
        if self.tracker is None:
            logger.error("Tracker not initialized!")
            return []
        
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
