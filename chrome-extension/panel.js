/**
 * Fast-Flux Chrome Extension - Panel UI Logic (panel.js) v2
 *
 * ARCHITECTURE:
 * - panelJobs (Map) is the single source of truth for all job state.
 * - Downloading happens HERE in the panel via fetch().
 * - ArrayBuffers are stored in panelJobs[id].buffers (Map<index, ArrayBuffer>).
 * - Merging reads directly from that local Map — ZERO IPC transfer needed.
 * - The service worker is only notified of lightweight status changes.
 */

'use strict';

// ============================================================
// Concurrency Semaphore
// ============================================================
class Semaphore {
  constructor(limit) {
    this.limit = limit;
    this._count = 0;
    this._queue = [];
  }
  acquire() {
    return new Promise(resolve => {
      if (this._count < this.limit) { this._count++; resolve(); }
      else { this._queue.push(resolve); }
    });
  }
  release() {
    this._count--;
    if (this._queue.length > 0) { this._count++; this._queue.shift()(); }
  }
}

// ============================================================
// Panel Job State (lives here — never sent to SW as buffers)
// ============================================================
class PanelJob {
  constructor(id, params) {
    this.id = id;
    this.filename    = params.filename;
    this.baseUrl     = params.baseUrl;
    this.startIndex  = params.startIndex;
    this.endIndex    = params.endIndex;
    this.padding     = params.padding || null;
    this.concurrency = Math.max(1, Math.min(params.concurrency || 20, 100));
    this.timeout     = params.timeout || 30000;
    this.total       = params.endIndex - params.startIndex + 1;

    // Per-segment metadata (no buffers here)
    this.segments = [];
    for (let i = params.startIndex; i <= params.endIndex; i++) {
      this.segments.push({ index: i, status: 'pending', size: 0, retries: 0, url: generateUrl(params.baseUrl, i, params.padding) });
    }

    // Buffers stored separately (large data)
    this.buffers = new Map(); // index -> ArrayBuffer

    this.status     = 'running';
    this.downloaded = 0;
    this.failed     = 0;
    this.startTime  = Date.now();
    this.cancelled  = false;
  }

  get speed() {
    const elapsed = (Date.now() - this.startTime) / 1000;
    return elapsed > 0 ? (this.downloaded / elapsed) : 0;
  }

  get eta() {
    const spd = this.speed;
    const remaining = this.total - this.downloaded - this.failed;
    return spd > 0 ? Math.round(remaining / spd) : 0;
  }

  get totalBytes() {
    return this.segments.reduce((s, seg) => s + (seg.size || 0), 0);
  }

  toSnapshot() {
    return {
      id:          this.id,
      filename:    this.filename,
      total:       this.total,
      downloaded:  this.downloaded,
      failed:      this.failed,
      status:      this.status,
      speed:       `${this.speed.toFixed(1)} seg/s`,
      eta:         this.eta > 0 ? `${this.eta}s` : '--',
      totalBytes:  this.totalBytes,
      hasBuffers:  this.buffers.size > 0,
      segments:    this.segments.map(s => ({ index: s.index, status: s.status, size: s.size, retries: s.retries })),
    };
  }
}

const panelJobs = new Map(); // jobId -> PanelJob (source of truth)
let config = {};
let mergeAbortFlag = false;

// ============================================================
// DOM Refs
// ============================================================
const $ = id => document.getElementById(id);
const jobsList        = $('jobsList');
const emptyState      = $('emptyState');
const urlStatus       = $('urlStatus');
const formBody        = $('formBody');
const formToggle      = $('formToggle');
const mergeOverlay    = $('mergeOverlay');
const settingsOverlay = $('settingsOverlay');
const jobsMeta        = $('jobsMeta');
const jobCardTemplate = $('jobCardTemplate');

// ============================================================
// Init
// ============================================================
document.addEventListener('DOMContentLoaded', async () => {
  await loadConfig();
  setupEventListeners();
  renderJobs(); // Start with empty state
});

// ============================================================
// Config
// ============================================================
async function loadConfig() {
  const res = await sendBg({ type: 'GET_CONFIG' });
  config = res.config || {};
  applyConfigToForm();
}

function applyConfigToForm() {
  $('concurrencyInput').value = config.maxConcurrent || 20;
  if (config.padding !== undefined) $('paddingSelect').value = config.padding || '';
  $('settingsConcurrency').value = config.maxConcurrent || 20;
  $('settingsTimeout').value     = config.timeout || 30000;
  $('settingsPadding').value     = config.padding || '';
}

