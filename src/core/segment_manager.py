import os
import shutil
from src.core.types import Job, Segment

class SegmentManager:
    def __init__(self, base_download_path: str):
        self.base_download_path = base_download_path

    def initialize_job_cache(self, job: Job):
        """Creates the cache directory for the job."""
        cache_dir = self.get_job_cache_path(job.name)
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir, exist_ok=True)

    def get_job_cache_path(self, job_name: str) -> str:
        # Sanitize job name to be safe for folder name
        safe_name = "".join(c for c in job_name if c.isalnum() or c in (' ', '_', '-')).strip()
        return os.path.join(self.base_download_path, f"Cache_{safe_name}")

    def get_segment_path(self, job: Job, segment: Segment) -> str:
        """Returns the absolute path where the segment should be saved, using index-based naming."""
        cache_dir = self.get_job_cache_path(job.name)
        # Use simple index.ts naming (e.g., 001.ts, 002.ts)
        # We can use a fixed padding like 5 digits to ensure correct sorting for huge lists
        filename = f"{segment.index:05d}.ts" 
        return os.path.join(cache_dir, filename)

    def clear_job_cache(self, job: Job):
        cache_dir = self.get_job_cache_path(job.name)
        if os.path.exists(cache_dir):
            shutil.rmtree(cache_dir)

    def check_segment_exists(self, job: Job, segment: Segment) -> bool:
        path = self.get_segment_path(job, segment)
        return os.path.exists(path) and os.path.getsize(path) > 0
    
    def get_all_segment_files(self, job: Job) -> list[str]:
        """Returns a sorted list of all segment file paths for merging."""
        files = []
        for segment in job.segments:
            files.append(self.get_segment_path(job, segment))
        return files
