"""
Calibration Widget - Helper widget for calibration display
(Currently integrated into VideoWidget)
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt


class CalibrationWidget(QWidget):
    """Helper widget for calibration instructions and info"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        """Setup UI"""
        layout = QVBoxLayout(self)
        
        title = QLabel("Hướng Dẫn Hiệu Chỉnh")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)
        
        instructions = QLabel(
            "1. Chấm 4 điểm trên video để đánh dấu vùng quan sát\n"
            "2. Nhập chiều dài thực tế (Ls) của đoạn đường\n"
            "3. Nhập chiều rộng thực tế (Ws) của đường\n"
            "4. Hệ thống sẽ tính diện tích DT = Ls × Ws\n\n"
            "Lưu ý:\n"
            "- Chấm 4 điểm theo thứ tự: góc trên trái → trên phải → dưới phải → dưới trái\n"
            "- Đảm bảo vùng được đánh dấu là vùng cần giám sát\n"
            "- Nhập kích thước thực tế chính xác để tính mật độ đúng"
        )
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        
        layout.addStretch()