async function saveConfig() {
  const c = {
    maxConcurrent: parseInt($('settingsConcurrency').value) || 20,
    timeout:       parseInt($('settingsTimeout').value) || 30000,
    padding:       $('settingsPadding').value || null,
  };
  await sendBg({ type: 'SAVE_CONFIG', config: c });
  config = c;
  hideSettings();
  showToast('Settings saved', 'success');
}

// ============================================================
// URL Generation
// ============================================================
function generateUrl(baseUrl, index, padding) {
  let idx = String(index);
  if (padding) idx = idx.padStart(padding.length, '0');
  return baseUrl.replace(/\[(index|i)\]/gi, idx);
}

// ============================================================
// Download Engine (runs in the panel)
// ============================================================
async function startPanelDownload(params) {
  const jobId = `${Date.now()}_${params.filename.replace(/\W/g, '_').slice(0, 30)}`;
  const job = new PanelJob(jobId, params);
  panelJobs.set(jobId, job);

  // Register with SW (lightweight metadata only — no buffers)
  sendBg({ type: 'CREATE_JOB', job: job.toSnapshot() }).catch(() => {});

  // Show card immediately
  renderJobs();

  // Start downloading asynchronously
  runPanelJob(jobId).catch(e => {
    const j = panelJobs.get(jobId);
    if (j) { j.status = 'failed'; j.error = e.message; renderJobs(); }
  });
}

async function runPanelJob(jobId) {
  const job = panelJobs.get(jobId);
  if (!job) return;

  const sem = new Semaphore(job.concurrency);
  const pending = job.segments.filter(s => s.status !== 'completed');

  // Throttled UI refresh (every 200ms)
  let lastRender = 0;
  const scheduleRender = () => {
    const now = Date.now();
    if (now - lastRender > 200) { lastRender = now; updateJobCard(jobId); }
  };

  // Progress timer
  const progressTimer = setInterval(() => updateJobCard(jobId), 300);

  await Promise.all(pending.map(async (seg) => {
    await sem.acquire();
    try {
      if (!job.cancelled) {
        await downloadSegmentInPanel(job, seg, 0);
        scheduleRender();
      }
    } finally {
      sem.release();
    }
  }));

  clearInterval(progressTimer);

  if (job.cancelled) {
    job.status = 'cancelled';
  } else {
    const failCount = job.segments.filter(s => s.status === 'failed').length;
    job.status = failCount === 0 ? 'completed' : 'failed';

    if (failCount === 0) {
      sendBg({ type: 'NOTIFY_COMPLETE', jobId: job.id, filename: job.filename }).catch(() => {});
    }
  }

  // Tell SW the final status (for popup stats)
  sendBg({ type: 'UPDATE_JOB', jobId: job.id, updates: { status: job.status, downloaded: job.downloaded, failed: job.failed } }).catch(() => {});

  renderJobs(); // Full re-render to show merge/retry buttons
}

async function downloadSegmentInPanel(job, seg, attempt) {
  if (job.cancelled) return;

  seg.status = 'downloading';

  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), job.timeout);

  try {
    const response = await fetch(seg.url, { signal: ctrl.signal });
    clearTimeout(timer);

    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const buffer = await response.arrayBuffer();
    clearTimeout(timer);

    seg.size   = buffer.byteLength;
    seg.status = 'completed';
    job.buffers.set(seg.index, buffer); // Store buffer locally in panel
    job.downloaded++;
  } catch (err) {
    clearTimeout(timer);

    if (err.name === 'AbortError' || job.cancelled) {
      seg.status = 'failed';
      return;
    }

    if (attempt < 3) {
      seg.status = 'pending';
      seg.retries = attempt + 1;
      await sleep(1500 * (attempt + 1));
      return downloadSegmentInPanel(job, seg, attempt + 1);
    }

    seg.status = 'failed';
    job.failed++;
  }
}

function cancelPanelJob(jobId) {
  const job = panelJobs.get(jobId);
  if (!job) return;
  job.cancelled = true;
  job.status = 'cancelled';
  sendBg({ type: 'UPDATE_JOB', jobId, updates: { status: 'cancelled' } }).catch(() => {});
  renderJobs();
}

