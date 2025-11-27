"""
Vehicle Detector using YOLO
Handles vehicle detection from video frames with batch processing support
"""

import cv2
import numpy as np
from ultralytics import YOLO
from typing import List, Dict, Optional

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
        original_shape = frame.shape[:2]
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
