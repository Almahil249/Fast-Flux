import subprocess
import os

class ThumbnailGenerator:
    @staticmethod
    def extract_frame(input_path: str, output_path: str, ffmpeg_path: str = "ffmpeg") -> bool:
        """
        Extracts the first frame from a video segment using ffmpeg.
        """
        try:
            # -i input: Input file
            # -frames:v 1: Extract 1 frame
            # -q:v 2: Output quality (JPEG)
            # -y: Overwrite output
            command = [
                ffmpeg_path,
                "-i", input_path,
                "-frames:v", "1",
                "-q:v", "2",
                "-y",
                output_path
            ]
            
            # Use subprocess.run to execute ffmpeg
            # Hide console window on Windows
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
                return True
            else:
                print(f"ffmpeg error: {result.stderr}")
                return False
        except Exception as e:
            print(f"Thumbnail generation error: {e}")
            return False
