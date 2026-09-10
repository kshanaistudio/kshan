/**
 * FaceShare Face Engine
 * Browser-based ultra-fast face detection and embedding pipeline
 * Uses MediaPipe / Face-API / ONNX Runtime Web for 100% on-device biometric extraction.
 * No photos, selfies or vectors ever leave the client's device to the cloud.
 */

class FaceEngine {
  constructor() {
    this.isLoaded = false;
    this.loadingPromise = null;
    this.detector = null;
    this.matchThreshold = 0.60; // Cosine similarity threshold
  }

  async init() {
    if (this.isLoaded) return true;
    if (this.loadingPromise) return this.loadingPromise;

    this.loadingPromise = (async () => {
      try {
        console.log('[FaceEngine] Initializing Face Detection & Feature Extractor...');
        
        // Ensure human-friendly face-api or WebAssembly models are available
        // We load face-api.js or lightweight mobile pipeline from trusted CDN / local static
        await this.loadDependencies();
        this.isLoaded = true;
        console.log('[FaceEngine] Face Engine initialized successfully.');
        return true;
      } catch (err) {
        console.error('[FaceEngine] Failed to initialize face engine:', err);
        throw err;
      }
    })();

    return this.loadingPromise;
  }

  async loadDependencies() {
    // If faceapi is already on window, initialize models
    if (window.faceapi) {
      const MODEL_URL = 'https://cdn.jsdelivr.net/npm/@vladmandic/face-api/model/';
      await Promise.all([
        faceapi.nets.ssdMobilenetv1.loadFromUri(MODEL_URL),
        faceapi.nets.faceLandmark68Net.loadFromUri(MODEL_URL),
        faceapi.nets.faceRecognitionNet.loadFromUri(MODEL_URL)
      ]);
      return;
    }

    // Dynamically inject face-api if not pre-loaded
    await new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = 'https://cdn.jsdelivr.net/npm/@vladmandic/face-api@1.7.12/dist/face-api.js';
      script.async = true;
      script.onload = async () => {
        try {
          const MODEL_URL = 'https://cdn.jsdelivr.net/npm/@vladmandic/face-api/model/';
          await Promise.all([
            faceapi.nets.ssdMobilenetv1.loadFromUri(MODEL_URL),
            faceapi.nets.faceLandmark68Net.loadFromUri(MODEL_URL),
            faceapi.nets.faceRecognitionNet.loadFromUri(MODEL_URL)
          ]);
          resolve();
        } catch (e) {
          reject(e);
        }
      };
      script.onerror = () => reject(new Error('Failed to load Face Recognition libraries'));
      document.head.appendChild(script);
    });
  }

  /**
   * Corrects orientation and resizes image element or canvas for fast face processing
   */
  async getProcessedCanvas(fileOrBlob, maxDim = 1280) {
    return new Promise((resolve, reject) => {
      const img = new Image();
      const url = URL.createObjectURL(fileOrBlob);
      img.onload = () => {
        let w = img.naturalWidth || img.width;
        let h = img.naturalHeight || img.height;

        if (Math.max(w, h) > maxDim) {
          const scale = maxDim / Math.max(w, h);
          w = Math.round(w * scale);
          h = Math.round(h * scale);
        }

        const canvas = document.createElement('canvas');
        canvas.width = w;
        canvas.height = h;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(img, 0, 0, w, h);
        URL.revokeObjectURL(url);
        resolve(canvas);
      };
      img.onerror = (e) => {
        URL.revokeObjectURL(url);
        reject(e);
      };
      img.src = url;
    });
  }

  /**
   * Extract all faces from a photo (Host batch scanning)
   * Returns array of { bbox, score, descriptor (Float32Array) }
   */
  async extractFaces(canvasOrImg) {
    await this.init();
    const detections = await faceapi
      .detectAllFaces(canvasOrImg, new faceapi.SsdMobilenetv1Options({ minConfidence: 0.38 }))
      .withFaceLandmarks()
      .withFaceDescriptors();

    return detections.map(d => ({
      bbox: [
        Math.round(d.detection.box.x),
        Math.round(d.detection.box.y),
        Math.round(d.detection.box.width),
        Math.round(d.detection.box.height)
      ],
      score: d.detection.score,
      descriptor: Array.from(d.descriptor) // 128-dim normalized embedding
    }));
  }

  /**
   * Extract and validate a single selfie (Participant Flow)
   * Must have exactly 1 clear face
   */
  async extractSelfieEmbedding(canvasOrImg) {
    await this.init();
    const detections = await faceapi
      .detectAllFaces(canvasOrImg, new faceapi.SsdMobilenetv1Options({ minConfidence: 0.45 }))
      .withFaceLandmarks()
      .withFaceDescriptors();

    if (!detections || detections.length === 0) {
      throw new Error('No face detected. Please ensure your face is well-lit and facing the camera directly.');
    }

    if (detections.length > 1) {
      throw new Error('Multiple faces detected. Please ensure only you are in the selfie frame.');
    }

    const face = detections[0];
    return {
      descriptor: Array.from(face.descriptor),
      score: face.detection.score,
      bbox: [
        Math.round(face.detection.box.x),
        Math.round(face.detection.box.y),
        Math.round(face.detection.box.width),
        Math.round(face.detection.box.height)
      ]
    };
  }

  /**
   * Cosine similarity between two float vectors
   */
  static cosineSimilarity(vecA, vecB) {
    let dot = 0.0;
    let normA = 0.0;
    let normB = 0.0;
    for (let i = 0; i < vecA.length; i++) {
      dot += vecA[i] * vecB[i];
      normA += vecA[i] * vecA[i];
      normB += vecB[i] * vecB[i];
    }
    if (normA === 0 || normB === 0) return 0;
    return dot / (Math.sqrt(normA) * Math.sqrt(normB));
  }

  /**
   * Compare participant embedding against a list of photo faces
   * Returns highest similarity match score
   */
  static matchPhoto(participantEmbedding, photoFaces, threshold = 0.60) {
    let bestScore = 0;
    let isMatch = false;

    for (const face of photoFaces) {
      const score = FaceEngine.cosineSimilarity(participantEmbedding, face.descriptor);
      if (score > bestScore) {
        bestScore = score;
      }
      if (score >= threshold) {
        isMatch = true;
      }
    }

    return {
      matched: isMatch,
      confidence: bestScore,
      reviewNeeded: (bestScore >= (threshold - 0.08) && bestScore < threshold)
    };
  }
}

window.faceEngine = new FaceEngine();
