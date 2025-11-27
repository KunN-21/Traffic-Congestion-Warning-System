"""
Real-time Chart Widget for Traffic Statistics
Displays live charts for density, vehicle counts, and speed
"""

from typing import List, Dict
from collections import deque
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QPen, QColor, QFont, QPainterPath

from ..utils.logger import get_logger

logger = get_logger(__name__)


class LineChartWidget(QWidget):
    """
    Real-time line chart widget using QPainter.
    
    Features:
    - Multiple data series
    - Auto-scaling Y axis
    - Smooth animations
    - Grid lines
    - Legend
    """
    
    # Colors for different series
    SERIES_COLORS = [
        QColor(66, 133, 244),   # Blue
        QColor(234, 67, 53),    # Red
        QColor(251, 188, 5),    # Yellow
        QColor(52, 168, 83),    # Green
        QColor(171, 71, 188),   # Purple
        QColor(0, 172, 193),    # Cyan
    ]
    
    def __init__(self, title: str = "Chart", max_points: int = 100, parent=None):
        super().__init__(parent)
        self.title = title
        self.max_points = max_points
        
        # Data storage - series_name: deque of values
        self.data: Dict[str, deque] = {}
        self.series_order: List[str] = []
        
        # Chart settings
        self.margin_left = 60
        self.margin_right = 20
        self.margin_top = 40
        self.margin_bottom = 30
        
        self.y_min = 0
        self.y_max = 100
        self.auto_scale = True
        
        self.grid_lines = 5
        self.show_legend = True
        self.show_grid = True
        
        # Background color
        self.background_color = QColor(30, 30, 30)
        self.grid_color = QColor(60, 60, 60)
        self.text_color = QColor(200, 200, 200)
        
        self.setMinimumHeight(150)
        
    def apply_theme(self, is_dark: bool):
        """Apply theme colors"""
        if is_dark:
            self.background_color = QColor(30, 30, 30)
            self.grid_color = QColor(60, 60, 60)
            self.text_color = QColor(200, 200, 200)
        else:
            self.background_color = QColor(245, 245, 245)
            self.grid_color = QColor(200, 200, 200)
            self.text_color = QColor(50, 50, 50)
        self.update()
    
    def add_series(self, name: str, color: QColor = None):
        """Add a new data series"""
        if name not in self.data:
            self.data[name] = deque(maxlen=self.max_points)
            self.series_order.append(name)
            logger.debug(f"Added chart series: {name}")
    
    def add_data(self, series_name: str, value: float):
        """Add a data point to a series"""
        if series_name not in self.data:
            self.add_series(series_name)
        
        self.data[series_name].append(value)
        
        # Auto-scale Y axis
        if self.auto_scale:
            self._update_y_scale()
        
        self.update()  # Trigger repaint
    
    def add_multiple_data(self, data: Dict[str, float]):
        """Add data to multiple series at once"""
        for series_name, value in data.items():
            if series_name not in self.data:
                self.add_series(series_name)
            self.data[series_name].append(value)
        
        if self.auto_scale:
            self._update_y_scale()
        
        self.update()
    
    def _update_y_scale(self):
        """Update Y axis scale based on data"""
        all_values = []
        for series in self.data.values():
            all_values.extend(series)
        
        if all_values:
            self.y_min = 0
            self.y_max = max(all_values) * 1.1  # 10% padding
            if self.y_max < 10:
                self.y_max = 10
    
    def clear(self):
        """Clear all data"""
        for series in self.data.values():
            series.clear()
        self.update()
    
    def paintEvent(self, event):
        """Paint the chart"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Background
        painter.fillRect(self.rect(), self.background_color)
        
        # Calculate chart area
        chart_left = self.margin_left
        chart_right = self.width() - self.margin_right
        chart_top = self.margin_top
        chart_bottom = self.height() - self.margin_bottom
        chart_width = chart_right - chart_left
        chart_height = chart_bottom - chart_top
        
        if chart_width <= 0 or chart_height <= 0:
            return
        
        # Draw title
        painter.setPen(QPen(self.text_color))
        font = QFont()
        font.setPointSize(10)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(chart_left, 20, self.title)
        
        # Draw grid
        if self.show_grid:
            self._draw_grid(painter, chart_left, chart_top, chart_width, chart_height)
        
        # Draw Y axis labels
        self._draw_y_axis(painter, chart_left, chart_top, chart_height)
        
        # Draw data series
        for i, series_name in enumerate(self.series_order):
            if series_name in self.data:
                color = self.SERIES_COLORS[i % len(self.SERIES_COLORS)]
                self._draw_series(painter, series_name, color, 
                                chart_left, chart_top, chart_width, chart_height)
        
        # Draw legend
        if self.show_legend and self.series_order:
            self._draw_legend(painter, chart_right)
    
    def _draw_grid(self, painter: QPainter, x: int, y: int, w: int, h: int):
        """Draw grid lines"""
        painter.setPen(QPen(self.grid_color, 1, Qt.PenStyle.DotLine))
        
        # Horizontal grid lines
        for i in range(self.grid_lines + 1):
            y_pos = y + (h * i / self.grid_lines)
            painter.drawLine(int(x), int(y_pos), int(x + w), int(y_pos))
        
        # Vertical grid lines (every 20 points)
        num_vertical = 5
        for i in range(num_vertical + 1):
            x_pos = x + (w * i / num_vertical)
            painter.drawLine(int(x_pos), int(y), int(x_pos), int(y + h))
    
    def _draw_y_axis(self, painter: QPainter, x: int, y: int, h: int):
        """Draw Y axis labels"""
        painter.setPen(QPen(self.text_color))
        font = QFont()
        font.setPointSize(8)
        painter.setFont(font)
        
        for i in range(self.grid_lines + 1):
            y_pos = y + (h * i / self.grid_lines)
            value = self.y_max - (self.y_max - self.y_min) * i / self.grid_lines
            painter.drawText(5, int(y_pos + 4), f"{value:.1f}")
    
    def _draw_series(self, painter: QPainter, series_name: str, color: QColor,
                     x: int, y: int, w: int, h: int):
        """Draw a data series line"""
        data = list(self.data[series_name])
        if len(data) < 2:
            return
        
        painter.setPen(QPen(color, 2))
        
        path = QPainterPath()
        
        for i, value in enumerate(data):
            # Calculate position
            x_pos = x + (w * i / (self.max_points - 1))
            y_pos = y + h - (h * (value - self.y_min) / (self.y_max - self.y_min))
            
            # Clamp to chart area
            y_pos = max(y, min(y + h, y_pos))
            
            if i == 0:
                path.moveTo(x_pos, y_pos)
            else:
                path.lineTo(x_pos, y_pos)
        
        painter.drawPath(path)
    
    def _draw_legend(self, painter: QPainter, x: int):
        """Draw legend"""
        font = QFont()
        font.setPointSize(8)
        painter.setFont(font)
        
        legend_x = x - 100
        legend_y = 15
        
        for i, series_name in enumerate(self.series_order):
            color = self.SERIES_COLORS[i % len(self.SERIES_COLORS)]
            
            # Draw color box
            painter.fillRect(legend_x, legend_y + i * 15 - 8, 10, 10, color)
            
            # Draw label
            painter.setPen(QPen(self.text_color))
            painter.drawText(legend_x + 15, legend_y + i * 15, series_name)


class TrafficChartPanel(QWidget):
    """
    Panel containing multiple charts for traffic monitoring.
    
    Includes:
    - Density chart over time
    - Vehicle count chart
    - Speed chart (if available)
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.history_length = 100  # Number of data points to keep
        
        self.setup_ui()
        
        logger.info("TrafficChartPanel initialized")
    
    def setup_ui(self):
        """Setup the UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)
        
        # Chart selector
        selector_layout = QHBoxLayout()
        selector_layout.addWidget(QLabel("Biểu đồ:"))
        
        self.chart_selector = QComboBox()
        self.chart_selector.addItems([
            "Mật độ giao thông",
            "Số lượng xe",
            "Tốc độ trung bình"
        ])
        self.chart_selector.currentIndexChanged.connect(self._on_chart_changed)
        selector_layout.addWidget(self.chart_selector)
        selector_layout.addStretch()
        
        layout.addLayout(selector_layout)
        
        # Density chart
        self.density_chart = LineChartWidget("Mật độ giao thông (%)", self.history_length)
        self.density_chart.add_series("Mật độ")
        self.density_chart.y_max = 100
        layout.addWidget(self.density_chart)
        
        # Vehicle count chart
        self.count_chart = LineChartWidget("Số lượng xe", self.history_length)
        self.count_chart.add_series("Xe máy")
        self.count_chart.add_series("Ô tô")
        self.count_chart.add_series("Xe tải")
        self.count_chart.add_series("Xe buýt")
        self.count_chart.add_series("Xe đạp")
        self.count_chart.hide()
        layout.addWidget(self.count_chart)
        
        # Speed chart
        self.speed_chart = LineChartWidget("Tốc độ trung bình (km/h)", self.history_length)
        self.speed_chart.add_series("Tốc độ TB")
        self.speed_chart.y_max = 60
        self.speed_chart.hide()
        layout.addWidget(self.speed_chart)
        
    def apply_theme(self, is_dark: bool):
        """Apply theme to all charts"""
        self.density_chart.apply_theme(is_dark)
        self.count_chart.apply_theme(is_dark)
        self.speed_chart.apply_theme(is_dark)
    
    def _on_chart_changed(self, index: int):
        """Handle chart selector change"""
        self.density_chart.hide()
        self.count_chart.hide()
        self.speed_chart.hide()
        
        if index == 0:
            self.density_chart.show()
        elif index == 1:
            self.count_chart.show()
        elif index == 2:
            self.speed_chart.show()
    
    def update_data(self, stats: Dict):
        """
        Update charts with new statistics.
        
        Args:
            stats: Dictionary containing:
                - density_percentage: float
                - vehicle_counts: Dict[str, int]
                - average_speed: float (optional)
        """
        # Update density chart
        if 'density_percentage' in stats:
            self.density_chart.add_data("Mật độ", stats['density_percentage'])
        
        # Update vehicle count chart
        if 'vehicle_counts' in stats:
            counts = stats['vehicle_counts']
            self.count_chart.add_multiple_data({
                "Xe máy": counts.get('motorcycle', 0),
                "Ô tô": counts.get('car', 0),
                "Xe tải": counts.get('truck', 0),
                "Xe buýt": counts.get('bus', 0),
                "Xe đạp": counts.get('bicycle', 0)
            })
        
        # Update speed chart
        if 'average_speed' in stats:
            self.speed_chart.add_data("Tốc độ TB", stats['average_speed'])
    
    def clear(self):
        """Clear all charts"""
        self.density_chart.clear()
        self.count_chart.clear()
        self.speed_chart.clear()


class MiniDensityGauge(QWidget):
    """
    Compact density gauge widget showing current density level.
    
    Displays as a circular gauge with color coding.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.value = 0.0
        self.max_value = 100.0
        self.status_text = ""
        self.status_color = QColor(0, 255, 0)
        
        self.setMinimumSize(100, 100)
        self.setMaximumSize(150, 150)
        
        self.bg_color = QColor(60, 60, 60)
        self.text_color = QColor(255, 255, 255)
        
    def apply_theme(self, is_dark: bool):
        """Apply theme colors"""
        if is_dark:
            self.bg_color = QColor(60, 60, 60)
            self.text_color = QColor(255, 255, 255)
        else:
            self.bg_color = QColor(200, 200, 200)
            self.text_color = QColor(50, 50, 50)
        self.update()
    
    def set_value(self, value: float, status_text: str = "", color: tuple = None):
        """
        Set gauge value.
        
        Args:
            value: Density percentage (0-100)
            status_text: Status text to display
            color: BGR color tuple
        """
        self.value = min(max(value, 0), self.max_value)
        self.status_text = status_text
        
        if color:
            # Convert BGR to RGB
            self.status_color = QColor(color[2], color[1], color[0])
        
        self.update()
    
    def paintEvent(self, event):
        """Paint the gauge"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Calculate dimensions
        size = min(self.width(), self.height()) - 10
        x = (self.width() - size) // 2
        y = (self.height() - size) // 2
        
        # Draw background arc
        painter.setPen(QPen(self.bg_color, 8))
        painter.drawArc(x, y, size, size, 225 * 16, -270 * 16)
        
        # Draw value arc
        angle = int((self.value / self.max_value) * 270)
        painter.setPen(QPen(self.status_color, 8))
        painter.drawArc(x, y, size, size, 225 * 16, -angle * 16)
        
        # Draw center text
        # Draw center text
        painter.setPen(QPen(self.text_color))
        font = QFont()
        font.setPointSize(14)
        font.setBold(True)
        painter.setFont(font)
        
        text = f"{self.value:.1f}%"
        text_rect = painter.fontMetrics().boundingRect(text)
        painter.drawText(
            (self.width() - text_rect.width()) // 2,
            self.height() // 2 + 5,
            text
        )
        
        # Draw status text
        font.setPointSize(9)
        font.setBold(False)
        painter.setFont(font)
        painter.setPen(QPen(self.status_color))
        
        status_rect = painter.fontMetrics().boundingRect(self.status_text)
        painter.drawText(
            (self.width() - status_rect.width()) // 2,
            self.height() // 2 + 25,
            self.status_text
        )