async function retryFailedSegments(jobId) {
  const job = panelJobs.get(jobId);
  if (!job) return;

  job.segments.filter(s => s.status === 'failed').forEach(s => { s.status = 'pending'; s.retries = 0; });
  job.failed    = 0;
  job.cancelled = false;
  job.status    = 'running';
  renderJobs();

  await runPanelJob(jobId);
}

// ============================================================
// Merge — reads buffers directly from panel memory (no IPC!)
// ============================================================
async function startStreamingMerge(jobId) {
  const job = panelJobs.get(jobId);
  if (!job) { showToast('Job not found', 'error'); return; }

  const orderedSegments = job.segments
    .filter(s => s.status === 'completed')
    .sort((a, b) => a.index - b.index);

  if (orderedSegments.length === 0) {
    showToast('No completed segments to merge.', 'error');
    return;
  }

  // Check that buffers are actually in memory
  const missingBuffers = orderedSegments.filter(s => !job.buffers.has(s.index));
  if (missingBuffers.length > 0) {
    showToast(`${missingBuffers.length} segment buffer(s) missing from memory. Try re-downloading.`, 'error');
    return;
  }

  mergeAbortFlag = false;
  showMergeOverlay();
  setMergeStatus('Building output from memory...');
  setMergeFill(10);

  try {
    // Collect ordered ArrayBuffers directly from panel memory
    const blobParts = orderedSegments.map(s => job.buffers.get(s.index));
    const totalSize = blobParts.reduce((sum, buf) => sum + buf.byteLength, 0);

    setMergeStatus(`Creating blob (${formatBytes(totalSize)})...`);
    setMergeStats(`${orderedSegments.length} segments`);
    setMergeFill(40);

    // Yield to browser to keep UI alive before Blob allocation
    await sleep(10);

    const mimeType = getMimeType(job.filename);
    const blob = new Blob(blobParts, { type: mimeType });

    if (mergeAbortFlag) { hideMergeOverlay(); return; }

    setMergeStatus('Opening save dialog...');
    setMergeFill(70);

    // Try File System Access API first (if available in this context)
    if (typeof window.showSaveFilePicker === 'function') {
      try {
        const fileHandle = await window.showSaveFilePicker({
          suggestedName: job.filename,
          types: [{ description: 'Video / Media', accept: { 'video/*': ['.mp4', '.ts', '.mkv', '.avi', '.mov'], 'application/octet-stream': ['.*'] } }],
        });
        const writable = await fileHandle.createWritable();
        const CHUNK = 64 * 1024 * 1024; // 64 MB
        let offset = 0;
        setMergeStatus('Writing to disk...');
        while (offset < blob.size) {
          if (mergeAbortFlag) { await writable.abort(); hideMergeOverlay(); return; }
          await writable.write(blob.slice(offset, offset + CHUNK));
          offset += CHUNK;
          setMergeFill(70 + Math.round((Math.min(offset, blob.size) / blob.size) * 28));
          setMergeStats(`${formatBytes(Math.min(offset, blob.size))} / ${formatBytes(blob.size)}`);
          await sleep(0); // yield
        }
        await writable.close();
        setMergeFill(100);
        hideMergeOverlay();
        showToast(`✓ Saved: ${fileHandle.name}`, 'success');
        return;
      } catch (fsaErr) {
        if (fsaErr.name === 'AbortError') { hideMergeOverlay(); return; }
        console.warn('FSA picker unavailable, using downloads API:', fsaErr.name, '-', fsaErr.message);
      }
    }

    // Fallback: chrome.downloads API (reliable in all extension pages)
    setMergeStatus('Sending to Chrome download manager...');
    setMergeFill(85);

    const blobUrl = URL.createObjectURL(blob);
    await new Promise((resolve, reject) => {
      chrome.downloads.download(
        { url: blobUrl, filename: sanitizeFilename(job.filename), saveAs: true, conflictAction: 'uniquify' },
        (downloadId) => {
          URL.revokeObjectURL(blobUrl);
          if (chrome.runtime.lastError) {
            reject(new Error(chrome.runtime.lastError.message));
          } else if (downloadId === undefined) {
            reject(new Error('Download manager rejected the file'));
          } else {
            resolve(downloadId);
          }
        }
      );
    });

    setMergeFill(100);
    hideMergeOverlay();
    showToast(`✓ Download started: ${job.filename}`, 'success');

  } catch (e) {
    console.error('Merge error:', e);
    hideMergeOverlay();
    showToast(`Merge failed: ${e.message}`, 'error');
  }
}

