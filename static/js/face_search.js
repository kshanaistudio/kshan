// =========================================================
// KSHAN - USER SELFIE & FACE SEARCH LOGIC
// =========================================================

let selectedSelfieFile = null;
let webcamStream = null;
let capturedBase64Image = null;

function triggerFileInput() {
  document.getElementById("selfieFileInput").click();
}

function handleSelfieFileSelect(file) {
  if (!file) return;

  selectedSelfieFile = file;
  capturedBase64Image = null;

  const reader = new FileReader();
  reader.onload = (e) => {
    document.getElementById("selfiePreview").src = e.target.result;
    document.getElementById("previewFilename").textContent = file.name;
    document.getElementById("previewContainer").style.display = "block";
    document.getElementById("dropzoneContent").style.display = "none";
    document.getElementById("searchBtn").disabled = false;
  };
  reader.readAsDataURL(file);
}

// Drag & drop support on dropzone
const dropzone = document.getElementById("selfieDropzone");
if (dropzone) {
  ["dragenter", "dragover"].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.add("dragover");
    });
  });

  ["dragleave", "drop"].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.remove("dragover");
    });
  });

  dropzone.addEventListener("drop", (e) => {
    const dt = e.dataTransfer;
    const files = dt.files;
    if (files && files.length > 0) {
      handleSelfieFileSelect(files[0]);
    }
  });
}

// ================= WEBCAM CAPTURE =================
async function openCameraModal() {
  const modal = document.getElementById("cameraModal");
  const video = document.getElementById("webcamVideo");
  modal.classList.add("active");

  try {
    webcamStream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "user", width: { ideal: 1280 }, height: { ideal: 960 } },
      audio: false
    });
    video.srcObject = webcamStream;
  } catch (err) {
    showToast("Camera access denied or not available: " + err.message, "danger");
    closeCameraModal();
  }
}

function closeCameraModal() {
  const modal = document.getElementById("cameraModal");
  modal.classList.remove("active");

  if (webcamStream) {
    webcamStream.getTracks().forEach(track => track.stop());
    webcamStream = null;
  }
}

function captureWebcamPhoto() {
  const video = document.getElementById("webcamVideo");
  const canvas = document.getElementById("cameraCanvas");
  if (!video || !canvas) return;

  canvas.width = video.videoWidth || 640;
  canvas.height = video.videoHeight || 480;
  const ctx = canvas.getContext("2d");
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

  capturedBase64Image = canvas.toDataURL("image/jpeg", 0.95);
  selectedSelfieFile = null;

  document.getElementById("selfiePreview").src = capturedBase64Image;
  document.getElementById("previewFilename").textContent = "Camera Selfie Snap";
  document.getElementById("previewContainer").style.display = "block";
  document.getElementById("dropzoneContent").style.display = "none";
  document.getElementById("searchBtn").disabled = false;

  closeCameraModal();
}

// ================= SEARCH EXECUTION =================
async function performFaceSearch() {
  if (!selectedSelfieFile && !capturedBase64Image) {
    showToast("Please upload or capture a selfie first", "warning");
    return;
  }

  const searchBtn = document.getElementById("searchBtn");
  const searchLoading = document.getElementById("searchLoading");

  searchBtn.disabled = true;
  searchLoading.style.display = "block";

  const formData = new FormData();
  if (selectedSelfieFile) {
    formData.append("file", selectedSelfieFile);
  } else if (capturedBase64Image) {
    formData.append("image_base64", capturedBase64Image);
  }

  try {
    const res = await fetch(`/api/events/${window.CURRENT_EVENT_ID}/search-face`, {
      method: "POST",
      body: formData
    });

    const data = await res.json();
    searchLoading.style.display = "none";
    searchBtn.disabled = false;

    if (res.ok) {
      // Save search results in sessionStorage and redirect to gallery view
      sessionStorage.setItem("kshan_last_search_results", JSON.stringify(data));
      window.location.href = `/event/${window.CURRENT_EVENT_CODE}/gallery`;
    } else {
      const errorMsg = data.detail || "Error searching face";
      showToast(errorMsg, "danger");
    }
  } catch (err) {
    searchLoading.style.display = "none";
    searchBtn.disabled = false;
    showToast("Face search request failed: " + err.message, "danger");
  }
}
