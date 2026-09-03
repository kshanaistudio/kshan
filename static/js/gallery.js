// =========================================================
// KSHAN - RESULTS GALLERY, HIGHLIGHTS, FAVORITES & SHARING
// =========================================================

let searchResults = null;
let selectedPhotoIds = new Set();
let favoritePhotoIds = new Set(JSON.parse(localStorage.getItem("kshan_favorites") || "[]"));
let currentLightboxIdx = 0;
let currentTab = "all"; // "all" or "favorites"
let touchStartX = 0;
let touchEndX = 0;

document.addEventListener("DOMContentLoaded", () => {
  loadGalleryData();
  
  // Touch swipe support on lightbox
  const lightbox = document.getElementById("lightboxModal");
  if (lightbox) {
    lightbox.addEventListener("touchstart", (e) => {
      touchStartX = e.changedTouches[0].screenX;
    }, { passive: true });

    lightbox.addEventListener("touchend", (e) => {
      touchEndX = e.changedTouches[0].screenX;
      handleSwipe();
    }, { passive: true });
  }

  // Keyboard navigation for lightbox
  document.addEventListener("keydown", (e) => {
    const modal = document.getElementById("lightboxModal");
    if (modal && modal.style.display === "flex") {
      if (e.key === "ArrowLeft") prevLightboxPhoto();
      if (e.key === "ArrowRight") nextLightboxPhoto();
      if (e.key === "Escape") closeLightbox();
    }
  });
});

function handleSwipe() {
  const diff = touchEndX - touchStartX;
  if (Math.abs(diff) > 50) {
    if (diff > 0) {
      prevLightboxPhoto(); // Swiped right
    } else {
      nextLightboxPhoto(); // Swiped left
    }
  }
}

function loadGalleryData() {
  const rawData = sessionStorage.getItem("kshan_last_search_results");
  if (!rawData) {
    document.getElementById("noResultsBox").style.display = "block";
    return;
  }

  try {
    searchResults = JSON.parse(rawData);
    renderGallery();
  } catch (e) {
    document.getElementById("noResultsBox").style.display = "block";
  }
}

function getActivePhotos() {
  if (!searchResults || !searchResults.photos) return [];
  if (currentTab === "favorites") {
    return searchResults.photos.filter(p => {
      const pid = p.photo_id || p.id;
      return favoritePhotoIds.has(pid);
    });
  }
  return searchResults.photos;
}

function renderGallery() {
  const grid = document.getElementById("galleryGrid");
  const noResults = document.getElementById("noResultsBox");
  const headline = document.getElementById("resultsHeadline");
  const sub = document.getElementById("resultsSub");

  grid.innerHTML = "";
  const photos = getActivePhotos();

  if (photos.length === 0) {
    noResults.style.display = "block";
    if (currentTab === "favorites") {
      headline.textContent = "No Favorites Saved";
      sub.textContent = "Tap the heart (♡) on any photo to save your favorite moments.";
    } else if (searchResults.is_public_highlights) {
      headline.textContent = "Event Highlights";
      sub.textContent = `${searchResults.event_name} (${searchResults.event_code})`;
    } else {
      headline.textContent = "No Matches Found";
      sub.textContent = `Scanned face embeddings in event ${searchResults.event_code}`;
    }
    return;
  }

  noResults.style.display = "none";

  if (searchResults.is_public_highlights) {
    headline.innerHTML = `Event <span style="color: var(--gold); font-style: italic;">Highlights</span>`;
    sub.textContent = `${searchResults.event_name} (${searchResults.event_code}) &bull; ${photos.length} Photographs`;
  } else if (currentTab === "favorites") {
    headline.innerHTML = `Your <span style="color: var(--gold); font-style: italic;">Favorites</span> (${photos.length})`;
    sub.textContent = `${searchResults.event_name} (${searchResults.event_code})`;
  } else {
    headline.innerHTML = `We found <span style="color: var(--gold); font-style: italic;">${photos.length} moments</span> of you`;
    sub.textContent = `${searchResults.event_name} (${searchResults.event_code}) &bull; Ranked by match accuracy`;
  }

  photos.forEach((photo, idx) => {
    const pid = photo.photo_id || photo.id;
    const isFav = favoritePhotoIds.has(pid);
    const card = document.createElement("div");
    card.className = "gallery-item animate-fade-in";
    card.style.animationDelay = `${idx * 0.03}s`;

    card.innerHTML = `
      <div 
        class="card-select-checkbox ${selectedPhotoIds.has(pid) ? 'selected' : ''}" 
        id="check-${pid}" 
        onclick="event.stopPropagation(); togglePhotoSelection(${pid})"
      >
        <span style="color: #fff; font-size: 13px; font-weight: bold;">✓</span>
      </div>

      <!-- Favorite Heart Icon -->
      <button 
        onclick="event.stopPropagation(); toggleFavorite(${pid})" 
        title="Save to Favorites"
        style="position: absolute; top: 10px; right: 44px; z-index: 3; background: rgba(43,18,27,0.92); color: var(--gold); border: 1px solid var(--gold-border); border-radius: 6px; width: 26px; height: 26px; display: flex; align-items: center; justify-content: center; font-size: 13px; cursor: pointer;"
      >
        <span style="color: ${isFav ? 'var(--danger)' : 'var(--text-muted)'};">${isFav ? '❤️' : '♡'}</span>
      </button>

      <img src="${photo.thumbnail_url}" alt="${photo.original_filename}" loading="lazy">
      
      <div class="overlay">
        <span style="font-size: 11px; color: #FFFFFF; font-weight: 600; text-overflow: ellipsis; overflow: hidden; white-space: nowrap;">
          ${photo.original_filename}
        </span>
        <button class="btn-secondary btn-sm" style="align-self: flex-start; padding: 6px 12px; font-size: 10px; background: rgba(43,18,27,0.95);" onclick="event.stopPropagation(); openLightboxById(${pid})">
          Fullscreen ↗
        </button>
      </div>
    `;

    card.addEventListener("click", () => openLightboxById(pid));
    grid.appendChild(card);
  });
}

