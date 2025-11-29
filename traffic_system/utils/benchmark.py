"""
Benchmark and Evaluation Tools
For evaluating model performance and system metrics
"""

import cv2
import time
import numpy as np
import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime

from ..utils.logger import get_logger
from ..config.settings import Settings

logger = get_logger(__name__)


@dataclass
class BenchmarkResult:
    """Container for benchmark results"""
    # Timing metrics
    total_frames: int = 0
    total_time: float = 0.0
    avg_fps: float = 0.0
    min_fps: float = float('inf')
    max_fps: float = 0.0
    
    # Detection metrics
    avg_detection_time: float = 0.0
    avg_tracking_time: float = 0.0
    avg_density_calc_time: float = 0.0
    
    # Detection counts
    total_detections: int = 0
    avg_detections_per_frame: float = 0.0
    detections_by_class: Dict[str, int] = field(default_factory=dict)
    
    # Tracking metrics
    unique_tracks: int = 0
    avg_track_length: float = 0.0
    
    # System info
    timestamp: str = ""
    video_path: str = ""
    model_path: str = ""
    resolution: Tuple[int, int] = (0, 0)
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return asdict(self)


class Benchmarker:
    """
    Benchmark tool for evaluating system performance.
    
    Features:
    - FPS measurement
    - Detection timing
    - Tracking timing
    - Memory usage (optional)
    - Export results to JSON
    
    Usage:
        benchmarker = Benchmarker(settings)
        results = benchmarker.run_benchmark("video.mp4")
        benchmarker.save_results("benchmark_results.json")
    """
    
    def __init__(self, settings: Settings):
        """
        Initialize benchmarker.
        
        Args:
            settings: Application settings
        """
        self.settings = settings
        self.results: Optional[BenchmarkResult] = None
        
        logger.info("Benchmarker initialized")
    
    def run_benchmark(self, video_path: str, 
                      max_frames: int = None,
                      warmup_frames: int = 30) -> BenchmarkResult:
        """
        Run benchmark on a video file.
        
        Args:
            video_path: Path to video file
            max_frames: Maximum frames to process (None = all)
            warmup_frames: Frames to skip for warmup
        
        Returns:
            BenchmarkResult with all metrics
        """
        # Lazy import to avoid circular dependency
        from ..core.detector import VehicleDetector
        from ..core.tracker import VehicleTracker
        
        logger.info(f"Starting benchmark on: {video_path}")
        
        # Initialize components
        detector = VehicleDetector(
            model_path=self.settings.model.model_path,
            conf_threshold=self.settings.model.conf_threshold,
            iou_threshold=self.settings.model.iou_threshold,
            conf_filter=self.settings.model.detection_conf_filter,
            imgsz=self.settings.model.imgsz
        )
        
        tracker = VehicleTracker(
            tracker_type=self.settings.tracker.tracker_type,
            track_buffer=self.settings.tracker.track_buffer,
            match_thresh=self.settings.tracker.match_thresh
        )
        
        # Open video
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")
        
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        if max_frames:
            total_frames = min(total_frames, max_frames + warmup_frames)
        
        # Initialize result
        result = BenchmarkResult(
            timestamp=datetime.now().isoformat(),
            video_path=video_path,
            model_path=self.settings.model.model_path,
            resolution=(width, height)
        )
        
        # Metrics storage
        fps_values = []
        detection_times = []
        tracking_times = []
        detections_per_frame = []
        
        frame_count = 0
        start_time = time.perf_counter()
        last_frame_time = start_time
        
        logger.info(f"Processing {total_frames} frames (warmup: {warmup_frames})")
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            frame_count += 1
            
            if frame_count > total_frames:
                break
            
            # Skip warmup frames for timing
            is_warmup = frame_count <= warmup_frames
            
            # Detection
            det_start = time.perf_counter()
            vehicle_types = list(self.settings.VEHICLE_DIMENSIONS.keys())
            detections = detector.detect(frame, vehicle_types)
            det_time = time.perf_counter() - det_start
            
            # Tracking
            track_start = time.perf_counter()
            _ = tracker.update(detections, frame)  # Update tracker state
            track_time = time.perf_counter() - track_start
            
            # Record metrics (skip warmup)
            if not is_warmup:
                detection_times.append(det_time * 1000)  # ms
                tracking_times.append(track_time * 1000)  # ms
                detections_per_frame.append(len(detections))
                
                # Count detections by class
                for det in detections:
                    cls = det['class']
                    result.detections_by_class[cls] = result.detections_by_class.get(cls, 0) + 1
                
                # FPS calculation
                current_time = time.perf_counter()
                frame_fps = 1.0 / (current_time - last_frame_time)
                fps_values.append(frame_fps)
                last_frame_time = current_time
            
            # Progress logging
            if frame_count % 100 == 0:
                progress = frame_count / total_frames * 100
                logger.info(f"Progress: {progress:.1f}% ({frame_count}/{total_frames})")
        
        cap.release()
        end_time = time.perf_counter()
        
        # Calculate final metrics
        measured_frames = frame_count - warmup_frames
        result.total_frames = measured_frames
        result.total_time = end_time - start_time
        
        if fps_values:
            result.avg_fps = np.mean(fps_values)
            result.min_fps = np.min(fps_values)
            result.max_fps = np.max(fps_values)
        
        if detection_times:
            result.avg_detection_time = np.mean(detection_times)
        
        if tracking_times:
            result.avg_tracking_time = np.mean(tracking_times)
        
        if detections_per_frame:
            result.avg_detections_per_frame = np.mean(detections_per_frame)
            result.total_detections = sum(detections_per_frame)
        
        result.unique_tracks = tracker.get_total_unique_vehicles()
        
        self.results = result
        
        logger.info("Benchmark completed!")
        self._log_results(result)
        
        return result
    
    def _log_results(self, result: BenchmarkResult):
        """Log benchmark results"""
        logger.info("=" * 60)
        logger.info("BENCHMARK RESULTS")
        logger.info("=" * 60)
        logger.info(f"Video: {result.video_path}")
        logger.info(f"Resolution: {result.resolution}")
        logger.info(f"Total Frames: {result.total_frames}")
        logger.info(f"Total Time: {result.total_time:.2f}s")
        logger.info("-" * 40)
        logger.info(f"Average FPS: {result.avg_fps:.2f}")
        logger.info(f"Min FPS: {result.min_fps:.2f}")
        logger.info(f"Max FPS: {result.max_fps:.2f}")
        logger.info("-" * 40)
        logger.info(f"Avg Detection Time: {result.avg_detection_time:.2f}ms")
        logger.info(f"Avg Tracking Time: {result.avg_tracking_time:.2f}ms")
        logger.info("-" * 40)
        logger.info(f"Total Detections: {result.total_detections}")
        logger.info(f"Avg Detections/Frame: {result.avg_detections_per_frame:.2f}")
        logger.info(f"Unique Tracks: {result.unique_tracks}")
        logger.info("-" * 40)
        logger.info("Detections by Class:")
        for cls, count in result.detections_by_class.items():
            logger.info(f"  {cls}: {count}")
        logger.info("=" * 60)
    
    def save_results(self, output_path: str = None):
        """
        Save benchmark results to JSON file.
        
        Args:
            output_path: Output file path. If None, auto-generate.
        """
        if self.results is None:
            logger.warning("No results to save. Run benchmark first.")
            return
        
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"benchmark_results_{timestamp}.json"
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.results.to_dict(), f, indent=2, ensure_ascii=False)
        
        logger.info(f"Results saved to: {output_path}")
    
    def compare_results(self, result1: BenchmarkResult, 
                       result2: BenchmarkResult) -> Dict:
        """
        Compare two benchmark results.
        
        Args:
            result1: First benchmark result
            result2: Second benchmark result
        
        Returns:
            Dictionary with comparison metrics
        """
        return {
            'fps_diff': result2.avg_fps - result1.avg_fps,
            'fps_improvement': (result2.avg_fps - result1.avg_fps) / result1.avg_fps * 100,
            'detection_time_diff': result2.avg_detection_time - result1.avg_detection_time,
            'tracking_time_diff': result2.avg_tracking_time - result1.avg_tracking_time,
        }


