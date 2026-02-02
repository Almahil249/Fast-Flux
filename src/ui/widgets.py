from PyQt6.QtWidgets import QWidget, QVBoxLayout, QProgressBar, QLabel, QHBoxLayout, QGridLayout
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QBrush, QPen

class SegmentMap(QWidget):
    """
    Visualizes segments as a grid of blocks.
    Green = Completed, Red = Failed, Gray = Pending/Downloading (can differentiate if needed).
    Using QPainter for performance with high segment counts instead of individual widgets.
    """
    def __init__(self, total_segments: int):
        super().__init__()
        self.total_segments = total_segments
        # 0: Pending/Downloading, 1: Completed, 2: Failed
        self.status_map = [0] * total_segments 
        self.setMinimumHeight(100)
        self.start_index = 0 # To map real index to 0-based array

    def set_range(self, start: int, end: int):
        self.start_index = start
        self.total_segments = end - start + 1
        self.status_map = [0] * self.total_segments
        self.update()

    def update_segment(self, real_index: int, status: str):
        local_idx = real_index - self.start_index
        if 0 <= local_idx < len(self.status_map):
            if status == "Completed":
                self.status_map[local_idx] = 1
            elif status == "Failed":
                self.status_map[local_idx] = 2
            else:
                self.status_map[local_idx] = 0
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        rect = self.rect()
        width = rect.width()
        
        # Determine grid size
        if self.total_segments == 0:
            return

        # Simple logic: fill width, then new row
        cols = width // 10  # 10px per block
        if cols == 0: cols = 1
        
        block_size = 8
        spacing = 2

        for i, status in enumerate(self.status_map):
            row = i // cols
            col = i % cols
            
            x = col * (block_size + spacing)
            y = row * (block_size + spacing)
            
            # Don't draw if out of bounds (vertical)
            if y > rect.height():
                break

            if status == 1:
                color = QColor("green")
            elif status == 2:
                color = QColor("red")
            else:
                color = QColor("lightgray")

            painter.fillRect(x, y, block_size, block_size, QBrush(color))

class JobProgressBar(QWidget):
    def __init__(self, job_name: str):
        super().__init__()
        self.job_name = job_name
        self.layout = QVBoxLayout(self)
        
        self.info_layout = QHBoxLayout()
        self.name_label = QLabel(f"Job: {job_name}")
        self.stats_label = QLabel("Waiting...")
        self.info_layout.addWidget(self.name_label)
        self.info_layout.addStretch()
        self.info_layout.addWidget(self.stats_label)
        
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        
        self.layout.addLayout(self.info_layout)
        self.layout.addWidget(self.bar)

    def update_progress(self, progress: float, speed: str, eta: str):
        self.bar.setValue(int(progress))
        self.stats_label.setText(f"Speed: {speed} | ETA: {eta}")
