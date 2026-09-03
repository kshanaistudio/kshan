// =========================================================
// KSHAN - ADMIN BULK UPLOADER & LIVE PROGRESS
// =========================================================

let progressPollingInterval = null;

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

async function uploadFilesInBatches(files) {
  const statusBox = document.getElementById("uploadStatusBox");
  const statusText = document.getElementById("uploadStatusText");
  statusBox.style.display = "block";

  const totalFiles = files.length;
  const BATCH_SIZE = 25;
  let totalUploaded = 0;
  let totalSkipped = 0;

  for (let i = 0; i < totalFiles; i += BATCH_SIZE) {
    const batch = files.slice(i, i + BATCH_SIZE);
    const formData = new FormData();
    batch.forEach(f => formData.append("files", f));

    statusText.textContent = `Uploading photos ${i + 1} to ${Math.min(i + BATCH_SIZE, totalFiles)} of ${totalFiles}...`;

      const eventIdentifier = window.EVENT_ID || window.CURRENT_EVENT_ID;
      const res = await fetch(`/api/events/${eventIdentifier}/photos/`, {
        method: "POST",
        headers: {
          'X-CSRFToken': getCsrfToken ? getCsrfToken() : ''
        },
        body: formData
      });

      if (res.ok) {
        const data = await res.json();
        totalUploaded += data.uploaded_count;
        totalSkipped += data.skipped_count;
      } else {
        showToast(`Batch upload error: ${res.statusText}`, "danger");
      }
    } catch (err) {
      showToast(`Network error during batch upload: ${err.message}`, "danger");
    }
  }

  statusText.textContent = `Upload complete! ${totalUploaded} new photos uploaded, ${totalSkipped} duplicates skipped. Background face extraction in progress.`;
  showToast(`Upload complete (${totalUploaded} added)`, "success");

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
    const res = await fetch(`/api/admin/events/${window.CURRENT_EVENT_ID}/progress`);
    if (!res.ok) return;

    const data = await res.json();
    document.getElementById("processingPercentText").textContent = `${data.percentage}%`;
    document.getElementById("processingProgressBar").style.width = `${data.percentage}%`;
    
    document.getElementById("progTotal").textContent = data.total;
    document.getElementById("progCompleted").textContent = data.completed;
    document.getElementById("progPending").textContent = data.pending + data.processing;
    document.getElementById("progFaces").textContent = data.faces_detected;
    document.getElementById("progFailed").textContent = data.failed;

    if (data.is_complete && data.total > 0) {
      clearInterval(progressPollingInterval);
      progressPollingInterval = null;
      // Reload photos grid after processing completes
      setTimeout(() => window.location.reload(), 1500);
    }
  } catch (err) {
    console.error("Progress poll error:", err);
  }
}

async function reprocessFailedPhotos() {
  try {
    const res = await fetch(`/api/admin/events/${window.CURRENT_EVENT_ID}/reprocess-failed`, {
      method: "POST"
    });
    const data = await res.json();
    showToast(data.message, "info");
    startProgressPolling();
  } catch (err) {
    showToast("Error triggering reprocessing", "danger");
  }
}

async function reprocessAllPhotos() {
  if (!confirm("Re-index all event photos with the state-of-the-art ResNet-50 ArcFace AI model for maximum precision?")) return;

  try {
    const res = await fetch(`/api/admin/events/${window.CURRENT_EVENT_ID}/reprocess-all`, {
      method: "POST"
    });
    const data = await res.json();
    showToast(data.message, "info");
    startProgressPolling();
  } catch (err) {
    showToast("Error triggering re-indexing", "danger");
  }
}

async function deletePhoto(photoId) {
  if (!confirm("Are you sure you want to delete this photo and its detected face embeddings?")) return;

  try {
    const res = await fetch(`/api/admin/photos/${photoId}`, { method: "DELETE" });
    if (res.ok) {
      showToast("Photo deleted", "success");
      setTimeout(() => window.location.reload(), 400);
    } else {
      showToast("Failed to delete photo", "danger");
    }
  } catch (err) {
    showToast("Network error deleting photo", "danger");
  }
}

// Check initial progress status on page load
document.addEventListener("DOMContentLoaded", () => {
  if (window.CURRENT_EVENT_ID) {
    startProgressPolling();
  }
});
