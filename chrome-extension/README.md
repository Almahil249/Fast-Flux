# Fast-Flux Chrome Extension

A Chrome extension port of **Fast-Flux Turbo Downloader**.  
Downloads hundreds/thousands of numbered `.ts` video segments **concurrently**, then streams them directly to disk — supporting output files **up to 4GB** (the physical disk limit).

---

## 📁 Extension Structure

```
chrome-extension/
├── manifest.json        # Extension manifest (MV3)
├── background.js        # Service worker: all download logic
├── sidepanel.html       # Full-featured side panel UI
├── sidepanel.html       # Same HTML used for panel
├── panel.css            # Dark futuristic UI styles
├── panel.js             # Panel logic, streaming merge
├── popup.html           # Compact toolbar popup (stats + open panel)
├── popup.js             # Popup logic
├── icons/               # Extension icons (16/32/48/128px)
├── source_icon.png      # Source icon for regenerating sizes
└── generate_icons.py    # Re-generate icons from source_icon.png
```

---

## 🚀 Installing in Chrome (Developer Mode)

1. Open Chrome and go to: `chrome://extensions/`
2. Enable **Developer Mode** (top-right toggle)
3. Click **"Load unpacked"**
4. Select the `chrome-extension` folder from this repo
5. The extension icon will appear in your toolbar

### Opening the Side Panel
- Click the **Fast-Flux icon** in the toolbar → "Open Full Panel"
- Or: Right-click the icon → "Open side panel"
- The side panel opens alongside any webpage

---

## 📖 How to Use

### 1. Enter Job Details
| Field | Description |
|-------|-------------|
| **Base URL** | URL with `[index]` or `[i]` as the segment number placeholder |
| **Start Index** | First segment number (e.g. `1`) |
| **End Index** | Last segment number (e.g. `500`) |
| **Padding** | Leading zeros style (`001`, `0001`, etc.) |
| **Output Filename** | Your merged output file name (e.g. `video.mp4`) |
| **Concurrency** | Parallel downloads (default: 20, max: 100) |

**Example URL:** `https://cdn.example.com/hls/segment_[index].ts`

### 2. Test URL (Optional)
Click **Test URL** to verify the first and last segment URLs return HTTP 200 before starting.

### 3. Start Download
Click **Start Download**. The job card appears in the queue showing:
- Real-time **progress bar** and percentage
- **Speed** (segments/sec) and **ETA**
- **Total downloaded size** in MB/GB
- **Segment map**: a color-coded grid of every segment
  - 🟩 **Green** = Downloaded
  - 🟥 **Red** = Failed
  - 🟦 **Blue pulse** = Actively downloading
  - ⬜ **Dark** = Pending

### 4. Save & Merge (4GB-safe)
When all segments finish, click **Save & Merge**:
- A native **file save dialog** opens (you choose the location)
- Segments are **streamed one-by-one** to disk using the [File System Access API](https://developer.chrome.com/docs/capabilities/web-apis/file-system-access)
- **Never loads the full file into RAM** — safe for 4GB+ outputs
- A merge progress bar shows segments written

### 5. Retry Failed
If some segments failed (network errors), click **Retry Failed** to re-attempt only the failed ones.

---

## ⚙️ Settings

Click the gear icon to configure:

| Setting | Default | Description |
|---------|---------|-------------|
| **Default Concurrency** | 20 | Parallel download limit |
| **Request Timeout** | 30000ms | Per-segment timeout before retry |
| **Default Padding** | None | Leading-zero format for segment numbers |

Settings are persisted via `chrome.storage.local`.

---

## 🔬 Technical Details

### Large File Support (4GB Max)
The classic approach of `Blob.arrayBuffer()` → in-memory merge breaks above ~1-2GB on most systems. Fast-Flux uses the **File System Access API** with `FileSystemWritableFileStream`:

```javascript
const fileHandle = await window.showSaveFilePicker({ suggestedName: 'video.mp4' });
const writable = await fileHandle.createWritable();
for (const seg of completedSegments) {
  const buffer = await getSegmentBuffer(seg.index); // From service worker
  await writable.write(buffer);  // Writes directly to OS file system
}
await writable.close();
```

This streams each ~2-5MB segment buffer sequentially to disk — RAM usage stays constant regardless of total file size.

### Concurrency Engine
The service worker uses a dynamic semaphore pattern:
- A queue of segments is created up-front
- Up to N downloads run concurrently (configurable)
- Each segment has up to 3 automatic retries with exponential backoff
- A cancellation token allows clean job abort mid-flight

### Architecture
```
popup.html/popup.js
  └── Opens sidepanel

sidepanel.html/panel.js
  ├── Sends messages to background.js (START_JOB, CANCEL_JOB, GET_JOBS...)
  ├── Receives JOBS_UPDATED broadcasts
  ├── Renders segment map on <canvas>
  └── Streaming merge via File System Access API

background.js (Service Worker)
  ├── Manages jobs Map<jobId, JobState>
  ├── Concurrent fetch() engine with semaphore
  ├── Holds ArrayBuffers in memory until merge
  └── Broadcasts state updates to all views
```

---

## ⚠️ Known Limitations

| Limitation | Detail |
|------------|--------|
| **Memory** | All downloaded segment buffers are held in the service worker's memory until merged. For 4GB of data across 2000+ segments, this requires ~4GB RAM. |
| **Service Worker Lifecycle** | Chrome may idle/kill the service worker after 5 minutes of inactivity. Active downloads prevent this; but if Chrome restarts, in-progress jobs are lost. |
| **File System Access API** | Requires Chrome 86+. Not available in Firefox or Safari. |
| **CORS** | The extension has `<all_urls>` host permission, but some CDNs may still block cross-origin range requests. |

---

## 🛠️ Regenerating Icons

If you replace `source_icon.png`:
```powershell
cd chrome-extension
python generate_icons.py
```

---

## 🔄 Differences from the Python App

| Feature | Python App | Chrome Extension |
|---------|------------|-----------------|
| Download Engine | `aiohttp` + asyncio | `fetch()` + Service Worker |
| File Merging | `shutil.copyfileobj` (Python streams) | File System Access API streams |
| Max File Size | Disk limit | Disk limit (4GB) |
| UI | PyQt6 Desktop GUI | Chrome Side Panel |
| Thumbnail | FFmpeg extract | ❌ Not available |
| Standalone merge folder | ✅ | ❌ Not yet |
| Persistent cache (resume) | ✅ | ❌ (in-memory only) |
