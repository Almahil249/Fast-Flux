import asyncio
import os
import aiohttp
import aiofiles
import time
from PyQt6.QtCore import QObject, pyqtSignal
from src.core.types import Job, Segment, SegmentStatus
from src.core.segment_manager import SegmentManager
from src.config import ConfigManager

class DownloaderSignals(QObject):
    # Signals: Job Name, Segment Index, Status
    segment_status_changed = pyqtSignal(str, int, str) 
    # Signals: Job Name, Progress (0-100), Speed (str), ETA (str)
    job_progress_updated = pyqtSignal(str, float, str, str)
    job_completed = pyqtSignal(str)
    job_failed = pyqtSignal(str, str)

class Downloader:
    def __init__(self, segment_manager: SegmentManager):
        self.segment_manager = segment_manager
        self.signals = DownloaderSignals()
        self.active_jobs = {}
        self.session = None

    async def start_job(self, job: Job):
        self.active_jobs[job.name] = job
        job.status = "Running"
        
        # Initialize Cache
        self.segment_manager.initialize_job_cache(job)
        
        # Configure Semaphore
        config = ConfigManager().get_config()
        self.semaphore = asyncio.Semaphore(config.max_concurrent_downloads)

        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()

        tasks = []
        for segment in job.segments:
            if segment.status != SegmentStatus.COMPLETED:
                tasks.append(self.download_segment(job, segment))
        
        # Monitor progress in background
        progress_task = asyncio.create_task(self.monitor_progress(job))
        
        try:
            await asyncio.gather(*tasks)
        except Exception as e:
            print(f"Job failed: {e}")
            job.status = "Failed"
            self.signals.job_failed.emit(job.name, str(e))
        finally:
             # Wait for progress monitor to finish one last update
            progress_task.cancel()
            
            # Check completion
            if all(s.status == SegmentStatus.COMPLETED for s in job.segments):
                job.status = "Completed"
                self.signals.job_completed.emit(job.name)
            else:
                 # Check for failures
                 failed_count = sum(1 for s in job.segments if s.status == SegmentStatus.FAILED)
                 if failed_count > 0:
                      self.signals.job_failed.emit(job.name, f"{failed_count} segments failed.")

    async def download_segment(self, job: Job, segment: Segment):
        target_path = self.segment_manager.get_segment_path(job, segment)
        
        if self.segment_manager.check_segment_exists(job, segment):
            segment.status = SegmentStatus.COMPLETED
            self.signals.segment_status_changed.emit(job.name, segment.index, "Completed")
            return

        async with self.semaphore:
            segment.status = SegmentStatus.DOWNLOADING
            # Immediate status update for downloading start
            self.signals.segment_status_changed.emit(job.name, segment.index, "Downloading")
            
            try:
                async with self.session.get(segment.url, timeout=30) as response:
                    if response.status == 200:
                        async with aiofiles.open(target_path, 'wb') as f:
                            await f.write(await response.read())
                        segment.status = SegmentStatus.COMPLETED
                        segment.size = os.path.getsize(target_path)
                        job.downloaded_segments += 1
                        self.signals.segment_status_changed.emit(job.name, segment.index, "Completed")
                    else:
                        segment.status = SegmentStatus.FAILED
                        self.signals.segment_status_changed.emit(job.name, segment.index, "Failed")
            except Exception as e:
                print(f"Segment {segment.index} error: {e}")
                segment.status = SegmentStatus.FAILED
                self.signals.segment_status_changed.emit(job.name, segment.index, "Failed")

    async def monitor_progress(self, job: Job):
        """
        Periodically calculates progress and emits throttled signals.
        """
        start_time = time.time()
        last_emit = 0
        throttle_interval = 0.1 # 100ms
        
        while job.status == "Running":
            now = time.time()
            if now - last_emit >= throttle_interval:
                # Calculate metrics
                total = job.total_segments
                completed = sum(1 for s in job.segments if s.status == SegmentStatus.COMPLETED)
                progress = (completed / total) * 100 if total > 0 else 0
                
                # Speed calculation (Simple Implementation)
                # A more robust one would track bytes/sec over a sliding window
                elapsed = now - start_time
                if elapsed > 0:
                    # Estimate based on avg segment completions/sec for now (simplification)
                    # Real byte tracking would require hooks into the read buffer
                    segments_per_sec = completed / elapsed
                    speed_str = f"{segments_per_sec:.1f} seg/s"
                    
                    remaining = total - completed
                    eta_seconds = remaining / segments_per_sec if segments_per_sec > 0 else 0
                    eta_str = f"{int(eta_seconds)}s"
                else:
                    speed_str = "0.0 seg/s"
                    eta_str = "--"

                self.signals.job_progress_updated.emit(job.name, progress, speed_str, eta_str)
                last_emit = now
            
            await asyncio.sleep(0.05) # Check/Sleep 50ms

    async def close(self):
        if self.session:
            await self.session.close()