function setTab(tab) {
  currentTab = tab;
  document.querySelectorAll(".tab-btn").forEach(btn => btn.classList.remove("active"));
  document.getElementById(`tab-${tab}`)?.classList.add("active");
  renderGallery();
}

function toggleFavorite(photoId) {
  if (favoritePhotoIds.has(photoId)) {
    favoritePhotoIds.delete(photoId);
    showToast("Removed from favorites");
  } else {
    favoritePhotoIds.add(photoId);
    showToast("Saved to favorites ❤️", "success");
  }
  localStorage.setItem("kshan_favorites", JSON.stringify(Array.from(favoritePhotoIds)));
  renderGallery();
}

function togglePhotoSelection(photoId) {
  if (selectedPhotoIds.has(photoId)) {
    selectedPhotoIds.delete(photoId);
    document.getElementById(`check-${photoId}`)?.classList.remove("selected");
  } else {
    selectedPhotoIds.add(photoId);
    document.getElementById(`check-${photoId}`)?.classList.add("selected");
  }
  updateSelectionUI();
}

function toggleSelectAll() {
  const photos = getActivePhotos();
  if (photos.length === 0) return;

  const allSelected = selectedPhotoIds.size === photos.length;
  if (allSelected) {
    selectedPhotoIds.clear();
    document.querySelectorAll(".card-select-checkbox").forEach(el => el.classList.remove("selected"));
    document.getElementById("selectAllBtn").innerHTML = `<span>Select All</span>`;
  } else {
    selectedPhotoIds.clear();
    photos.forEach(p => selectedPhotoIds.add(p.photo_id || p.id));
    document.querySelectorAll(".card-select-checkbox").forEach(el => el.classList.add("selected"));
    document.getElementById("selectAllBtn").innerHTML = `<span>Deselect All</span>`;
  }
  updateSelectionUI();
}

function updateSelectionUI() {
  const count = selectedPhotoIds.size;
  document.getElementById("selectedCount").textContent = count;
  const downloadBtn = document.getElementById("downloadSelectedBtn");
  
  if (count > 0) {
    downloadBtn.disabled = false;
  } else {
    downloadBtn.disabled = true;
  }
}

function openLightboxById(photoId) {
  const photos = getActivePhotos();
  const idx = photos.findIndex(p => (p.photo_id || p.id) === photoId);
  if (idx !== -1) {
    currentLightboxIdx = idx;
    showLightboxPhoto();
  }
}

function showLightboxPhoto() {
  const photos = getActivePhotos();
  const photo = photos[currentLightboxIdx];
  if (!photo) return;

  const pid = photo.photo_id || photo.id;
  const isFav = favoritePhotoIds.has(pid);

  document.getElementById("lightboxImage").src = photo.original_url || photo.view_url || photo.thumbnail_url;
  document.getElementById("lightboxFilename").textContent = photo.original_filename;
  document.getElementById("lightboxDetails").textContent = photo.width && photo.height ? `${photo.width} × ${photo.height}px` : "";
  document.getElementById("lightboxIndexText").textContent = `PHOTO ${currentLightboxIdx + 1} OF ${photos.length}`;
  document.getElementById("lightboxDownloadBtn").href = photo.download_url || `/api/photos/${pid}/download/`;

  const favBtn = document.getElementById("lightboxFavBtn");
  if (favBtn) {
    favBtn.innerHTML = `<span>${isFav ? '❤️ Favorited' : '♡ Favorite'}</span>`;
    favBtn.onclick = () => {
      toggleFavorite(pid);
      showLightboxPhoto();
    };
  }

  document.getElementById("lightboxModal").style.display = "flex";
}

function prevLightboxPhoto() {
  const photos = getActivePhotos();
  if (photos.length === 0) return;
  currentLightboxIdx = (currentLightboxIdx - 1 + photos.length) % photos.length;
  showLightboxPhoto();
}

function nextLightboxPhoto() {
  const photos = getActivePhotos();
  if (photos.length === 0) return;
  currentLightboxIdx = (currentLightboxIdx + 1) % photos.length;
  showLightboxPhoto();
}

function closeLightbox(event) {
  if (event && event.target !== event.currentTarget && !event.target.classList.contains("modal-close-btn")) {
    return;
  }
  document.getElementById("lightboxModal").style.display = "none";
}

async function shareGallery() {
  const url = window.location.href;
  if (navigator.share) {
    try {
      await navigator.share({
        title: `Photos from ${searchResults?.event_name || 'KSHAN'}`,
        text: `Found my photos from ${searchResults?.event_name || 'Event'} on KSHAN!`,
        url: url
      });
    } catch (e) {
      // Ignored if cancelled
    }
  } else {
    navigator.clipboard.writeText(url);
    showToast("Gallery link copied to clipboard!", "success");
  }
}

async function downloadSelectedPhotos() {
  if (selectedPhotoIds.size === 0) return;

  const photoIds = Array.from(selectedPhotoIds);
  try {
    const res = await authFetch("/api/photos/download-batch/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ photo_ids: photoIds })
    });

    if (!res.ok) {
      alert("Batch download failed.");
      return;
    }

    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `kshan_photos_${photoIds.length}.zip`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
  } catch (err) {
    alert("Download network error: " + err.message);
  }
}
