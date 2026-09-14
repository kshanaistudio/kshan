// =========================================================
// KSHAN - ENTERPRISE HIGH-RES BULK UPLOADER & PROGRESS PIPELINE
// Supports Multi-Gigabyte Uploads (1GB+ / Thousands of Photos)
// =========================================================

let progressPollingInterval = null;
let isUploading = false;
let uploadAbortControllers = [];

function getUploadCsrfToken() {
  if (typeof getCookie === 'function') {
    const c = getCookie('csrftoken');
    if (c) return c;
  }
  const match = document.cookie.match(/csrftoken=([^;]+)/);
  if (match) return match[1];
  const input = document.querySelector('[name=csrfmiddlewaretoken]');
  if (input) return input.value;
  return window.CSRF_TOKEN || '';
}

function formatBytes(bytes, decimals = 1) {
  if (!bytes || bytes === 0) return '0 MB';
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

function minimizeUploadModal() {
  const modal = document.getElementById("uploadProgressModal");
  const widget = document.getElementById("bgUploadWidget");
  if (modal) modal.style.display = "none";
  if (widget && isUploading) widget.style.display = "block";
}

function restoreUploadModal() {
  const modal = document.getElementById("uploadProgressModal");
  const widget = document.getElementById("bgUploadWidget");
  if (widget) widget.style.display = "none";
  if (modal) modal.style.display = "flex";
}

function handleBulkFilesSelected(files) {
  if (!files || files.length === 0) return;
  uploadFilesInBatches(Array.from(files));
}

// Drag & drop support on admin bulk dropzone
const bulkDropzone = document.getElementById("bulkDropzone");
if (bulkDropzone) {
  ["dragenter", "dragover"].forEach(eventName => {
    bulkDropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      bulkDropzone.classList.add("dragover");
    });
  });

  ["dragleave", "drop"].forEach(eventName => {
    bulkDropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      bulkDropzone.classList.remove("dragover");
    });
  });

  bulkDropzone.addEventListener("drop", (e) => {
    const dt = e.dataTransfer;
    const files = dt.files;
    if (files && files.length > 0) {
      uploadFilesInBatches(Array.from(files));
    }
  });
}

/**
 * Enterprise Adaptive Batch Uploader
 * 1. Partitions files into safe batches (max 20MB or max 5 files per HTTP request)
 * 2. Runs up to 3 parallel concurrent upload streams
 * 3. Tracks real-time transferred bytes via XMLHttpRequest progress events
 * 4. Retries failed batches automatically with exponential backoff
 */