// ============================================================
// Render Jobs
// ============================================================
function renderJobs() {
  const jobsArray = [...panelJobs.values()];

  // Remove orphaned cards
  jobsList.querySelectorAll('.job-card').forEach(card => {
    if (!panelJobs.has(card.dataset.jobId)) card.remove();
  });

  if (jobsArray.length === 0) {
    emptyState.classList.remove('hidden');
    jobsMeta.textContent = '';
    return;
  }

  emptyState.classList.add('hidden');

  const running   = jobsArray.filter(j => j.status === 'running').length;
  const completed = jobsArray.filter(j => j.status === 'completed').length;
  jobsMeta.textContent = `${running} running · ${completed} completed`;

  jobsArray.forEach(job => {
    let card = jobsList.querySelector(`[data-job-id="${job.id}"]`);
    if (!card) {
      card = createJobCard(job.id);
      jobsList.insertBefore(card, jobsList.firstChild);
    }
    updateJobCard(job.id, card);
  });
}

function createJobCard(jobId) {
  const node = jobCardTemplate.content.cloneNode(true);
  const card = node.querySelector('.job-card');
  card.dataset.jobId = jobId;

  card.querySelector('.job-cancel-btn').addEventListener('click', () => cancelPanelJob(jobId));
  card.querySelector('.retry-btn').addEventListener('click', () => retryFailedSegments(jobId));
  card.querySelector('.merge-btn').addEventListener('click', () => startStreamingMerge(jobId));
  card.querySelector('.remove-btn').addEventListener('click', () => {
    panelJobs.delete(jobId);
    sendBg({ type: 'REMOVE_JOB', jobId }).catch(() => {});
    card.remove();
    if (panelJobs.size === 0) emptyState.classList.remove('hidden');
    renderJobs();
  });

  return card;
}

function updateJobCard(jobId, card) {
  const job = panelJobs.get(jobId);
  if (!job) return;

  card = card || jobsList.querySelector(`[data-job-id="${jobId}"]`);
  if (!card) return;

  const downloadedPct = job.total > 0 ? Math.round((job.downloaded / job.total) * 100) : 0;

  card.className = `job-card ${job.status}`;
  card.querySelector('.job-name').textContent    = job.filename;
  const badge = card.querySelector('.job-badge');
  badge.textContent  = job.status.toUpperCase();
  badge.className    = `job-badge badge-${job.status}`;

  card.querySelector('.job-progress-fill').style.width    = `${downloadedPct}%`;
  card.querySelector('.job-progress-pct').textContent     = `${downloadedPct}%`;

  card.querySelector('.speed-stat').textContent = `${job.speed.toFixed(1)} seg/s`;
  card.querySelector('.eta-stat').textContent   = `ETA: ${job.eta > 0 ? job.eta + 's' : '--'}`;
  card.querySelector('.size-stat').textContent  = formatBytes(job.totalBytes);
  card.querySelector('.seg-stat').textContent   = `${job.downloaded} / ${job.total}`;

  card.querySelector('.job-cancel-btn').style.display = job.status === 'running' ? '' : 'none';

  const canMerge  = job.status === 'completed' && job.buffers.size > 0;
  const canRetry  = job.status === 'failed' && job.failed > 0;
  card.querySelector('.merge-btn').classList.toggle('hidden', !canMerge);
  card.querySelector('.retry-btn').classList.toggle('hidden', !canRetry);

  renderSegmentMap(card, job);
}

// ============================================================
// Segment Map (Canvas)
// ============================================================
function renderSegmentMap(card, job) {
  const canvas = card.querySelector('.segment-map');
  const total  = job.total || 0;
  if (total === 0) return;

  const SEG  = 6;
  const GAP  = 1;
  const W    = (card.offsetWidth || 400) - 24;
  const cols = Math.max(1, Math.floor((W + GAP) / (SEG + GAP)));
  const rows = Math.ceil(total / cols);
  const cW   = cols * (SEG + GAP) - GAP;
  const cH   = rows * (SEG + GAP) - GAP;

  const dpr = window.devicePixelRatio || 1;
  canvas.width  = cW * dpr;
  canvas.height = cH * dpr;
  canvas.style.width  = `${cW}px`;
  canvas.style.height = `${cH}px`;

  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);

  const colors = { pending: '#21262d', downloading: '#1f6b2e', completed: '#3fb950', failed: '#f85149' };

  job.segments.forEach((seg, i) => {
    const col = i % cols;
    const row = Math.floor(i / cols);
    const x = col * (SEG + GAP);
    const y = row * (SEG + GAP);
    ctx.fillStyle = colors[seg.status] || colors.pending;
    ctx.fillRect(x, y, SEG, SEG);
  });
}

