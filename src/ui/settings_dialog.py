from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QFormLayout, QFileDialog, QComboBox
from src.config import ConfigManager

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.resize(400, 200)
        self.config_manager = ConfigManager()
        self.config = self.config_manager.get_config()

        layout = QVBoxLayout(self)
        form = QFormLayout()

        # Download Folder
        self.folder_input = QLineEdit(self.config.download_folder)
        self.browse_btn = QPushButton("Browse")
        self.browse_btn.clicked.connect(self.browse_folder)
        form.addRow("Default Folder:", self.folder_input)
        form.addRow("", self.browse_btn)

        # Max Concurrent
        self.concurrent_input = QLineEdit(str(self.config.max_concurrent_downloads))
        form.addRow("Max Concurrent Downloads:", self.concurrent_input)
        
        # Global Padding
        self.padding_combo = QComboBox()
        self.padding_combo.addItems(["None", "00 (2 digits)", "000 (3 digits)", "0000 (4 digits)", "00000 (5 digits)"])
        
        # Set current index based on config
        current_pad = self.config.global_padding
        if current_pad == "00": self.padding_combo.setCurrentIndex(1)
        elif current_pad == "000": self.padding_combo.setCurrentIndex(2)
        elif current_pad == "0000": self.padding_combo.setCurrentIndex(3)
        elif current_pad == "00000": self.padding_combo.setCurrentIndex(4)
        else: self.padding_combo.setCurrentIndex(0)
        
        form.addRow("Default Padding:", self.padding_combo)

        layout.addLayout(form)

        # Buttons
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.save)
        layout.addWidget(save_btn)

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Download Folder")
        if folder:
            self.folder_input.setText(folder)

    def save(self):
        self.config_manager.set_download_folder(self.folder_input.text())
        try:
            concurrent = int(self.concurrent_input.text())
            self.config_manager.set_max_concurrent(concurrent)
        except ValueError:
            pass # Ignore invalid int

        pad_text = self.padding_combo.currentText()
        if "00 (2 digits)" in pad_text: val = "00"
        elif "000 (3 digits)" in pad_text: val = "000"
        elif "0000 (4 digits)" in pad_text: val = "0000"
        elif "00000 (5 digits)" in pad_text: val = "00000"
        else: val = None
        self.config_manager.set_global_padding(val)
        
        self.accept()
