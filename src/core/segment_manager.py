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

    def clear_job_cache(self, job: Job) -> bool:
        """
        Clears the cache directory for a job.
        Returns True if successful, False if files are in use.
        """
        cache_dir = self.get_job_cache_path(job.name)
        if os.path.exists(cache_dir):
            try:
                shutil.rmtree(cache_dir)
                return True
            except PermissionError:
                # Files still in use (common on Windows during/after cancellation)
                raise PermissionError(
                    f"Cannot clear cache - files are still in use.\n"
                    f"Wait a moment for downloads to fully stop, then try again."
                )
        return True

    def check_segment_exists(self, job: Job, segment: Segment) -> bool:
        path = self.get_segment_path(job, segment)
        return os.path.exists(path) and os.path.getsize(path) > 0
    
    def get_all_segment_files(self, job: Job) -> list[str]:
        """Returns a sorted list of all segment file paths for merging."""
        files = []
        for segment in job.segments:
            files.append(self.get_segment_path(job, segment))
        return files
    
    @staticmethod
    def clear_all_caches(base_path: str) -> int:
        """
        Scans the base_path directory and removes all Cache_* subdirectories.
        Returns the number of cache directories removed.
        """
        count = 0
        if not os.path.exists(base_path):
            return count
            
        for item in os.listdir(base_path):
            if item.startswith("Cache_"):
                cache_path = os.path.join(base_path, item)
                if os.path.isdir(cache_path):
                    try:
                        shutil.rmtree(cache_path)
                        count += 1
                    except Exception as e:
                        print(f"Failed to remove cache {cache_path}: {e}")
        return count

