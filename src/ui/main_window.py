import asyncio
import os
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QLineEdit, QPushButton, QGroupBox, QScrollArea,
    QMessageBox, QTextEdit, QFrame, QFileDialog, QDialog,
    QFormLayout, QComboBox, QDialogButtonBox
)
from PyQt6.QtCore import pyqtSlot
from qasync import asyncSlot

from src.core.downloader import Downloader
from src.core.segment_manager import SegmentManager
from src.core.merger import Merger
from src.core.types import Job, Segment, SegmentStatus, JobStatus
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
        self.downloader.signals.job_cancelled.connect(self.on_job_cancelled)
        self.downloader.signals.connectivity_tested.connect(self.on_connectivity_tested)

        self.setup_ui()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # === Top Bar (Settings, Merge Folder, & Clear History) ===
        top_bar = QHBoxLayout()
        top_bar.addStretch()
        
        self.merge_folder_btn = QPushButton("📁 Merge Folder")
        self.merge_folder_btn.clicked.connect(self.standalone_merge)
        self.merge_folder_btn.setToolTip("Select a folder with downloaded segments to merge into a video")
        
        self.clear_history_btn = QPushButton("Clear History")
        self.clear_history_btn.clicked.connect(self.clear_history)
        self.clear_history_btn.setToolTip("Remove completed jobs from the list (does not delete files)")
        
        self.settings_btn = QPushButton("⚙ Settings")
        self.settings_btn.clicked.connect(self.open_settings)
        
        top_bar.addWidget(self.merge_folder_btn)
        top_bar.addWidget(self.clear_history_btn)
        top_bar.addWidget(self.settings_btn)
        main_layout.addLayout(top_bar)

        # === Input Area ===
        input_group = QGroupBox("New Job")
        input_layout = QVBoxLayout()
        
        # URL
        url_layout = QHBoxLayout()
        url_layout.addWidget(QLabel("Base URL:"))
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("http://example.com/segment_[i or index].ts")
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

        # URL Test Status Label
        self.url_status_label = QLabel("")
        self.url_status_label.setStyleSheet("color: #666; font-style: italic;")
        input_layout.addWidget(self.url_status_label)

        # Actions
        btn_layout = QHBoxLayout()
        self.test_btn = QPushButton("Test URL")
        self.test_btn.clicked.connect(self.test_url)
        self.add_job_btn = QPushButton("Start Job")
        self.add_job_btn.clicked.connect(self.add_job)
        
        btn_layout.addWidget(self.test_btn)
        btn_layout.addWidget(self.add_job_btn)
        btn_layout.addStretch()
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

    def open_settings(self):
        dlg = SettingsDialog(self)
        if dlg.exec():
            # Update segment manager path if changed
            new_path = self.config_manager.get_config().download_folder
            self.segment_manager.base_download_path = new_path

    @asyncSlot()
    async def test_url(self):
        """Async URL testing with HEAD/GET requests to first and last indices."""
        base_url = self.url_input.text().strip()
        try:
            start = int(self.start_input.text())
            end = int(self.end_input.text())
        except ValueError:
            QMessageBox.warning(self, "Error", "Invalid indices")
            return

        padding = self.config_manager.get_config().global_padding
        first_url, last_url = get_example_urls(base_url, start, end, padding)
        
        # Update UI to show testing
        self.url_status_label.setText("Testing connectivity...")
        self.url_status_label.setStyleSheet("color: #0077cc; font-style: italic;")
        self.test_btn.setEnabled(False)
        
        # Perform async connectivity test
        await self.downloader.test_connectivity(first_url, last_url)

    @pyqtSlot(int, int, str, str)
    def on_connectivity_tested(self, first_status, last_status, first_error, last_error):
        """Handle connectivity test results."""
        self.test_btn.setEnabled(True)
        
        results = []
        
        # First URL result
        if first_error:
            results.append(f"First: ❌ {first_error}")
        elif first_status == 200:
            results.append(f"First: ✓ OK ({first_status})")
        else:
            results.append(f"First: ⚠ Status {first_status}")
        
        # Last URL result
        if last_error:
            results.append(f"Last: ❌ {last_error}")
        elif last_status == 200:
            results.append(f"Last: ✓ OK ({last_status})")
        else:
            results.append(f"Last: ⚠ Status {last_status}")
        
        status_text = " | ".join(results)
        
        # Color based on results
        if first_error or last_error or first_status >= 400 or last_status >= 400:
            self.url_status_label.setStyleSheet("color: #cc3333; font-weight: bold;")
        else:
            self.url_status_label.setStyleSheet("color: #33cc33; font-weight: bold;")
        
        self.url_status_label.setText(status_text)

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

        # Button row
        btn_row = QHBoxLayout()
        
        # Cancel Button
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("background-color: #ff6b6b; color: white;")
        cancel_btn.clicked.connect(lambda: self.cancel_job(job_name))
        
        # Clear Cache Button
        clear_cache_btn = QPushButton("Clear Cache")
        clear_cache_btn.clicked.connect(lambda: self.clear_job_cache(job_name))
        
        # Retry Merge Button (initially hidden)
        retry_merge_btn = QPushButton("Retry Merge")
        retry_merge_btn.setStyleSheet("background-color: #ffaa00; color: white;")
        retry_merge_btn.clicked.connect(lambda: asyncio.create_task(self.start_merge(job)))
        retry_merge_btn.setVisible(False)
        
        # Merge Button (initially disabled)
        merge_btn = QPushButton("Merge")
        merge_btn.setEnabled(False)
        merge_btn.clicked.connect(lambda: asyncio.create_task(self.start_merge(job)))

        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(clear_cache_btn)
        btn_row.addStretch()
        btn_row.addWidget(retry_merge_btn)
        btn_row.addWidget(merge_btn)

        job_layout.addWidget(pbar)
        job_layout.addWidget(seg_map)
        job_layout.addLayout(btn_row)
        
        # Add frame styling
        job_widget.setStyleSheet("border: 1px solid #ccc; margin: 5px; padding: 5px; border-radius: 5px;")
        
        self.jobs_layout.insertWidget(0, job_widget) # Add to top
        self.jobs[job_name] = {
            "job": job,
            "pbar": pbar,
            "map": seg_map,
            "merge_btn": merge_btn,
            "cancel_btn": cancel_btn,
            "clear_cache_btn": clear_cache_btn,
            "retry_merge_btn": retry_merge_btn,
            "widget": job_widget
        }

        # Start Download
        asyncio.create_task(self.downloader.start_job(job))

    def cancel_job(self, job_name: str):
        """Cancel an active job."""
        if job_name in self.jobs:
            self.downloader.cancel_job(job_name)
            ui = self.jobs[job_name]
            ui["cancel_btn"].setEnabled(False)
            ui["pbar"].stats_label.setText("Cancelled")

    def clear_job_cache(self, job_name: str):
        """Clear cache for a specific job."""
        if job_name in self.jobs:
            job = self.jobs[job_name]["job"]
            reply = QMessageBox.question(
                self, 
                "Clear Cache", 
                f"Delete cached segments for '{job_name}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                try:
                    self.segment_manager.clear_job_cache(job)
                    QMessageBox.information(self, "Cache Cleared", f"Cache for '{job_name}' has been deleted.")
                except PermissionError as e:
                    QMessageBox.warning(
                        self, 
                        "Cannot Clear Cache", 
                        str(e)
                    )

    def clear_history(self):
        """Remove completed jobs from the UI (does not delete files)."""
        jobs_to_remove = []
        for job_name, ui in self.jobs.items():
            job = ui["job"]
            # Remove completed, cancelled, or failed jobs
            if job.status in ["Completed", "Cancelled", "Failed", "Merge Error",
                              JobStatus.COMPLETED, JobStatus.CANCELLED, JobStatus.FAILED, JobStatus.MERGE_ERROR]:
                jobs_to_remove.append(job_name)
        
        for job_name in jobs_to_remove:
            ui = self.jobs[job_name]
            ui["widget"].setParent(None)
            ui["widget"].deleteLater()
            del self.jobs[job_name]
        
        if jobs_to_remove:
            QMessageBox.information(self, "History Cleared", f"Removed {len(jobs_to_remove)} job(s) from the list.")

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
            ui["cancel_btn"].setEnabled(False)
            ui["pbar"].stats_label.setText("Download Complete! Auto-merging...")
            
            # Auto-Merge
            await self.start_merge(ui["job"])

    @pyqtSlot(str, str)
    def on_job_failed(self, job_name, error):
        if job_name in self.jobs:
            ui = self.jobs[job_name]
            ui["pbar"].stats_label.setText(f"Failed: {error}")
            ui["cancel_btn"].setEnabled(False)
            ui["merge_btn"].setEnabled(True)  # Allow manual merge attempt

    @pyqtSlot(str)
    def on_job_cancelled(self, job_name):
        if job_name in self.jobs:
            ui = self.jobs[job_name]
            ui["pbar"].stats_label.setText("Cancelled")
            ui["cancel_btn"].setEnabled(False)

    async def start_merge(self, job: Job):
        ui = self.jobs[job.name]
        ui["merge_btn"].setEnabled(False)
        ui["retry_merge_btn"].setVisible(False)
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
                 job.status = JobStatus.COMPLETED
                 ui["pbar"].stats_label.setText(f"✓ Done! Saved to {output_path}")
             else:
                 job.status = JobStatus.MERGE_ERROR
                 ui["pbar"].stats_label.setText("⚠ Merge finished but integrity check failed.")
                 ui["retry_merge_btn"].setVisible(True)
        else:
            job.status = JobStatus.MERGE_ERROR
            ui["pbar"].stats_label.setText("❌ Merge Failed - Click 'Retry Merge' to try again")
            ui["retry_merge_btn"].setVisible(True)

    @asyncSlot()
    async def standalone_merge(self):
        """Open folder dialog and merge segments from a selected folder."""
        # Select folder containing segments
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Select Folder with Downloaded Segments",
            self.config_manager.get_config().download_folder
        )
        
        if not folder_path:
            return
        
        # Scan for segment files (.ts)
        segment_files = []
        for filename in os.listdir(folder_path):
            if filename.endswith('.ts'):
                segment_files.append(os.path.join(folder_path, filename))
        
        if not segment_files:
            QMessageBox.warning(
                self, 
                "No Segments Found", 
                "No .ts segment files found in the selected folder."
            )
            return
        
        # Sort segment files naturally (by numeric prefix if present)
        segment_files.sort(key=lambda f: os.path.basename(f))
        
        # Extract folder name and remove "Cache_" prefix if present
        folder_name = os.path.basename(folder_path)
        if folder_name.startswith("Cache_"):
            folder_name = folder_name[6:]  # Remove "Cache_" prefix
        
        # Show merge dialog for filename/extension editing
        dialog = MergeDialog(self, folder_name)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        
        output_filename = dialog.get_output_filename()
        output_path = os.path.join(
            self.config_manager.get_config().download_folder,
            output_filename
        )
        
        # Perform merge
        QMessageBox.information(
            self, 
            "Merging", 
            f"Merging {len(segment_files)} segments into {output_filename}..."
        )
        
        loop = asyncio.get_event_loop()
        success = await loop.run_in_executor(
            self.merger.executor,
            self.merger.merge_segments,
            segment_files,
            output_path
        )
        
        if success:
            # Integrity check
            valid = await loop.run_in_executor(
                self.merger.executor,
                self.merger.verify_integrity,
                segment_files,
                output_path
            )
            
            if valid:
                QMessageBox.information(
                    self, 
                    "Merge Complete", 
                    f"✓ Successfully merged to:\n{output_path}"
                )
            else:
                QMessageBox.warning(
                    self, 
                    "Merge Warning", 
                    f"⚠ Merge completed but integrity check failed.\nFile: {output_path}"
                )
        else:
            QMessageBox.critical(
                self, 
                "Merge Failed", 
                "❌ Failed to merge segments. Check console for details."
            )



