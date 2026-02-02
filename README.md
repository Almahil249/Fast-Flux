# Fast-Flux Turbo Segment Downloader

**Fast-Flux** is a high-performance, multi-threaded Python GUI application designed to download and merge `.ts` video segments with extreme speed. It leverages asynchronous I/O (`aiohttp`) and buffered binary merging to handle hundreds of segments efficiently.

## 🚀 Features

*   **Turbo-Charged Downloading**: Uses `asyncio` and `aiohttp` to download dozens of segments concurrently (default 20, customizable).
*   **Double-Buffered Merging**: Merges segments using a high-speed binary stream approach (`shutil.copyfileobj`) running in a background thread, preventing UI freezes.
*   **Modern GUI**: Built with `PyQt6`, featuring a real-time **Segment Map** that visualizes the status of every individual segment (Green=Done, Red=Fail, Gray=Pending).
*   **Smart Automation**: Auto-detects padding (e.g., `001.ts`), retries failed segments, and performs integrity checks after merging.
*   **Persistent Config**: Remembers your download folder and settings between sessions.

---

## 🛠️ Setup & Installation

### Prerequisites
*   Windows, macOS, or Linux
*   Python 3.13+

### 1. Install Dependencies
Open a terminal in the project folder and run:

```powershell
pip install -r requirements.txt
```

*Note: If you encounter permission errors, try `pip install --user -r requirements.txt`.*

### 2. Run the Application
You can run the application directly from the source:

```powershell
python src/main.py
```

---

## 📖 How to Use

### 1. Configuration (First Run)
*   Click the **Settings** button in the bottom-right corner.
*   **Default Folder**: Choose where you want your videos to be saved.
*   **Max Concurrent**: Set the number of parallel downloads (e.g., 20-50).
*   **Default Padding**: Select the numbering style of your URL segments (e.g., `000` for `segment_001.ts`).
*   Click **Save**.

### 2. Downloading a Video
1.  **Base URL**: Paste the URL for the segments, replacing the number with `[index]`.
    *   *Example*: `https://example.com/videos/segment_[index].ts`
2.  **Start / End**: Enter the starting and ending segment numbers (e.g., `1` to `500`).
3.  **Filename**: Name your output file (e.g., `my_movie.mp4`).
4.  **Test URL** (Optional): Click this to verify that the app generates the correct URLs for the first and last segment.
5.  **Start Job**: Click to begin.

### 3. Monitoring
*   **Progress Bar**: Shows overall progress, current speed in segments/sec, and ETA.
*   **Segment Map**: Watch the grid fill up!
    *   🟩 **Green**: Successfully downloaded.
    *   🟥 **Red**: Failed (will NOT merge automatically if failures exist).
    *   ⬜ **Gray**: Waiting.

### 4. Merging
*   Once all segments are downloaded, the app will **automatically** merge them into your Output Filename.
*   If artifacts are missing, you can retry or check the logs.

---

## 📂 Project Structure

A quick guide to the codebase:

*   **`src/main.py`**: The entry point of the application. Handles `sys.path` setup and launches the UI.
*   **`src/config.py`**: Manages `config.json` for saving user preferences (Download folder, concurrency).
*   **`src/core/`**: contains the heavy-lifting logic.
    *   `downloader.py`: Async engine using `aiohttp`. Manages the download queue and signals.
    *   `merger.py`: Handles high-speed binary file concatenation.
    *   `segment_manager.py`: Manages file paths, caching, and renaming logic (e.g., `001.ts`).
    *   `types.py`: Dataclasses for `Job` and `Segment` state.
*   **`src/ui/`**: PyQt6 GUI components.
    *   `main_window.py`: The main dashboard logic.
    *   `widgets.py`: Custom UI elements like the **SegmentMap** (the visual grid).
*   **`src/utils/`**: Helper functions for URL parsing.

---

## 🔧 Troubleshooting

### Common Errors

**1. `ModuleNotFoundError: No module named 'src'`**
*   **Cause**: Running the script from the wrong directory or python path issue.
*   **Fix**: Always run from the root `Fast-Flux` folder using `python src/main.py`. (This has been patched in the latest version to auto-detect root).

**2. `Merge error: [Errno 22] Invalid argument`**
*   **Cause**: Your output filename might contain invalid characters (like newlines `\n` from copy-pasting).
*   **Fix**: The app now auto-sanitizes filenames. Ensure your filename doesn't contain symbols like `/ \ : * ? " < > |`.

**3. "Segments Failed" / Red Blocks**
*   **Cause**: 404 Not Found or Timeout.
*   **Fix**: Check your **Base URL** and **Indices**. Use the **Test URL** button to ensure you aren't requesting `segment_500.ts` when the video only has 100 segments.

**4. UI Freezing**
*   **Cause**: Too many concurrent downloads updating the UI too fast.
*   **Fix**: Reduce **Max Concurrent Downloads** in Settings (try 10-20). The app uses signal throttling, but extreme values can still lag older CPUs.
