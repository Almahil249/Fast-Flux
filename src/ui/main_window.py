import asyncio
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QLineEdit, QPushButton, QGroupBox, QScrollArea,
    QMessageBox, QTextEdit
)
from PyQt6.QtCore import pyqtSlot
from qasync import asyncSlot

from src.core.downloader import Downloader
from src.core.segment_manager import SegmentManager
from src.core.merger import Merger
from src.core.types import Job, Segment, SegmentStatus
from src.config import ConfigManager
from src.ui.widgets import SegmentMap, JobProgressBar
from src.ui.settings_dialog import SettingsDialog
from src.utils.helpers import get_example_urls

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Fast-Flux Turbo Downloader")
        self.resize(900, 700)

        # Core Components
        self.config_manager = ConfigManager()
        self.segment_manager = SegmentManager(self.config_manager.get_config().download_folder)
        self.downloader = Downloader(self.segment_manager)
        self.merger = Merger()
        
        self.jobs = {} # Job Name -> UI Widget Ref
        
        # Connect Downloader Signals
        self.downloader.signals.job_progress_updated.connect(self.on_progress_update)
        self.downloader.signals.segment_status_changed.connect(self.on_segment_status)
        self.downloader.signals.job_completed.connect(self.on_job_completed)
        self.downloader.signals.job_failed.connect(self.on_job_failed)

        self.setup_ui()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # === Input Area ===
        input_group = QGroupBox("New Job")
        input_layout = QVBoxLayout()
        
        # URL
        url_layout = QHBoxLayout()
        url_layout.addWidget(QLabel("Base URL:"))
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("http://example.com/segment_[index].ts")
        url_layout.addWidget(self.url_input)
        input_layout.addLayout(url_layout)

        # Indices & Settings
        idx_layout = QHBoxLayout()
        self.start_input = QLineEdit()
        self.start_input.setPlaceholderText("Start Index (e.g. 1)")
        self.end_input = QLineEdit()
        self.end_input.setPlaceholderText("End Index (e.g. 100)")
        self.filename_input = QLineEdit()
        self.filename_input.setPlaceholderText("Output Filename (e.g. video.mp4)")
        
        idx_layout.addWidget(QLabel("Start:"))
        idx_layout.addWidget(self.start_input)
        idx_layout.addWidget(QLabel("End:"))
        idx_layout.addWidget(self.end_input)
        idx_layout.addWidget(QLabel("Filename:"))
        idx_layout.addWidget(self.filename_input)
        input_layout.addLayout(idx_layout)

        # Actions
        btn_layout = QHBoxLayout()
        self.test_btn = QPushButton("Test URL")
        self.test_btn.clicked.connect(self.test_url)
        self.add_job_btn = QPushButton("Start Job")
        self.add_job_btn.clicked.connect(self.add_job)
        self.settings_btn = QPushButton("Settings")
        self.settings_btn.clicked.connect(self.open_settings)
        
        btn_layout.addWidget(self.test_btn)
        btn_layout.addWidget(self.add_job_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.settings_btn)
        input_layout.addLayout(btn_layout)
        
        input_group.setLayout(input_layout)
        main_layout.addWidget(input_group)

        # === Job Dashboard ===
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.jobs_container = QWidget()
        self.jobs_layout = QVBoxLayout(self.jobs_container)
        self.jobs_layout.addStretch() # Push items up
        self.scroll_area.setWidget(self.jobs_container)
        
        main_layout.addWidget(self.scroll_area)
        
        # === Log/Console (Optional) ===
        # self.log_area = QTextEdit()
        # self.log_area.setMaximumHeight(100)
        # main_layout.addWidget(self.log_area)

    def open_settings(self):
        dlg = SettingsDialog(self)
        if dlg.exec():
            # Update segment manager path if changed
            new_path = self.config_manager.get_config().download_folder
            self.segment_manager.base_download_path = new_path

    def test_url(self):
        base_url = self.url_input.text()
        try:
            start = int(self.start_input.text())
            end = int(self.end_input.text())
        except ValueError:
            QMessageBox.warning(self, "Error", "Invalid indices")
            return

        padding = self.config_manager.get_config().global_padding
        first, last = get_example_urls(base_url, start, end, padding)
        
        msg = f"First Segment:\n{first}\n\nLast Segment:\n{last}\n\nDoes this look correct?"
        QMessageBox.information(self, "URL Test", msg)

    @asyncSlot()
    async def add_job(self):
        try:
            base_url = self.url_input.text()
            start = int(self.start_input.text())
            end = int(self.end_input.text())
            fname = self.filename_input.text().strip() or "output.mp4"
            if not fname.endswith(('.mp4', '.ts')):
                fname += ".mp4"
                
            padding = self.config_manager.get_config().global_padding
        except ValueError:
            QMessageBox.warning(self, "Error", "Invalid indices")
            return

        if start > end:
            QMessageBox.warning(self, "Error", "Start index must be <= End index")
            return

        # Create Job Object
        job_name = fname.replace(".", "_") # Simple unique ID logic
        job = Job(job_name, base_url, start, end, fname)
        
        # Generate segments
        for i in range(start, end + 1):
            url = get_example_urls(base_url, i, i, padding)[0]
            job.segments.append(Segment(i, url))

        # Create UI
        job_widget = QWidget()
        job_layout = QVBoxLayout(job_widget)
        
        pbar = JobProgressBar(job_name)
        seg_map = SegmentMap(job.total_segments)
        seg_map.set_range(start, end)

        # Merge Button (initially disabled or hidden, shows on completion)
        merge_btn = QPushButton("Merge")
        merge_btn.setEnabled(False)
        merge_btn.clicked.connect(lambda: self.start_merge(job))

        job_layout.addWidget(pbar)
        job_layout.addWidget(seg_map)
        job_layout.addWidget(merge_btn)
        
        # Add frame styling
        job_widget.setStyleSheet("border: 1px solid #ccc; margin: 5px; padding: 5px; border-radius: 5px;")
        
        self.jobs_layout.insertWidget(0, job_widget) # Add to top
        self.jobs[job_name] = {
            "job": job,
            "pbar": pbar,
            "map": seg_map,
            "merge_btn": merge_btn,
            "widget": job_widget
        }

        # Start Download
        asyncio.create_task(self.downloader.start_job(job))

    @pyqtSlot(str, float, str, str)
    def on_progress_update(self, job_name, progress, speed, eta):
        if job_name in self.jobs:
            self.jobs[job_name]["pbar"].update_progress(progress, speed, eta)

    @pyqtSlot(str, int, str)
    def on_segment_status(self, job_name, index, status):
        if job_name in self.jobs:
            self.jobs[job_name]["map"].update_segment(index, status)

    @asyncSlot(str)
    async def on_job_completed(self, job_name):
        if job_name in self.jobs:
            ui = self.jobs[job_name]
            ui["pbar"].stats_label.setText("Download Complete! Auto-merging...")
            
            # Auto-Merge
            await self.start_merge(ui["job"])

    @pyqtSlot(str, str)
    def on_job_failed(self, job_name, error):
        if job_name in self.jobs:
             self.jobs[job_name]["pbar"].stats_label.setText(f"Failed: {error}")

    async def start_merge(self, job: Job):
        ui = self.jobs[job.name]
        ui["merge_btn"].setEnabled(False)
        ui["pbar"].stats_label.setText("Merging...")
        
        # Get all valid files from segment manager
        files = self.segment_manager.get_all_segment_files(job)
        output_path = f"{self.config_manager.get_config().download_folder}/{job.output_filename}"
        
        # Run in executor
        loop = asyncio.get_event_loop()
        success = await loop.run_in_executor(
            self.merger.executor, 
            self.merger.merge_segments, 
            files, 
            output_path
        )
        
        if success:
             # Integrity Check
             valid = await loop.run_in_executor(
                 self.merger.executor,
                 self.merger.verify_integrity,
                 files,
                 output_path
            )
             
             if valid:
                 ui["pbar"].stats_label.setText(f"Done! Saved to {output_path}")
                 QMessageBox.information(self, "Success", f"Job {job.name} finished!\nFile: {output_path}")
             else:
                 ui["pbar"].stats_label.setText("Merge finished but integrity check failed.")
        else:
            ui["pbar"].stats_label.setText("Merge Failed.")
