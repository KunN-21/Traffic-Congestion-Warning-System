"""
Vehicle Detector using YOLO
Handles vehicle detection from video frames with batch processing support
"""

import cv2
import numpy as np
import os
import tempfile
from ultralytics import YOLO
from typing import List, Dict

from ..utils.logger import get_logger, PerformanceLogger

logger = get_logger(__name__)
perf_logger = PerformanceLogger("detector")


class VehicleDetector:
    """
    YOLO-based vehicle detector with batch processing support.
    
    Features:
    - Single frame detection
    - Batch detection for multiple frames
    - Automatic frame resizing
    - Performance logging
    
    Attributes:
        model: YOLO model instance
        conf_threshold: Minimum confidence for detection
        iou_threshold: IOU threshold for NMS
        conf_filter: Additional filtering threshold
        imgsz: Inference image size
    """
    
    def __init__(self, model_path: str, conf_threshold: float = 0.6, 
                 iou_threshold: float = 0.6, conf_filter: float = 0.4,
                 imgsz: int = 640):
        """
        Initialize vehicle detector.
        
        Args:
            model_path: Path to YOLO model file (.pt)
            conf_threshold: Confidence threshold for detection (0-1)
            iou_threshold: IOU threshold for NMS (0-1)
            conf_filter: Additional confidence filter (0-1)
            imgsz: Inference image size (pixels). Frame will be resized to this size.
        
        Raises:
            FileNotFoundError: If model file doesn't exist
            RuntimeError: If model loading fails
        """
        self.model = YOLO(model_path)
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.conf_filter = conf_filter
        self.imgsz = imgsz
        
        logger.info(f"Model loaded: {model_path}")
        logger.info(f"Model classes: {self.model.names}")
        logger.info(f"Inference resolution: {imgsz}x{imgsz}")
    
    def detect(self, frame: np.ndarray, vehicle_types: List[str] = None,
               resize_frame: bool = False) -> List[Dict]:
        """
        Detect vehicles in a single frame.
        
        Args:
            frame: Input frame (BGR format, numpy array)
            vehicle_types: List of vehicle types to detect. 
                          None means detect all types.
            resize_frame: If True, resize frame to imgsz before detection.
                         This can improve performance but may affect detection
                         of small objects.
        
        Returns:
            List of detection dictionaries with format:
            [{'bbox': [x1, y1, w, h], 'conf': float, 'class': str}, ...]
            
            bbox is in [left, top, width, height] format for DeepSORT compatibility.
        
        Example:
            >>> detector = VehicleDetector("model.pt")
            >>> detections = detector.detect(frame, ['car', 'motorcycle'])
            >>> for det in detections:
            ...     print(f"{det['class']}: {det['conf']:.2f}")
        """
        perf_logger.start("detection")
        
        # Resize frame if requested
        scale_x, scale_y = 1.0, 1.0
        
        if resize_frame and self.imgsz:
            # Calculate scale to maintain aspect ratio
            h, w = frame.shape[:2]
            scale = self.imgsz / max(h, w)
            if scale != 1.0:
                new_w = int(w * scale)
                new_h = int(h * scale)
                frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
                scale_x = w / new_w
                scale_y = h / new_h
        
        # Run YOLO detection with optimized NMS settings
        results = self.model(frame, conf=self.conf_threshold, 
                           iou=self.iou_threshold, agnostic_nms=True,
                           max_det=300, verbose=False, imgsz=self.imgsz)[0]
        
        detections = []
        for box in results.boxes:
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
            conf = float(box.conf[0].cpu().numpy())
            cls = int(box.cls[0].cpu().numpy())
            
            # Get class name
            class_name = results.names[cls]
            
            # Filter by vehicle types if specified
            if vehicle_types and class_name not in vehicle_types:
                continue
            
            # Apply additional confidence filter
            if conf < self.conf_filter:
                continue
            
            # Scale coordinates back to original frame size
            if resize_frame:
                x1 *= scale_x
                x2 *= scale_x
                y1 *= scale_y
                y2 *= scale_y
            
            # Convert to DeepSORT format: [x1, y1, width, height]
            bbox = [float(x1), float(y1), float(x2 - x1), float(y2 - y1)]
            
            detections.append({
                'bbox': bbox,
                'conf': conf,
                'class': class_name
            })
        
        perf_logger.end("detection")
        
        return detections
    
    def detect_batch(self, frames: List[np.ndarray], 
                     vehicle_types: List[str] = None) -> List[List[Dict]]:
        """
        Detect vehicles in multiple frames (batch processing).
        
        Batch processing can be more efficient than processing frames
        one by one, especially when using GPU.
        
        Args:
            frames: List of input frames (BGR format)
            vehicle_types: List of vehicle types to detect
        
        Returns:
            List of detection lists, one per input frame.
            Each detection list has the same format as detect().
        
        Example:
            >>> frames = [frame1, frame2, frame3]
            >>> results = detector.detect_batch(frames)
            >>> for i, detections in enumerate(results):
            ...     print(f"Frame {i}: {len(detections)} vehicles")
        """
        if not frames:
            return []
        
        perf_logger.start("batch_detection")
        
        # Run batch inference
        results_list = self.model(frames, conf=self.conf_threshold,
                                  iou=self.iou_threshold, agnostic_nms=True,
                                  max_det=300, verbose=False, imgsz=self.imgsz)
        
        all_detections = []
        
        for results in results_list:
            detections = []
            for box in results.boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                conf = float(box.conf[0].cpu().numpy())
                cls = int(box.cls[0].cpu().numpy())
                
                class_name = results.names[cls]
                
                if vehicle_types and class_name not in vehicle_types:
                    continue
                
                if conf < self.conf_filter:
                    continue
                
                bbox = [float(x1), float(y1), float(x2 - x1), float(y2 - y1)]
                
                detections.append({
                    'bbox': bbox,
                    'conf': conf,
                    'class': class_name
                })
            
            all_detections.append(detections)
        
        perf_logger.end("batch_detection")
        logger.debug(f"Batch detection: {len(frames)} frames processed")
        
        return all_detections
    
    def update_config(self, conf_threshold: float = None, 
                     iou_threshold: float = None, conf_filter: float = None,
                     imgsz: int = None):
        """
        Update detector configuration.
        
        Args:
            conf_threshold: New confidence threshold
            iou_threshold: New IOU threshold
            conf_filter: New confidence filter
            imgsz: New inference image size
        """
        if conf_threshold is not None:
            self.conf_threshold = conf_threshold
            logger.debug(f"Confidence threshold updated to: {conf_threshold}")
        if iou_threshold is not None:
            self.iou_threshold = iou_threshold
            logger.debug(f"IOU threshold updated to: {iou_threshold}")
        if conf_filter is not None:
            self.conf_filter = conf_filter
            logger.debug(f"Confidence filter updated to: {conf_filter}")
        if imgsz is not None:
            self.imgsz = imgsz
            logger.info(f"Inference resolution updated to: {imgsz}x{imgsz}")
    
    def detect_with_tracking(self, frame: np.ndarray, vehicle_types: List[str] = None,
                               tracker_type: str = "botsort", persist: bool = True,
                               tracker_config: Dict = None) -> List[Dict]:
        """
        Detect and track vehicles using YOLO's built-in tracker (BoT-SORT or ByteTrack).
        
        Args:
            frame: Input frame (BGR format, numpy array)
            vehicle_types: List of vehicle types to detect.
                          None means detect all types.
            tracker_type: Type of YOLO tracker ('botsort' or 'bytetrack')
            persist: Whether to persist tracks between frames
            tracker_config: Custom tracker configuration dictionary with parameters:
                - track_high_thresh: Threshold for first association (0.0-1.0)
                - track_low_thresh: Threshold for second association (0.0-1.0)
                - new_track_thresh: Threshold to init new track (0.0-1.0)
                - track_buffer: Frames to keep lost tracks (>=0)
                - match_thresh: Track matching threshold (0.0-1.0)
                - gmc_method: GMC method (orb, sift, ecc, sparseOptFlow, None) - BoT-SORT only
                - proximity_thresh: Min IoU for ReID (0.0-1.0) - BoT-SORT only
                - appearance_thresh: Min appearance similarity (0.0-1.0) - BoT-SORT only
                - with_reid: Enable ReID (True/False) - BoT-SORT only
        
        Returns:
            List of detection dictionaries with format:
            [{'bbox': [x1, y1, w, h], 'conf': float, 'class': str, 'track_id': int}, ...]
        """
        perf_logger.start("detection_tracking")
        
        # Create custom tracker config file if parameters provided
        if tracker_config:
            tracker_yaml = self._create_tracker_config(tracker_type, tracker_config)
        else:
            # Use default YOLO tracker config
            tracker_yaml = f"{tracker_type}.yaml"
        
        try:
            # Run YOLO tracking
            results = self.model.track(
                frame, 
                conf=self.conf_threshold,
                iou=self.iou_threshold,
                tracker=tracker_yaml,
                persist=persist,
                verbose=False,
                imgsz=self.imgsz
            )[0]
        finally:
            # Clean up temp file if created
            if tracker_config and os.path.exists(tracker_yaml):
                try:
                    os.remove(tracker_yaml)
                except Exception:
                    pass
        
        detections = []
        
        # Check if tracking results are available
        if results.boxes is None or len(results.boxes) == 0:
            perf_logger.end("detection_tracking")
            return detections
        
        for i, box in enumerate(results.boxes):
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
            conf = float(box.conf[0].cpu().numpy())
            cls = int(box.cls[0].cpu().numpy())
            
            # Get track_id if available
            track_id = -1
            if box.id is not None:
                track_id = int(box.id[0].cpu().numpy())
            
            # Get class name
            class_name = results.names[cls]
            
            # Filter by vehicle types if specified
            if vehicle_types and class_name not in vehicle_types:
                continue
            
            # Apply additional confidence filter
            if conf < self.conf_filter:
                continue
            
            # Convert to DeepSORT format: [x1, y1, width, height]
            bbox = [float(x1), float(y1), float(x2 - x1), float(y2 - y1)]
            
            detections.append({
                'bbox': bbox,
                'conf': conf,
                'class': class_name,
                'track_id': track_id
            })
        
        perf_logger.end("detection_tracking")
        
        return detections
    
    def _create_tracker_config(self, tracker_type: str, config: Dict) -> str:
        """
        Create a temporary YAML config file for YOLO tracker.
        
        Args:
            tracker_type: 'botsort' or 'bytetrack'
            config: Dictionary with tracker parameters
        
        Returns:
            Path to temporary YAML config file
        """
        # Base config
        yaml_content = f"tracker_type: {tracker_type}\n\n"
        
        # Common parameters for both trackers with defaults
        common_defaults = {
            'track_high_thresh': 0.5,
            'track_low_thresh': 0.1,
            'new_track_thresh': 0.6,
            'track_buffer': 30,
            'match_thresh': 0.8,
            'fuse_score': True
        }
        
        for param, default_value in common_defaults.items():
            value = config.get(param, default_value)
            if isinstance(value, bool):
                yaml_content += f"{param}: {str(value).lower()}\n"
            else:
                yaml_content += f"{param}: {value}\n"
        
        # BoT-SORT specific parameters with defaults
        if tracker_type == "botsort":
            botsort_defaults = {
                'gmc_method': 'sparseOptFlow',
                'proximity_thresh': 0.5,
                'appearance_thresh': 0.25,
                'with_reid': False,
                'model': 'auto'
            }
            for param, default_value in botsort_defaults.items():
                value = config.get(param, default_value)
                if isinstance(value, bool):
                    yaml_content += f"{param}: {str(value).lower()}\n"
                else:
                    yaml_content += f"{param}: {value}\n"
        
        # Write to temp file
        fd, temp_path = tempfile.mkstemp(suffix='.yaml', prefix=f'{tracker_type}_custom_')
        try:
            with os.fdopen(fd, 'w') as f:
                f.write(yaml_content)
        except Exception:
            os.close(fd)
            raise
        
        logger.debug(f"Created custom tracker config: {temp_path}")
        return temp_path

    def get_model_info(self) -> Dict:
        """
        Get model information.
        
        Returns:
            Dictionary containing model information:
            - classes: List of class names
            - num_classes: Number of classes
            - imgsz: Current inference size
        """
        return {
            'classes': list(self.model.names.values()),
            'num_classes': len(self.model.names),
            'imgsz': self.imgsz,
            'conf_threshold': self.conf_threshold,
            'iou_threshold': self.iou_threshold
        }
