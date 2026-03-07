import json
import os
from dataclasses import dataclass, asdict
from typing import Optional

CONFIG_FILE = "config.json"

@dataclass
class AppConfig:
    download_folder: str = ""
    max_concurrent_downloads: int = 20
    global_padding: Optional[str] = None  # "00", "000", etc. or None
    ffmpeg_path: str = "ffmpeg"  # Default to system ffmpeg

class ConfigManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance.config = AppConfig()
            cls._instance.load_config()
        return cls._instance

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    data = json.load(f)
                    self.config = AppConfig(**data)
            except Exception as e:
                print(f"Error loading config: {e}")
                # Fallback to default
                self.config = AppConfig()

        self._ensure_ffmpeg()

        if not self.config.download_folder:
            # Default to user's Downloads folder / Fast-Flux
            self.config.download_folder = os.path.join(os.path.expanduser("~"), "Downloads", "Fast-Flux")

    def save_config(self):
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(asdict(self.config), f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")

    def get_config(self) -> AppConfig:
        return self.config

    def set_download_folder(self, path: str):
        self.config.download_folder = path
        self.save_config()

    def set_max_concurrent(self, value: int):
        self.config.max_concurrent_downloads = value
        self.save_config()

    def set_global_padding(self, value: Optional[str]):
        self.config.global_padding = value
        self.save_config()

    def set_ffmpeg_path(self, path: str):
        self.config.ffmpeg_path = path
        self.save_config()

    def _ensure_ffmpeg(self):
        """Checks if ffmpeg exists and sets default if bundled version is found."""
        # If user has set a specific valid path, keep it
        if os.path.exists(self.config.ffmpeg_path):
            return

        # Check for bundled ffmpeg in bin/
        resource_dir = os.environ.get("FF_RESOURCE_DIR", os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
        bundled_ffmpeg = os.path.join(resource_dir, "bin", "ffmpeg.exe")
        
        if os.path.exists(bundled_ffmpeg):
            self.config.ffmpeg_path = bundled_ffmpeg
        else:
            # Fallback to system ffmpeg if nothing else found
            self.config.ffmpeg_path = "ffmpeg"
