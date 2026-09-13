/**
 * FaceShare Face Engine
 * Browser-based fast face detection and embedding pipeline
 * Uses Face-API / ONNX Web for 100% on-device biometric extraction.
 * No photos, selfies or vectors ever leave the client's device to the cloud.
 */

class FaceEngine {
  constructor() {
    this.isLoaded = false;
    this.loadingPromise = null;
    this.matchThreshold = 0.60; // Cosine similarity threshold (128-D descriptor)
    this.activeDetector = 'ssd'; // 'ssd' or 'tiny'
    this.modelUrls = [
      'https://cdn.jsdelivr.net/npm/@vladmandic/face-api/model/',
      'https://raw.githubusercontent.com/vladmandic/face-api/master/model/'
    ];
  }

  async init(onStatus) {
    if (this.isLoaded) return true;
    if (this.loadingPromise) return this.loadingPromise;

    this.loadingPromise = (async () => {
      try {
        if (onStatus) onStatus('Loading face detection AI models...');
        console.log('[FaceEngine] Initializing Face Detection & Feature Extractor...');

        // 1. Ensure faceapi is present in window
        await this.ensureFaceApiLoaded();

        // 2. Load models with mirror fallback
        await this.loadModelsWithFallback(onStatus);

        this.isLoaded = true;
        console.log('[FaceEngine] Face Engine initialized successfully.');
        return true;
      } catch (err) {
        console.error('[FaceEngine] Failed to initialize face engine:', err);
        this.loadingPromise = null;
        throw err;
      }
    })();

    return this.loadingPromise;
  }

  async ensureFaceApiLoaded() {
    if (window.faceapi) return;

    return new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = 'https://cdn.jsdelivr.net/npm/@vladmandic/face-api@1.7.12/dist/face-api.js';
      script.async = true;
      script.onload = () => resolve();
      script.onerror = () => {
        // Fallback CDN
        const fallbackScript = document.createElement('script');
        fallbackScript.src = 'https://unpkg.com/@vladmandic/face-api@1.7.12/dist/face-api.js';
        fallbackScript.async = true;
        fallbackScript.onload = () => resolve();
        fallbackScript.onerror = () => reject(new Error('Failed to load face recognition script from CDN.'));
        document.head.appendChild(fallbackScript);
      };
      document.head.appendChild(script);
    });
  }

  async loadModelsWithFallback(onStatus) {
    let loaded = false;
    let lastError = null;

    for (const url of this.modelUrls) {
      try {
        if (onStatus) onStatus(`Loading neural weights from ${url}...`);
        console.log(`[FaceEngine] Attempting model load from: ${url}`);
        
        await Promise.all([
          faceapi.nets.ssdMobilenetv1.loadFromUri(url),
          faceapi.nets.tinyFaceDetector.loadFromUri(url),
          faceapi.nets.faceLandmark68Net.loadFromUri(url),
          faceapi.nets.faceRecognitionNet.loadFromUri(url)
        ]);

        loaded = true;
        this.activeDetector = 'ssd';
        break;
      } catch (err) {
        console.warn(`[FaceEngine] Model load failed from ${url}:`, err);
        lastError = err;
      }
    }

    if (!loaded) {
      // Try minimal TinyFaceDetector only
      try {
        const url = this.modelUrls[0];
        await Promise.all([
          faceapi.nets.tinyFaceDetector.loadFromUri(url),
          faceapi.nets.faceLandmark68Net.loadFromUri(url),
          faceapi.nets.faceRecognitionNet.loadFromUri(url)
        ]);
        this.activeDetector = 'tiny';
        loaded = true;
      } catch (e) {
        throw new Error('Could not load face recognition neural models: ' + (lastError?.message || e.message));
      }
    }
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
   * Returns array of { bbox, score, descriptor (Array<number>) }
   */
  async extractFaces(canvasOrImg) {
    await this.init();
    
    let detections = [];
    if (this.activeDetector === 'ssd' && faceapi.nets.ssdMobilenetv1.isLoaded) {
      detections = await faceapi
        .detectAllFaces(canvasOrImg, new faceapi.SsdMobilenetv1Options({ minConfidence: 0.35 }))
        .withFaceLandmarks()
        .withFaceDescriptors();
    } else {
      detections = await faceapi
        .detectAllFaces(canvasOrImg, new faceapi.TinyFaceDetectorOptions({ inputSize: 416, scoreThreshold: 0.35 }))
        .withFaceLandmarks()
        .withFaceDescriptors();
    }

    return (detections || []).map(d => ({
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
    
    let detections = [];
    if (this.activeDetector === 'ssd' && faceapi.nets.ssdMobilenetv1.isLoaded) {
      detections = await faceapi
        .detectAllFaces(canvasOrImg, new faceapi.SsdMobilenetv1Options({ minConfidence: 0.40 }))
        .withFaceLandmarks()
        .withFaceDescriptors();
    } else {
      detections = await faceapi
        .detectAllFaces(canvasOrImg, new faceapi.TinyFaceDetectorOptions({ inputSize: 416, scoreThreshold: 0.40 }))
        .withFaceLandmarks()
        .withFaceDescriptors();
    }

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
    if (!vecA || !vecB || vecA.length !== vecB.length) return 0;
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
      if (!face.descriptor) continue;
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

window.FaceEngine = FaceEngine;
window.faceEngine = new FaceEngine();
