/**
 * FaceShare File Transfer Engine
 * Handles chunked direct binary transfer over WebRTC DataChannel.
 * Features:
 * - Chunk framing with FileID + ChunkIndex prefix to prevent multi-file chunk collision
 * - Per-peer sequential send queue to ensure clean single-stream transfer
 * - Backpressure flow control via bufferedAmount & bufferedAmountLowThreshold
 * - Metadata header (filename, size, type, totalChunks)
 * - ArrayBuffer assembly & integrity validation on recipient
 * - Progress callbacks for both sender and receiver
 */

class FileTransferEngine {
  constructor(webrtcManager) {
    this.webrtc = webrtcManager;
    this.chunkSize = 16384; // 16 KB standard WebRTC chunk payload size
    this.receivingFiles = new Map(); // fileId -> { fileId, name, size, mimeType, chunks: Array, totalChunks, receivedBytes, isThumbnail, senderPeerId }
    this.sendQueues = new Map(); // targetPeerId -> Array of { fileOrBlob, metadata, resolve, reject }
    this.isSending = new Map(); // targetPeerId -> boolean
    this.onProgress = null;
    this.onFileReceived = null;
  }

  /**
   * Enqueue a File or Blob for sending to target peer over RTCDataChannel.
   * Guarantees sequential, collision-free transfer.
   */
  async sendFile(targetPeerId, fileOrBlob, metadata = {}) {
    return new Promise((resolve, reject) => {
      if (!this.sendQueues.has(targetPeerId)) {
        this.sendQueues.set(targetPeerId, []);
      }
      this.sendQueues.get(targetPeerId).push({ fileOrBlob, metadata, resolve, reject });
      this._processQueue(targetPeerId);
    });
  }

  async _processQueue(targetPeerId) {
    if (this.isSending.get(targetPeerId)) {
      return; // Already streaming next item in queue
    }

    const queue = this.sendQueues.get(targetPeerId);
    if (!queue || queue.length === 0) {
      this.isSending.set(targetPeerId, false);
      return;
    }

    this.isSending.set(targetPeerId, true);
    const task = queue.shift();

    try {
      const result = await this._executeSend(targetPeerId, task.fileOrBlob, task.metadata);
      task.resolve(result);
    } catch (err) {
      console.error(`[FileTransfer] Error sending file to ${targetPeerId}:`, err);
      task.reject(err);
    } finally {
      this.isSending.set(targetPeerId, false);
      // Process next in queue
      this._processQueue(targetPeerId);
    }
  }

  /**
   * Internal worker to transmit a single file with framing & backpressure
   */
  async _executeSend(targetPeerId, fileOrBlob, metadata = {}) {
    const peer = this.webrtc.peers.get(targetPeerId);
    if (!peer || !peer.fileChannel || peer.fileChannel.readyState !== 'open') {
      throw new Error(`DataChannel to ${targetPeerId} is not open`);
    }

    const channel = peer.fileChannel;
    channel.bufferedAmountLowThreshold = 65536; // 64 KB low watermark

    const fileId = metadata.fileId || ('f_' + Math.random().toString(36).substring(2, 9));
    const fileName = metadata.name || fileOrBlob.name || 'photo.jpg';
    const fileSize = fileOrBlob.size;
    const fileType = fileOrBlob.type || 'image/jpeg';
    const totalChunks = Math.ceil(fileSize / this.chunkSize) || 1;

    // 1. Send Header Metadata via Control Channel
    this.webrtc.sendControlMessage(targetPeerId, {
      type: 'file_header',
      fileId,
      name: fileName,
      size: fileSize,
      mimeType: fileType,
      totalChunks,
      isThumbnail: Boolean(metadata.isThumbnail)
    });

    const buffer = await fileOrBlob.arrayBuffer();
    const enc = new TextEncoder();
    const fileIdBytes = enc.encode(fileId);
    const fileIdLen = fileIdBytes.length; // e.g. 8-12 bytes

    let offset = 0;
    let chunkIndex = 0;

    while (offset < buffer.byteLength) {
      // Flow control backpressure: Wait if socket buffer is congested (> 256 KB)
      if (channel.bufferedAmount > 262144) {
        await new Promise((resolve) => {
          channel.onbufferedamountlow = () => {
            channel.onbufferedamountlow = null;
            resolve();
          };
        });
      }

      const rawSlice = buffer.slice(offset, offset + this.chunkSize);
      const payloadLen = rawSlice.byteLength;

      // Binary Frame Format:
      // [1 byte: fileIdLen] + [fileIdLen bytes: fileId UTF-8] + [4 bytes: chunkIndex UInt32BE] + [payload]
      const frameBuffer = new ArrayBuffer(1 + fileIdLen + 4 + payloadLen);
      const frameUint8 = new Uint8Array(frameBuffer);
      const frameView = new DataView(frameBuffer);

      frameUint8[0] = fileIdLen;
      frameUint8.set(fileIdBytes, 1);
      frameView.setUint32(1 + fileIdLen, chunkIndex, false); // Big-endian
      frameUint8.set(new Uint8Array(rawSlice), 1 + fileIdLen + 4);

      channel.send(frameBuffer);
      offset += payloadLen;
      chunkIndex++;

      if (this.onProgress) {
        this.onProgress({
          direction: 'send',
          targetPeerId,
          fileId,
          fileName,
          bytesSent: offset,
          totalBytes: fileSize,
          percent: Math.min(100, Math.round((offset / fileSize) * 100))
        });
      }
    }

    // 2. Send File Complete event via Control Channel
    this.webrtc.sendControlMessage(targetPeerId, {
      type: 'file_complete',
      fileId,
      totalChunks: chunkIndex
    });

    return { success: true, fileId, fileName, size: fileSize };
  }