async function uploadFilesInBatches(files) {
  if (!files || files.length === 0) return;

  const eventIdentifier = window.EVENT_ID || window.CURRENT_EVENT_ID;
  if (!eventIdentifier) {
    if (typeof showToast === 'function') showToast("Error: No active event identifier found.", "danger");
    return;
  }

  isUploading = true;

  // UI elements
  const modal = document.getElementById("uploadProgressModal");
  const widget = document.getElementById("bgUploadWidget");
  const modalProgressBar = document.getElementById("modalUploadProgressBar");
  const modalPercent = document.getElementById("modalUploadPercent");
  const modalBytes = document.getElementById("modalUploadBytes");
  const modalSubtext = document.getElementById("modalUploadSubtext");
  const modalHeading = document.getElementById("modalUploadHeading");

  const bgProgressBar = document.getElementById("bgUploadProgressBar");
  const bgPercent = document.getElementById("bgUploadPercent");
  const bgBytes = document.getElementById("bgUploadBytes");

  const statusBox = document.getElementById("uploadStatusBox");
  const statusText = document.getElementById("uploadStatusText");

  if (modal) modal.style.display = "flex";
  if (statusBox) statusBox.style.display = "block";
  if (modalHeading) modalHeading.textContent = "Uploading Event Photos";

  const totalFiles = files.length;
  let totalBytes = 0;
  files.forEach(f => { totalBytes += (f.size || 0); });

  const formattedTotalBytes = formatBytes(totalBytes);

  // 1. Partition files into size-capped adaptive chunks (max 20 MB or 5 files per chunk)
  const MAX_CHUNK_BYTES = 20 * 1024 * 1024; // 20 MB
  const MAX_CHUNK_FILES = 5;

  const chunks = [];
  let currentChunk = [];
  let currentChunkBytes = 0;

  for (const file of files) {
    if (currentChunk.length >= MAX_CHUNK_FILES || (currentChunkBytes + file.size > MAX_CHUNK_BYTES && currentChunk.length > 0)) {
      chunks.push({ id: chunks.length, files: currentChunk, bytes: currentChunkBytes });
      currentChunk = [];
      currentChunkBytes = 0;
    }
    currentChunk.push(file);
    currentChunkBytes += (file.size || 0);
  }
  if (currentChunk.length > 0) {
    chunks.push({ id: chunks.length, files: currentChunk, bytes: currentChunkBytes });
  }

  // Progress tracking map (bytes uploaded per chunk)
  const chunkLoadedBytes = new Array(chunks.length).fill(0);
  let totalUploadedPhotos = 0;
  let totalSkippedPhotos = 0;
  let uploadedFilesCount = 0;

  function updateUiProgress() {
    let transferredBytes = chunkLoadedBytes.reduce((acc, val) => acc + val, 0);
    if (transferredBytes > totalBytes) transferredBytes = totalBytes;

    const percent = totalBytes > 0 ? Math.min(100, Math.round((transferredBytes / totalBytes) * 100)) : 0;
    const formattedTransferred = formatBytes(transferredBytes);

    if (modalProgressBar) modalProgressBar.style.width = `${percent}%`;
    if (modalPercent) modalPercent.textContent = `${percent}%`;
    if (modalBytes) modalBytes.textContent = `${formattedTransferred} / ${formattedTotalBytes}`;
    if (modalSubtext) {
      modalSubtext.textContent = `Uploading photo ${uploadedFilesCount} of ${totalFiles} (${chunks.length} batches total)... Please keep this tab open.`;
    }

    if (bgProgressBar) bgProgressBar.style.width = `${percent}%`;
    if (bgPercent) bgPercent.textContent = `${percent}%`;
    if (bgBytes) bgBytes.textContent = `${formattedTransferred} / ${formattedTotalBytes}`;

    if (statusText) {
      statusText.textContent = `Uploading: ${percent}% (${uploadedFilesCount}/${totalFiles} photos, ${formattedTransferred} of ${formattedTotalBytes})`;
    }
  }

  updateUiProgress();

  // Helper function to upload one chunk with XMLHttpRequest & retries
  function uploadChunkWithRetry(chunk, maxRetries = 3) {
    return new Promise((resolve, reject) => {
      let attempts = 0;

      function attemptUpload() {
        attempts++;
        const formData = new FormData();
        chunk.files.forEach(f => formData.append("files", f));

        const xhr = new XMLHttpRequest();
        xhr.open("POST", `/api/events/${eventIdentifier}/photos/`, true);

        const csrfToken = getUploadCsrfToken();
        if (csrfToken) {
          xhr.setRequestHeader("X-CSRFToken", csrfToken);
        }

        xhr.upload.onprogress = (e) => {
          if (e.lengthComputable) {
            chunkLoadedBytes[chunk.id] = Math.min(e.loaded, chunk.bytes);
            updateUiProgress();
          }
        };

        xhr.onload = () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            try {
              const resData = JSON.parse(xhr.responseText);
              chunkLoadedBytes[chunk.id] = chunk.bytes; // Complete
              totalUploadedPhotos += (resData.uploaded_count || chunk.files.length);
              totalSkippedPhotos += (resData.skipped_count || 0);
              uploadedFilesCount += chunk.files.length;
              updateUiProgress();
              resolve(resData);
            } catch (err) {
              resolve({ ok: true, uploaded_count: chunk.files.length });
            }
          } else {
            if (attempts < maxRetries) {
              console.warn(`Chunk ${chunk.id + 1} failed with status ${xhr.status}. Retrying (${attempts}/${maxRetries})...`);
              setTimeout(attemptUpload, 1200 * attempts);
            } else {
              reject(new Error(`Chunk upload failed with HTTP ${xhr.status}: ${xhr.statusText}`));
            }
          }
        };

        xhr.onerror = () => {
          if (attempts < maxRetries) {
            console.warn(`Chunk ${chunk.id + 1} network error. Retrying (${attempts}/${maxRetries})...`);
            setTimeout(attemptUpload, 1500 * attempts);
          } else {
            reject(new Error(`Network error uploading chunk ${chunk.id + 1}`));
          }
        };

        xhr.ontimeout = () => {
          if (attempts < maxRetries) {
            console.warn(`Chunk ${chunk.id + 1} timed out. Retrying (${attempts}/${maxRetries})...`);
            setTimeout(attemptUpload, 1500 * attempts);
          } else {
            reject(new Error(`Timeout uploading chunk ${chunk.id + 1}`));
          }
        };

        xhr.timeout = 180000; // 3 minutes timeout per 20MB chunk
        xhr.send(formData);
      }

      attemptUpload();
    });
  }

  // 2. Parallel Worker Pool (3 Concurrent Upload Streams)
  const CONCURRENCY = 3;
  let chunkIndex = 0;
  const chunkErrors = [];

  async function worker() {
    while (chunkIndex < chunks.length) {
      const idx = chunkIndex++;
      try {
        await uploadChunkWithRetry(chunks[idx]);
      } catch (err) {
        console.error(`Error in chunk ${idx + 1}:`, err);
        chunkErrors.push(`Batch ${idx + 1}: ${err.message}`);
      }
    }
  }

  const workers = [];
  for (let w = 0; w < Math.min(CONCURRENCY, chunks.length); w++) {
    workers.push(worker());
  }

  await Promise.all(workers);

  isUploading = false;

  // Final UI Update
  if (modalProgressBar) modalProgressBar.style.width = "100%";
  if (modalPercent) modalPercent.textContent = "100%";
  if (modalBytes) modalBytes.textContent = `${formattedTotalBytes} / ${formattedTotalBytes}`;

  if (chunkErrors.length === 0) {
    if (modalHeading) modalHeading.textContent = "Upload Complete! ✨";
    if (modalSubtext) {
      modalSubtext.innerHTML = `Successfully uploaded <strong>${totalUploadedPhotos}</strong> photos (${formattedTotalBytes}). AI facial recognition & indexing is running in the background.`;
    }
    if (statusText) {
      statusText.textContent = `Upload complete! ${totalUploadedPhotos} photos added. AI Face Recognition in progress.`;
    }
    if (typeof showToast === 'function') {
      showToast(`Upload complete! ${totalUploadedPhotos} photos uploaded (${formattedTotalBytes})`, "success");
    }
  } else {
    if (modalHeading) modalHeading.textContent = "Upload Finished with Warnings";
    if (modalSubtext) {
      modalSubtext.textContent = `Uploaded ${totalUploadedPhotos} photos with ${chunkErrors.length} batch warning(s).`;
    }
    if (typeof showToast === 'function') {
      showToast(`Uploaded ${totalUploadedPhotos} photos with some warnings.`, "warning");
    }
  }

  // Hide floating widget if active
  if (widget) widget.style.display = "none";

  // Auto-close modal after 2.5s and start AI progress polling
  setTimeout(() => {
    if (modal) modal.style.display = "none";
  }, 2500);

  // Start polling live processing progress
  startProgressPolling();
}