// ============================================================
// Merge Overlay Helpers
// ============================================================
function showMergeOverlay() {
  mergeOverlay.classList.remove('hidden');
  setMergeStatus('Preparing...');
  setMergeFill(0);
  setMergeStats('');
  $('cancelMergeBtn').classList.remove('hidden');
}
function hideMergeOverlay() { mergeOverlay.classList.add('hidden'); }
function setMergeStatus(t)  { $('mergeStatus').textContent = t; }
function setMergeFill(pct)  { $('mergeFill').style.width = `${pct}%`; }
function setMergeStats(t)   { $('mergeStats').textContent = t; }

// ============================================================
// Settings
// ============================================================
function showSettings() { settingsOverlay.classList.remove('hidden'); }
function hideSettings() { settingsOverlay.classList.add('hidden'); }

// ============================================================
// Event Listeners
// ============================================================
function setupEventListeners() {
  formToggle.addEventListener('click', () => {
    formBody.classList.toggle('collapsed');
    formToggle.classList.toggle('collapsed');
  });

  $('testUrlBtn').addEventListener('click', testUrl);
  $('startJobBtn').addEventListener('click', startJob);
  $('settingsBtn').addEventListener('click', showSettings);
  $('closeSettingsBtn').addEventListener('click', hideSettings);
  $('saveSettingsBtn').addEventListener('click', saveConfig);
  $('clearHistoryBtn').addEventListener('click', clearHistory);
  $('cancelMergeBtn').addEventListener('click', () => { mergeAbortFlag = true; });

  [$('urlInput'), $('startInput'), $('endInput'), $('filenameInput')].forEach(input => {
    input.addEventListener('keydown', e => { if (e.key === 'Enter') startJob(); });
  });

  // SW broadcasts (for future multi-panel sync)
  chrome.runtime.onMessage.addListener((msg) => {
    if (msg.type === 'JOBS_UPDATED') renderJobs();
  });
}

// ============================================================
// Form Actions
// ============================================================
async function testUrl() {
  const baseUrl = $('urlInput').value.trim();
  const start   = parseInt($('startInput').value);
  const end     = parseInt($('endInput').value);
  const padding = $('paddingSelect').value || null;

  if (!baseUrl || isNaN(start) || isNaN(end)) {
    showUrlStatus('error', 'Please fill in URL, Start, and End.'); return;
  }

  const firstUrl = generateUrl(baseUrl, start, padding);
  const lastUrl  = generateUrl(baseUrl, end, padding);

  showUrlStatus('testing', 'Testing connectivity...', firstUrl, lastUrl);
  $('testUrlBtn').disabled = true;

  try {
    const res = await sendBg({ type: 'TEST_URL', firstUrl, lastUrl });
    const { first, last } = res;
    const ok  = first.ok && last.ok;
    const msg = [
      `First: ${first.ok ? '✓ OK' : '✗ ' + first.error}`,
      `Last: ${last.ok ? '✓ OK' : '✗ ' + last.error}`,
    ].join('\n');
    showUrlStatus(ok ? 'success' : 'error', msg, firstUrl, lastUrl);
  } catch (e) {
    showUrlStatus('error', 'Test failed: ' + e.message);
  } finally {
    $('testUrlBtn').disabled = false;
  }
}

