from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

class SegmentStatus(Enum):
    PENDING = "Pending"
    DOWNLOADING = "Downloading"
    COMPLETED = "Completed"
    FAILED = "Failed"

@dataclass
class Segment:
    index: int
    url: str
    status: SegmentStatus = SegmentStatus.PENDING
    file_path: Optional[str] = None
    size: int = 0
    retries: int = 0

class JobStatus(Enum):
    QUEUED = "Queued"
    RUNNING = "Running"
    PAUSED = "Paused"
    COMPLETED = "Completed"
    FAILED = "Failed"

@dataclass
class Job:
    name: str # Acts as ID
    base_url: str
    start_index: int
    end_index: int
    output_filename: str
    status: JobStatus = JobStatus.QUEUED
    segments: List[Segment] = field(default_factory=list)
    total_size: int = 0
    downloaded_segments: int = 0
    failed_segments: List[int] = field(default_factory=list)

    @property
    def total_segments(self) -> int:
        return self.end_index - self.start_index + 1
