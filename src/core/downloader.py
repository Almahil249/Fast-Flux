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
    job_cancelled = pyqtSignal(str)
    # Signals: First URL status (int), Last URL status (int), First error (str), Last error (str)
    connectivity_tested = pyqtSignal(int, int, str, str)

class Downloader:
    def __init__(self, segment_manager: SegmentManager):
        self.segment_manager = segment_manager
        self.signals = DownloaderSignals()
        self.active_jobs = {}
        self.cancellation_tokens = {}  # job_name -> bool (True = cancel requested)
        self.session = None

    async def start_job(self, job: Job):
        self.active_jobs[job.name] = job
        self.cancellation_tokens[job.name] = False  # Initialize cancellation token
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
        except asyncio.CancelledError:
            # Job was cancelled
            job.status = "Cancelled"
            self.signals.job_cancelled.emit(job.name)
        except Exception as e:
            print(f"Job failed: {e}")
            job.status = "Failed"
            self.signals.job_failed.emit(job.name, str(e))
        finally:
             # Wait for progress monitor to finish one last update
            progress_task.cancel()
            
            # Clean up cancellation token
            if job.name in self.cancellation_tokens:
                del self.cancellation_tokens[job.name]
            
            # Check completion (only if not cancelled)
            if job.status == "Running":
                if all(s.status == SegmentStatus.COMPLETED for s in job.segments):
                    job.status = "Completed"
                    self.signals.job_completed.emit(job.name)
                else:
                     # Check for failures
                     failed_count = sum(1 for s in job.segments if s.status == SegmentStatus.FAILED)
                     if failed_count > 0:
                          self.signals.job_failed.emit(job.name, f"{failed_count} segments failed.")

    async def download_segment(self, job: Job, segment: Segment):
        # Check if job is cancelled before starting
        if self.cancellation_tokens.get(job.name, False):
            return
            
        target_path = self.segment_manager.get_segment_path(job, segment)
        
        if self.segment_manager.check_segment_exists(job, segment):
            segment.status = SegmentStatus.COMPLETED
            self.signals.segment_status_changed.emit(job.name, segment.index, "Completed")
            return

        async with self.semaphore:
            # Check again after acquiring semaphore
            if self.cancellation_tokens.get(job.name, False):
                return
                
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

    def cancel_job(self, job_name: str):
        """
        Requests cancellation of a job. The download_segment coroutines will
        check this flag and exit early. Does NOT clean up files immediately
        since downloads may still be in progress - use clear_cache separately.
        """
        if job_name in self.cancellation_tokens:
            self.cancellation_tokens[job_name] = True
            
        # Update job status
        if job_name in self.active_jobs:
            job = self.active_jobs[job_name]
            job.status = "Cancelled"
            self.signals.job_cancelled.emit(job_name)
            # Note: File cleanup is deferred - user can use "Clear Cache" button
            # after cancellation completes to remove partial files

    async def test_connectivity(self, first_url: str, last_url: str):
        """
        Tests connectivity to both the first and last segment URLs.
        Performs HEAD requests (falls back to GET) and reports status codes.
        Emits connectivity_tested signal with results.
        """
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        
        async def check_url(url: str) -> tuple[int, str]:
            """Returns (status_code, error_message)"""
            try:
                # Try HEAD first, some servers don't support it
                async with self.session.head(url, timeout=10, allow_redirects=True) as response:
                    status = response.status
                    if status == 404:
                        return status, "Not Found (404)"
                    elif status == 403:
                        return status, "Forbidden (403)"
                    elif status >= 400:
                        return status, f"HTTP Error ({status})"
                    return status, ""
            except aiohttp.ClientResponseError as e:
                return e.status, f"HTTP Error ({e.status})"
            except aiohttp.ClientError as e:
                # Try GET as fallback
                try:
                    async with self.session.get(url, timeout=10, allow_redirects=True) as response:
                        status = response.status
                        if status == 404:
                            return status, "Not Found (404)"
                        elif status == 403:
                            return status, "Forbidden (403)"
                        elif status >= 400:
                            return status, f"HTTP Error ({status})"
                        return status, ""
                except aiohttp.ClientError as get_e:
                    return 0, f"Connection Error: {str(get_e)[:50]}"
            except asyncio.TimeoutError:
                return 0, "Timeout"
            except Exception as e:
                return 0, f"Error: {str(e)[:50]}"
        
        first_status, first_error = await check_url(first_url)
        last_status, last_error = await check_url(last_url)
        
        self.signals.connectivity_tested.emit(first_status, last_status, first_error, last_error)
        return first_status, last_status, first_error, last_error

    async def close(self):
        if self.session:
            await self.session.close()