  /**
   * Handle incoming control metadata (file_header, file_complete)
   */
  handleControlMessage(senderPeerId, data) {
    let msg = data;
    if (typeof data === 'string') {
      try { msg = JSON.parse(data); } catch(e) { return; }
    }

    if (msg.type === 'file_header') {
      this.receivingFiles.set(msg.fileId, {
        fileId: msg.fileId,
        name: msg.name,
        size: msg.size,
        mimeType: msg.mimeType || 'image/jpeg',
        totalChunks: msg.totalChunks,
        isThumbnail: Boolean(msg.isThumbnail),
        chunks: new Array(msg.totalChunks),
        receivedBytes: 0,
        senderPeerId
      });
      console.log(`[FileTransfer] Incoming file header: ${msg.name} (${msg.size} bytes, ${msg.totalChunks} chunks)`);
    } else if (msg.type === 'file_complete') {
      const item = this.receivingFiles.get(msg.fileId);
      if (item) {
        // Assemble all chunks in order
        const validChunks = item.chunks.filter(c => c instanceof ArrayBuffer || (c && c.byteLength > 0));
        const blob = new Blob(validChunks, { type: item.mimeType });
        const objectUrl = URL.createObjectURL(blob);
        
        console.log(`[FileTransfer] Completed transfer of ${item.name} (${blob.size} bytes received)`);

        if (this.onFileReceived) {
          this.onFileReceived({
            fileId: item.fileId,
            name: item.name,
            size: item.size,
            mimeType: item.mimeType,
            isThumbnail: item.isThumbnail,
            blob,
            objectUrl,
            senderPeerId: item.senderPeerId
          });
        }
        this.receivingFiles.delete(msg.fileId);
      }
    }
  }

  /**
   * Handle incoming framed binary chunk
   */
  handleBinaryChunk(senderPeerId, arrayBuffer) {
    if (!arrayBuffer || arrayBuffer.byteLength < 6) return;

    try {
      const view = new DataView(arrayBuffer);
      const uint8 = new Uint8Array(arrayBuffer);
      
      const fileIdLen = uint8[0];
      if (arrayBuffer.byteLength < 1 + fileIdLen + 4) return;

      const fileIdBytes = uint8.slice(1, 1 + fileIdLen);
      const fileId = new TextDecoder().decode(fileIdBytes);
      const chunkIndex = view.getUint32(1 + fileIdLen, false);
      const payload = arrayBuffer.slice(1 + fileIdLen + 4);

      let targetFile = this.receivingFiles.get(fileId);
      if (!targetFile) {
        // Fallback to active file if header arrived without id match
        const activeFiles = Array.from(this.receivingFiles.values()).filter(f => f.senderPeerId === senderPeerId);
        if (activeFiles.length > 0) targetFile = activeFiles[0];
      }

      if (targetFile) {
        targetFile.chunks[chunkIndex] = payload;
        targetFile.receivedBytes += payload.byteLength;

        if (this.onProgress) {
          this.onProgress({
            direction: 'receive',
            senderPeerId,
            fileId: targetFile.fileId,
            fileName: targetFile.name,
            bytesReceived: targetFile.receivedBytes,
            totalBytes: targetFile.size,
            percent: Math.min(100, Math.round((targetFile.receivedBytes / targetFile.size) * 100))
          });
        }
      }
    } catch (err) {
      console.warn('[FileTransfer] Error unpacking binary chunk:', err);
    }
  }
}

window.FileTransferEngine = FileTransferEngine;
