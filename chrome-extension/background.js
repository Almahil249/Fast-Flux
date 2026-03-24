/**
 * Fast-Flux Chrome Extension - Service Worker (background.js)
 * 
 * ARCHITECTURE (v2):
 * - This file is a lightweight coordinator: config, notifications,
 *   job-metadata broadcasting to popup / other views.
 */

// ============================================================
// State (metadata only — NO buffers)
// ============================================================
const jobRegistry = new Map(); // jobId -> lightweight metadata

// ============================================================
// Message Router
// ============================================================
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  handleMessage(msg, sender, sendResponse);
  return true; // Keep async response channel open
});

async function handleMessage(msg, sender, sendResponse) {
  try {
    switch (msg.type) {

      // Panel registers a new job (sends metadata only)
      case 'CREATE_JOB':
        jobRegistry.set(msg.job.id, msg.job);
        broadcast({ type: 'JOBS_UPDATED', jobs: getRegistrySnapshot() });
        sendResponse({ ok: true });
        break;

      // Panel pushes status/progress updates
      case 'UPDATE_JOB': {
        const job = jobRegistry.get(msg.jobId);
        if (job) Object.assign(job, msg.updates);
        broadcast({ type: 'JOBS_UPDATED', jobs: getRegistrySnapshot() });
        sendResponse({ ok: true });
        break;
      }

      // Panel removes a finished or cleared job
      case 'REMOVE_JOB':
        jobRegistry.delete(msg.jobId);
        broadcast({ type: 'JOBS_UPDATED', jobs: getRegistrySnapshot() });
        sendResponse({ ok: true });
        break;

      // Popup queries lightweight stats
      case 'GET_JOBS':
        sendResponse({ jobs: getRegistrySnapshot() });
        break;

      case 'GET_CONFIG':
        sendResponse({ config: await getConfig() });
        break;

      case 'SAVE_CONFIG':
        await saveConfig(msg.config);
        sendResponse({ ok: true });
        break;

      case 'TEST_URL': {
        const result = await testConnectivity(msg.firstUrl, msg.lastUrl);
        sendResponse(result);
        break;
      }

      // Panel asks SW to fire a desktop notification
      case 'NOTIFY_COMPLETE':
        chrome.notifications.create(`ff_done_${msg.jobId}`, {
          type: 'basic',
          iconUrl: 'icons/icon48.png',
          title: 'Fast-Flux: Download Complete!',
          message: `"${msg.filename}" is ready to save.`,
        });
        sendResponse({ ok: true });
        break;

      default:
        sendResponse({ ok: false, error: `Unknown message: ${msg.type}` });
    }
  } catch (e) {
    console.error('SW handleMessage error:', e);
    sendResponse({ ok: false, error: e.message });
  }
}

// ============================================================
// Config
// ============================================================
async function getConfig() {
  const result = await chrome.storage.local.get('ffConfig');
  return result.ffConfig || {
    maxConcurrent: 20,
    padding: null,
    timeout: 30000,
  };
}

async function saveConfig(config) {
  await chrome.storage.local.set({ ffConfig: config });
}

// ============================================================
// URL Connectivity Test
// ============================================================
async function testConnectivity(firstUrl, lastUrl) {
  async function checkUrl(url) {
    async function tryMethod(method) {
      const ctrl = new AbortController();
      const t = setTimeout(() => ctrl.abort(), 10000);
      try {
        const res = await fetch(url, { method, signal: ctrl.signal });
        clearTimeout(t);
        return { status: res.status, ok: res.ok, error: res.ok ? '' : `HTTP ${res.status}` };
      } catch (e) {
        clearTimeout(t);
        throw e;
      }
    }
    try {
      return await tryMethod('HEAD');
    } catch (_) {
      try {
        return await tryMethod('GET');
      } catch (e2) {
        return { status: 0, ok: false, error: e2.name === 'AbortError' ? 'Timeout' : e2.message.slice(0, 60) };
      }
    }
  }
  const [first, last] = await Promise.all([checkUrl(firstUrl), checkUrl(lastUrl)]);
  return { first, last };
}

// ============================================================
// Registry snapshot (for popup stats)
// ============================================================
function getRegistrySnapshot() {
  return [...jobRegistry.values()];
}

// ============================================================
// Broadcast to all extension views
// ============================================================
function broadcast(msg) {
  chrome.runtime.sendMessage(msg).catch(() => { });
}