function startProgressPolling() {
  if (progressPollingInterval) clearInterval(progressPollingInterval);

  updateProgressOnce();
  progressPollingInterval = setInterval(updateProgressOnce, 2000);
}

async function updateProgressOnce() {
  try {
    const eventIdentifier = window.EVENT_ID || window.CURRENT_EVENT_ID;
    if (!eventIdentifier) return;

    const res = await fetch(`/api/admin/events/${eventIdentifier}/progress/`);
    if (!res.ok) return;

    const data = await res.json();
    const pct = data.percentage || 0;

    const pText = document.getElementById("processingPercentText");
    const pBar = document.getElementById("processingProgressBar");
    if (pText) pText.textContent = `${pct}%`;
    if (pBar) pBar.style.width = `${pct}%`;

    const progTotal = document.getElementById("progTotal");
    const progCompleted = document.getElementById("progCompleted");
    const progPending = document.getElementById("progPending");
    const progFaces = document.getElementById("progFaces");
    const progFailed = document.getElementById("progFailed");

    if (progTotal) progTotal.textContent = data.total || 0;
    if (progCompleted) progCompleted.textContent = data.completed || 0;
    if (progPending) progPending.textContent = (data.pending || 0) + (data.processing || 0);
    if (progFaces) progFaces.textContent = data.faces_detected || 0;
    if (progFailed) progFailed.textContent = data.failed || 0;

    if (data.is_complete && data.total > 0) {
      clearInterval(progressPollingInterval);
      progressPollingInterval = null;
      if (typeof showToast === 'function') {
        showToast("All photos processed and face embeddings indexed!", "success");
      }
      setTimeout(() => window.location.reload(), 1500);
    }
  } catch (err) {
    console.error("Progress poll error:", err);
  }
}

