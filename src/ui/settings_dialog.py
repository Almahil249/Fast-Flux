from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, 
    QFormLayout, QFileDialog, QComboBox, QHBoxLayout, QMessageBox
)
from src.config import ConfigManager
from src.core.segment_manager import SegmentManager

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.resize(400, 250)
        self.config_manager = ConfigManager()
        self.config = self.config_manager.get_config()

        layout = QVBoxLayout(self)
        form = QFormLayout()

        # Download Folder
        folder_layout = QHBoxLayout()
        self.folder_input = QLineEdit(self.config.download_folder)
        self.folder_input.textChanged.connect(self.on_folder_changed)
        self.browse_btn = QPushButton("Browse")
        self.browse_btn.clicked.connect(self.browse_folder)
        folder_layout.addWidget(self.folder_input)
        folder_layout.addWidget(self.browse_btn)
        form.addRow("Default Folder:", folder_layout)

        # Max Concurrent
        self.concurrent_input = QLineEdit(str(self.config.max_concurrent_downloads))
        form.addRow("Max Concurrent Downloads:", self.concurrent_input)
        
        # Global Padding
        self.padding_combo = QComboBox()
        self.padding_combo.addItems(["None", "00 (2 digits)", "000 (3 digits)", "0000 (4 digits)", "00000 (5 digits)"])
        self.padding_combo.currentIndexChanged.connect(self.on_padding_changed)
        
        # Set current index based on config
        current_pad = self.config.global_padding
        if current_pad == "00": self.padding_combo.setCurrentIndex(1)
        elif current_pad == "000": self.padding_combo.setCurrentIndex(2)
        elif current_pad == "0000": self.padding_combo.setCurrentIndex(3)
        elif current_pad == "00000": self.padding_combo.setCurrentIndex(4)
        else: self.padding_combo.setCurrentIndex(0)
        
        form.addRow("Default Padding:", self.padding_combo)

        layout.addLayout(form)

        # Cache Management
        cache_layout = QHBoxLayout()
        self.clear_cache_btn = QPushButton("Clear All Cache")
        self.clear_cache_btn.setStyleSheet("background-color: #ff6b6b; color: white;")
        self.clear_cache_btn.clicked.connect(self.clear_all_cache)
        cache_layout.addStretch()
        cache_layout.addWidget(self.clear_cache_btn)
        layout.addLayout(cache_layout)

        # Buttons
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save && Close")
        save_btn.clicked.connect(self.save)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Download Folder")
        if folder:
            self.folder_input.setText(folder)
            # Auto-save is handled by textChanged signal

    def on_folder_changed(self, text):
        """Immediately save folder changes to config."""
        self.config_manager.set_download_folder(text)

    def on_padding_changed(self, index):
        """Immediately save padding changes to config."""
        pad_text = self.padding_combo.currentText()
        if "00 (2 digits)" in pad_text: val = "00"
        elif "000 (3 digits)" in pad_text: val = "000"
        elif "0000 (4 digits)" in pad_text: val = "0000"
        elif "00000 (5 digits)" in pad_text: val = "00000"
        else: val = None
        self.config_manager.set_global_padding(val)

    def clear_all_cache(self):
        """Clear all cache directories in the download folder."""
        download_folder = self.config.download_folder
        
        reply = QMessageBox.question(
            self, 
            "Clear All Cache", 
            f"This will delete all Cache_* folders in:\n{download_folder}\n\nAre you sure?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            count = SegmentManager.clear_all_caches(download_folder)
            QMessageBox.information(
                self, 
                "Cache Cleared", 
                f"Removed {count} cache folder(s)."
            )

    def save(self):
        # Folder and padding are auto-saved, just save concurrent
        try:
            concurrent = int(self.concurrent_input.text())
            self.config_manager.set_max_concurrent(concurrent)
        except ValueError:
            pass # Ignore invalid int
        
        self.accept()
