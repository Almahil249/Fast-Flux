import os
import shutil
from concurrent.futures import ThreadPoolExecutor
from typing import List

class Merger:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=1)

    def merge_segments(self, segment_files: List[str], output_file: str) -> bool:
        """
        Merges segments into a single file using a separate thread for blocking I/O.
        Returns a Future (implicitly handled if using run_in_executor correctly in async context, 
        but here we design it to be called from an async wrapper or directly).
        For this synchronous implementation, it blocks. 
        It is intended to be run with loop.run_in_executor.
        """
        try:
            # Ensure output directory exists
            output_dir = os.path.dirname(output_file)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)

            with open(output_file, 'wb') as outfile:
                for segment_path in segment_files:
                    if not os.path.exists(segment_path):
                        print(f"Missing segment during merge: {segment_path}")
                        continue
                        
                    with open(segment_path, 'rb') as infile:
                        shutil.copyfileobj(infile, outfile)
            return True
        except Exception as e:
            print(f"Merge error: {e}")
            return False

    def verify_integrity(self, segment_files: List[str], output_file: str) -> bool:
        """
        Checks if the output file size matches the sum of segment sizes.
        """
        try:
            if not os.path.exists(output_file):
                return False
                
            total_segment_size = sum(os.path.getsize(f) for f in segment_files if os.path.exists(f))
            final_size = os.path.getsize(output_file)
            
            return total_segment_size == final_size
        except Exception as e:
            print(f"Integrity check error: {e}")
            return False

    def attach_thumbnail(self, video_path: str, thumb_path: str, ffmpeg_path: str = "ffmpeg") -> bool:
        """
        Attaches a thumbnail to the video file as cover art using ffmpeg.
        """
        if not os.path.exists(video_path) or not os.path.exists(thumb_path):
            return False
            
        temp_output = video_path + ".tmp.mp4"
        try:
            # -i video: Input video
            # -i thumb: Input image
            # -map 0: Map all streams from first input
            # -map 1: Map first stream from second input
            # -c copy: Copy video/audio streams without re-encoding
            # -c:v:1 png/jpg: (Implicit if copying)
            # -disposition:v:1 attached_pic: Set the image as cover art
            command = [
                ffmpeg_path,
                "-i", video_path,
                "-i", thumb_path,
                "-map", "0",
                "-map", "1",
                "-c", "copy",
                "-disposition:v:1", "attached_pic",
                "-y",
                temp_output
            ]
            
            import subprocess
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                startupinfo=startupinfo
            )
            
            if result.returncode == 0:
                # Replace original with new one
                os.remove(video_path)
                os.rename(temp_output, video_path)
                return True
            else:
                print(f"ffmpeg cover art error: {result.stderr}")
                if os.path.exists(temp_output):
                    os.remove(temp_output)
                return False
        except Exception as e:
            print(f"Attach thumbnail error: {e}")
            if os.path.exists(temp_output):
                os.remove(temp_output)
            return False