async function reprocessFailedPhotos() {
  try {
    const eventIdentifier = window.EVENT_ID || window.CURRENT_EVENT_ID;
    const res = await fetch(`/api/admin/events/${eventIdentifier}/reprocess-failed/`, {
      method: "POST",
      headers: {
        'X-CSRFToken': getUploadCsrfToken()
      }
    });
    const data = await res.json();
    if (typeof showToast === 'function') showToast(data.message || "Reprocessing queued", "info");
    startProgressPolling();
  } catch (err) {
    if (typeof showToast === 'function') showToast("Error triggering reprocessing", "danger");
  }
}

async function reprocessAllPhotos() {
  if (!confirm("Re-index all event photos with the state-of-the-art ResNet-50 ArcFace AI model for maximum precision?")) return;

  try {
    const eventIdentifier = window.EVENT_ID || window.CURRENT_EVENT_ID;
    const res = await fetch(`/api/admin/events/${eventIdentifier}/reprocess-all/`, {
      method: "POST",
      headers: {
        'X-CSRFToken': getUploadCsrfToken()
      }
    });
    const data = await res.json();
    if (typeof showToast === 'function') showToast(data.message || "Re-indexing started", "info");
    startProgressPolling();
  } catch (err) {
    if (typeof showToast === 'function') showToast("Error triggering re-indexing", "danger");
  }
}

async function deletePhoto(photoId) {
  if (!confirm("Are you sure you want to delete this photo and its detected face embeddings?")) return;

  try {
    const res = await fetch(`/api/admin/photos/${photoId}/`, { 
      method: "DELETE",
      headers: {
        'X-CSRFToken': getUploadCsrfToken()
      }
    });
    if (res.ok) {
      if (typeof showToast === 'function') showToast("Photo deleted", "success");
      setTimeout(() => window.location.reload(), 400);
    } else {
      if (typeof showToast === 'function') showToast("Failed to delete photo", "danger");
    }
  } catch (err) {
    if (typeof showToast === 'function') showToast("Network error deleting photo", "danger");
  }
}

// Check initial progress status on page load
document.addEventListener("DOMContentLoaded", () => {
  if (window.EVENT_ID || window.CURRENT_EVENT_ID) {
    startProgressPolling();
  }
});