def sanitize_filename(filename: str) -> str:
    """Remove characters that are invalid in Windows filenames."""
    # Windows invalid characters: \ / : * ? " < > |
    invalid_chars = r'\/:*?"<>|'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    # Also remove leading/trailing spaces and dots
    filename = filename.strip(' .')
    return filename if filename else 'output'


class MergeDialog(QDialog):
    """Dialog for editing output filename and extension for standalone merge."""
    
    def __init__(self, parent, suggested_name: str):
        super().__init__(parent)
        self.setWindowTitle("Merge Settings")
        self.setModal(True)
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout(self)
        
        # Form layout for inputs
        form_layout = QFormLayout()
        
        # Filename input (sanitize the suggested name)
        self.filename_input = QLineEdit(sanitize_filename(suggested_name))
        form_layout.addRow("Filename:", self.filename_input)
        
        # Extension dropdown
        self.extension_combo = QComboBox()
        self.extension_combo.addItems(["mp4", "ts", "mkv", "avi", "mov"])
        self.extension_combo.setCurrentText("mp4")  # Default to mp4
        form_layout.addRow("Extension:", self.extension_combo)
        
        layout.addLayout(form_layout)
        
        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def get_output_filename(self) -> str:
        """Returns the full filename with extension, sanitized for safety."""
        name = self.filename_input.text().strip()
        ext = self.extension_combo.currentText()
        
        # Remove any existing extension from name
        if '.' in name:
            name = name.rsplit('.', 1)[0]
        
        # Sanitize the filename to remove invalid characters
        name = sanitize_filename(name)
        
        return f"{name}.{ext}"
