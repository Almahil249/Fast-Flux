/**
 * Fast-Flux popup.js
 * Shows quick stats and opens the side panel.
 */
document.addEventListener('DOMContentLoaded', async () => {
  // Load quick stats
  try {
    const res = await sendBg({ type: 'GET_JOBS' });
    const jobs = res.jobs || [];

    document.getElementById('statActive').textContent =
      jobs.filter(j => j.status === 'running').length;
    document.getElementById('statCompleted').textContent =
      jobs.filter(j => j.status === 'completed').length;
    document.getElementById('statFailed').textContent =
      jobs.filter(j => j.status === 'failed').length;
  } catch (e) {
    console.warn('Could not load stats:', e);
  }

  // Open side panel button
  document.getElementById('openPanelBtn').addEventListener('click', () => {
    // Open the side panel
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (tabs[0]) {
        chrome.sidePanel.open({ tabId: tabs[0].id }).catch(() => {
          // Fallback: open as a tab
          chrome.tabs.create({ url: chrome.runtime.getURL('sidepanel.html') });
        });
      }
    });
    window.close();
  });
});

function sendBg(msg) {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage(msg, (res) => {
      if (chrome.runtime.lastError) {
        reject(new Error(chrome.runtime.lastError.message));
      } else {
        resolve(res || {});
      }
    });
  });
}
