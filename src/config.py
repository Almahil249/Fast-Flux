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

        if not self.config.download_folder:
            # Default to user's Downloads folder
            self.config.download_folder = os.path.join(os.path.expanduser("~"), "Downloads")

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
