/**
 * FaceShare Photo Indexer
 * Manages the Host's local trip photos in browser RAM without server uploads.
 * - Generates fast WebP thumbnails
 * - Extracts face vectors in low-memory batches
 * - Compares participant face embeddings against indexed photos
 * - Handles duplicate detection & object URL disposal
 */

class PhotoIndexer {
  constructor() {
    this.photos = new Map(); // photoId -> { id, file, name, size, thumbUrl, thumbBlob, faces: [], scanned: false }
    this.duplicateSet = new Set(); // hash signature
    this.matchThreshold = 0.60;
  }

  setMatchThreshold(val) {
    this.matchThreshold = parseFloat(val);
  }

  async addFiles(fileList, onProgress) {
    const supportedTypes = ['image/jpeg', 'image/png', 'image/webp', 'image/heic', 'image/heif'];
    const validFiles = Array.from(fileList).filter(f => {
      const ext = '.' + f.name.split('.').pop().toLowerCase();
      return supportedTypes.includes(f.type) || ['.jpg', '.jpeg', '.png', '.webp', '.heic'].includes(ext);
    });

    const total = validFiles.length;
    let processed = 0;

    for (const file of validFiles) {
      const sig = `${file.name}_${file.size}_${file.lastModified}`;
      if (this.duplicateSet.has(sig)) {
        continue;
      }
      this.duplicateSet.add(sig);

      const id = 'ph_' + Math.random().toString(36).substring(2, 10);
      
      // Generate thumbnail
      const thumb = await this.createThumbnail(file);

      const item = {
        id,
        file,
        name: file.name,
        size: file.size,
        type: file.type || 'image/jpeg',
        thumbBlob: thumb.blob,
        thumbUrl: thumb.url,
        faces: [],
        scanned: false,
        faceCount: 0
      };

      this.photos.set(id, item);
      processed++;
      if (onProgress) {
        onProgress({ stage: 'preparing', current: processed, total });
      }
    }

    return Array.from(this.photos.values());
  }

  async createThumbnail(file, maxDim = 320) {
    return new Promise((resolve) => {
      const img = new Image();
      const url = URL.createObjectURL(file);
      img.onload = () => {
        let w = img.naturalWidth || img.width;
        let h = img.naturalHeight || img.height;
        const scale = maxDim / Math.max(w, h);
        if (scale < 1) {
          w = Math.round(w * scale);
          h = Math.round(h * scale);
        }

        const canvas = document.createElement('canvas');
        canvas.width = w;
        canvas.height = h;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(img, 0, 0, w, h);
        URL.revokeObjectURL(url);

        canvas.toBlob((blob) => {
          const thumbUrl = URL.createObjectURL(blob);
          resolve({ blob, url: thumbUrl });
        }, 'image/webp', 0.82);
      };
      img.onerror = () => {
        URL.revokeObjectURL(url);
        resolve({ blob: null, url: '' });
      };
      img.src = url;
    });
  }

  /**
   * Scan photos in small memory-safe batches
   */
  async scanAllFaces(onProgress) {
    const list = Array.from(this.photos.values()).filter(p => !p.scanned);
    const total = list.length;
    let completed = 0;
    let totalFacesDetected = 0;

    for (const item of list) {
      try {
        const canvas = await window.faceEngine.getProcessedCanvas(item.file, 1024);
        const faces = await window.faceEngine.extractFaces(canvas);
        
        item.faces = faces;
        item.faceCount = faces.length;
        item.scanned = true;
        totalFacesDetected += faces.length;

        // Cooperative garbage collection release
        canvas.width = 1;
        canvas.height = 1;
      } catch (err) {
        console.warn(`[PhotoIndexer] Face detection error on ${item.name}:`, err);
        item.scanned = true;
        item.faces = [];
      }

      completed++;
      if (onProgress) {
        onProgress({
          stage: 'scanning',
          current: completed,
          total,
          totalFaces: totalFacesDetected,
          currentPhoto: item.name
        });
      }

      // Yield event loop to maintain UI 60fps & keep Host responsive
      await new Promise(r => setTimeout(r, 15));
    }

    return { totalPhotos: this.photos.size, totalFaces: totalFacesDetected };
  }

  /**
   * Search photo index against a participant's selfie face vector
   */
  findMatchesForParticipant(participantEmbedding) {
    const matches = [];
    const reviews = [];

    for (const item of this.photos.values()) {
      if (!item.faces || item.faces.length === 0) continue;

      const result = FaceEngine.matchPhoto(participantEmbedding, item.faces, this.matchThreshold);
      if (result.matched) {
        matches.push({
          photoId: item.id,
          name: item.name,
          size: item.size,
          confidence: Math.round(result.confidence * 100),
          thumbUrl: item.thumbUrl
        });
      } else if (result.reviewNeeded) {
        reviews.push({
          photoId: item.id,
          name: item.name,
          size: item.size,
          confidence: Math.round(result.confidence * 100),
          thumbUrl: item.thumbUrl
        });
      }
    }

    return { matches, reviews };
  }

  getPhoto(photoId) {
    return this.photos.get(photoId);
  }

  clear() {
    for (const item of this.photos.values()) {
      if (item.thumbUrl) {
        URL.revokeObjectURL(item.thumbUrl);
      }
    }
    this.photos.clear();
    this.duplicateSet.clear();
  }
}

window.photoIndexer = new PhotoIndexer();