async function startJob() {
  const baseUrl     = $('urlInput').value.trim();
  const start       = parseInt($('startInput').value);
  const end         = parseInt($('endInput').value);
  const padding     = $('paddingSelect').value || null;
  let   filename    = $('filenameInput').value.trim() || 'video.mp4';
  const concurrency = parseInt($('concurrencyInput').value) || 20;
  const timeout     = config.timeout || 30000;

  if (!baseUrl)              { showToast('Please enter a Base URL', 'error'); return; }
  if (isNaN(start) || isNaN(end)) { showToast('Invalid index values', 'error'); return; }
  if (start > end)           { showToast('Start must be ≤ End', 'error'); return; }
  if (!filename.includes('.')) filename += '.mp4';

  const count = end - start + 1;
  if (count > 50000 && !confirm(`This job has ${count.toLocaleString()} segments. Continue?`)) return;

  $('startJobBtn').disabled = true;

  try {
    await startPanelDownload({ baseUrl, startIndex: start, endIndex: end, filename, padding, concurrency, timeout });
    showToast('Job started!', 'success');
    // Clear inputs
    $('urlInput').value = $('startInput').value = $('endInput').value = $('filenameInput').value = '';
    urlStatus.classList.add('hidden');
  } catch (e) {
    showToast('Failed to start: ' + e.message, 'error');
  } finally {
    $('startJobBtn').disabled = false;
  }
}

function clearHistory() {
  [...panelJobs.entries()].forEach(([id, job]) => {
    if (['completed', 'failed', 'cancelled'].includes(job.status)) {
      panelJobs.delete(id);
      sendBg({ type: 'REMOVE_JOB', jobId: id }).catch(() => {});
      const card = jobsList.querySelector(`[data-job-id="${id}"]`);
      if (card) card.remove();
    }
  });
  if (panelJobs.size === 0) emptyState.classList.remove('hidden');
  jobsMeta.textContent = '';
}

// ============================================================
// URL Status Display
// ============================================================
function showUrlStatus(type, message, firstUrl, lastUrl) {
  urlStatus.className = `url-status ${type}`;
  urlStatus.classList.remove('hidden');
  urlStatus.innerHTML = '';
  message.split('\n').forEach(line => {
    const d = document.createElement('div');
    d.textContent = line;
    urlStatus.appendChild(d);
  });
  [firstUrl, lastUrl].filter(Boolean).forEach((u, i) => {
    if (i === 1 && u === firstUrl) return;
    const d = document.createElement('div');
    d.className  = 'url-line';
    d.textContent = `→ ${u}`;
    urlStatus.appendChild(d);
  });
}

// ============================================================
// Utilities
// ============================================================
function getMimeType(filename) {
  const ext = (filename.split('.').pop() || '').toLowerCase();
  return { mp4: 'video/mp4', ts: 'video/mp2t', mkv: 'video/x-matroska', avi: 'video/x-msvideo', mov: 'video/quicktime' }[ext] || 'application/octet-stream';
}

function sanitizeFilename(name) {
  return name.replace(/[\\/:*?"<>|]/g, '_').trim() || 'video.mp4';
}

function formatBytes(bytes) {
  if (!bytes || bytes === 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), 3);
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`;
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function sendBg(msg) {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage(msg, res => {
      if (chrome.runtime.lastError) reject(new Error(chrome.runtime.lastError.message));
      else resolve(res || {});
    });
  });
}

// ============================================================
// Toast Notifications
// ============================================================
let toastTimer;
function showToast(message, type = 'info') {
  let toast = document.querySelector('.ff-toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.className = 'ff-toast';
    Object.assign(toast.style, {
      position: 'fixed', bottom: '16px', left: '50%', transform: 'translateX(-50%)',
      padding: '10px 16px', borderRadius: '8px', fontSize: '13px', fontWeight: '500',
      fontFamily: "'Inter', sans-serif", zIndex: '9999', maxWidth: 'calc(100% - 32px)',
      textAlign: 'center', boxShadow: '0 4px 12px rgba(0,0,0,0.5)',
      transition: 'opacity 0.2s ease', pointerEvents: 'none',
    });
    document.body.appendChild(toast);
  }
  const c = {
    success: { bg: 'rgba(63,185,80,.15)',  border: 'rgba(63,185,80,.4)',  color: '#3fb950' },
    error:   { bg: 'rgba(248,81,73,.15)',  border: 'rgba(248,81,73,.4)', color: '#f85149' },
    warning: { bg: 'rgba(210,153,34,.15)', border: 'rgba(210,153,34,.4)',color: '#d29922' },
    info:    { bg: 'rgba(47,129,247,.15)', border: 'rgba(47,129,247,.4)',color: '#58a6ff' },
  }[type] || {};
  Object.assign(toast.style, { background: c.bg, border: `1px solid ${c.border}`, color: c.color, opacity: '1' });
  toast.textContent = message;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toast.style.opacity = '0'; setTimeout(() => toast.remove(), 250); }, 3500);
}