class DetectionEvaluator:
    """
    Evaluate detection accuracy against ground truth.
    
    Metrics:
    - Precision
    - Recall
    - mAP (mean Average Precision)
    - IoU (Intersection over Union)
    """
    
    def __init__(self, iou_threshold: float = 0.5):
        """
        Initialize evaluator.
        
        Args:
            iou_threshold: IoU threshold for considering a detection as correct
        """
        self.iou_threshold = iou_threshold
        
        # Results storage
        self.predictions: List[Dict] = []
        self.ground_truths: List[Dict] = []
    
    def add_prediction(self, frame_id: int, bbox: List[float], 
                      class_name: str, confidence: float):
        """
        Add a detection prediction.
        
        Args:
            frame_id: Frame identifier
            bbox: Bounding box [x1, y1, x2, y2]
            class_name: Predicted class
            confidence: Detection confidence
        """
        self.predictions.append({
            'frame_id': frame_id,
            'bbox': bbox,
            'class': class_name,
            'confidence': confidence
        })
    
    def add_ground_truth(self, frame_id: int, bbox: List[float], 
                        class_name: str):
        """
        Add a ground truth annotation.
        
        Args:
            frame_id: Frame identifier
            bbox: Bounding box [x1, y1, x2, y2]
            class_name: True class
        """
        self.ground_truths.append({
            'frame_id': frame_id,
            'bbox': bbox,
            'class': class_name
        })
    
    @staticmethod
    def calculate_iou(box1: List[float], box2: List[float]) -> float:
        """
        Calculate Intersection over Union between two boxes.
        
        Args:
            box1: First box [x1, y1, x2, y2]
            box2: Second box [x1, y1, x2, y2]
        
        Returns:
            IoU value (0-1)
        """
        # Calculate intersection
        x1 = max(box1[0], box2[0])
        y1 = max(box1[1], box2[1])
        x2 = min(box1[2], box2[2])
        y2 = min(box1[3], box2[3])
        
        if x2 <= x1 or y2 <= y1:
            return 0.0
        
        intersection = (x2 - x1) * (y2 - y1)
        
        # Calculate union
        area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
        area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
        union = area1 + area2 - intersection
        
        return intersection / union if union > 0 else 0.0
    
    def evaluate(self) -> Dict:
        """
        Evaluate predictions against ground truth.
        
        Returns:
            Dictionary with evaluation metrics
        """
        if not self.predictions or not self.ground_truths:
            logger.warning("No predictions or ground truths to evaluate")
            return {}
        
        # Group by frame
        pred_by_frame = {}
        for pred in self.predictions:
            fid = pred['frame_id']
            if fid not in pred_by_frame:
                pred_by_frame[fid] = []
            pred_by_frame[fid].append(pred)
        
        gt_by_frame = {}
        for gt in self.ground_truths:
            fid = gt['frame_id']
            if fid not in gt_by_frame:
                gt_by_frame[fid] = []
            gt_by_frame[fid].append(gt)
        
        # Calculate metrics
        true_positives = 0
        false_positives = 0
        false_negatives = 0
        
        # Get all unique classes
        all_classes = set()
        for pred in self.predictions:
            all_classes.add(pred['class'])
        for gt in self.ground_truths:
            all_classes.add(gt['class'])
        
        class_metrics = {cls: {'tp': 0, 'fp': 0, 'fn': 0} for cls in all_classes}
        
        # Process each frame
        all_frames = set(pred_by_frame.keys()) | set(gt_by_frame.keys())
        
        for frame_id in all_frames:
            preds = pred_by_frame.get(frame_id, [])
            gts = gt_by_frame.get(frame_id, [])
            
            # Sort predictions by confidence
            preds = sorted(preds, key=lambda x: x['confidence'], reverse=True)
            
            matched_gts = set()
            
            for pred in preds:
                best_iou = 0
                best_gt_idx = -1
                
                for i, gt in enumerate(gts):
                    if i in matched_gts:
                        continue
                    if gt['class'] != pred['class']:
                        continue
                    
                    iou = self.calculate_iou(pred['bbox'], gt['bbox'])
                    if iou > best_iou and iou >= self.iou_threshold:
                        best_iou = iou
                        best_gt_idx = i
                
                if best_gt_idx >= 0:
                    # True positive
                    true_positives += 1
                    class_metrics[pred['class']]['tp'] += 1
                    matched_gts.add(best_gt_idx)
                else:
                    # False positive
                    false_positives += 1
                    class_metrics[pred['class']]['fp'] += 1
            
            # Count false negatives
            for i, gt in enumerate(gts):
                if i not in matched_gts:
                    false_negatives += 1
                    class_metrics[gt['class']]['fn'] += 1
        
        # Calculate overall metrics
        precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
        recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        
        # Calculate per-class metrics
        per_class = {}
        for cls, metrics in class_metrics.items():
            tp, fp, fn = metrics['tp'], metrics['fp'], metrics['fn']
            p = tp / (tp + fp) if (tp + fp) > 0 else 0
            r = tp / (tp + fn) if (tp + fn) > 0 else 0
            per_class[cls] = {
                'precision': p,
                'recall': r,
                'f1': 2 * p * r / (p + r) if (p + r) > 0 else 0
            }
        
        return {
            'precision': precision,
            'recall': recall,
            'f1_score': f1,
            'true_positives': true_positives,
            'false_positives': false_positives,
            'false_negatives': false_negatives,
            'per_class': per_class,
            'iou_threshold': self.iou_threshold
        }
    
    def reset(self):
        """Reset all stored predictions and ground truths"""
        self.predictions.clear()
        self.ground_truths.clear()
