"""
Density Calculator
Calculates traffic density using area-based formula
"""

from typing import Dict
from ..config.settings import Settings


class DensityCalculator:
    """Calculate traffic density using Vietnamese formula"""
    
    def __init__(self, settings: Settings):
        """
        Initialize density calculator
        
        Args:
            settings: Settings object with vehicle dimensions
        """
        self.settings = settings
        self.vehicle_footprints = settings.get_vehicle_footprint_areas()
    
    def calculate_density(self, vehicle_counts: Dict[str, int], 
                         road_area: float) -> tuple[float, float]:
        """
        Calculate traffic density
        
        Formula: R = (TL / DT) × 100
        Where:
            TL = Σ(Xi × SLi) - Total occupied area
            Xi = Vehicle footprint area (length × width)
            SLi = Number of vehicles of type i
            DT = Road area (Ls × Ws)
            R = Density percentage
        
        Args:
            vehicle_counts: Dictionary of vehicle counts by type
            road_area: Road area in square meters (DT)
        
        Returns:
            Tuple of (total_occupied_area, density_percentage)
        """
        if road_area == 0:
            return 0.0, 0.0
        
        # Calculate total occupied area: TL = Σ(Xi × SLi)
        total_occupied_area = 0.0
        for vehicle_type, count in vehicle_counts.items():
            if vehicle_type in self.vehicle_footprints:
                Xi = self.vehicle_footprints[vehicle_type]  # Footprint area in m²
                SLi = count  # Number of vehicles
                total_occupied_area += Xi * SLi
        
        # Calculate density percentage: R = (TL / DT) × 100
        density_percentage = (total_occupied_area / road_area) * 100
        
        return total_occupied_area, density_percentage
    
    def get_density_level(self, density_percentage: float) -> tuple[str, str, tuple]:
        """
        Get density level classification
        
        Args:
            density_percentage: Density percentage (R)
        
        Returns:
            Tuple of (level_name, status_text, color_bgr)
        """
        threshold = self.settings.get_density_level(density_percentage)
        return threshold.level_name, threshold.status_text, threshold.color_bgr
    
    def get_vehicle_info(self, vehicle_type: str) -> dict:
        """Get vehicle dimension info"""
        if vehicle_type in self.settings.VEHICLE_DIMENSIONS:
            dims = self.settings.VEHICLE_DIMENSIONS[vehicle_type]
            return {
                'length': dims.length,
                'width': dims.width,
                'height': dims.height,
                'footprint': dims.footprint_area
            }
        return None
