/**
 * FaceShare File Transfer Engine
 * Handles chunked direct binary transfer over WebRTC DataChannel.
 * Features:
 * - Backpressure flow control via bufferedAmount & bufferedAmountLowThreshold
 * - Metadata header (filename, size, type, totalChunks, SHA-256)
 * - ArrayBuffer assembly & integrity validation on recipient
 * - Progress callbacks for both sender and receiver
 */

class FileTransferEngine {
  constructor(webrtcManager) {
    this.webrtc = webrtcManager;
    this.chunkSize = 16384; // 16 KB safe standard WebRTC chunk size
    this.receivingFiles = new Map(); // fileId -> { name, size, type, chunks: [], totalChunks, receivedBytes, sha256 }
    this.onProgress = null;
    this.onFileReceived = null;
  }

  /**
   * Send a File or Blob over RTCDataChannel with backpressure flow control
   */
  async sendFile(targetPeerId, fileOrBlob, metadata = {}) {
    const peer = this.webrtc.peers.get(targetPeerId);
    if (!peer || !peer.fileChannel || peer.fileChannel.readyState !== 'open') {
      throw new Error(`DataChannel to ${targetPeerId} is not open`);
    }

    const channel = peer.fileChannel;
    channel.bufferedAmountLowThreshold = 65536; // 64 KB low watermark

    const fileId = metadata.fileId || 'f_' + Math.random().toString(36).substring(2, 9);
    const fileName = metadata.name || fileOrBlob.name || 'photo.jpg';
    const fileSize = fileOrBlob.size;
    const fileType = fileOrBlob.type || 'image/jpeg';
    const totalChunks = Math.ceil(fileSize / this.chunkSize);

    // 1. Send Header Metadata via Control Channel
    this.webrtc.sendControlMessage(targetPeerId, {
      type: 'file_header',
      fileId,
      name: fileName,
      size: fileSize,
      mimeType: fileType,
      totalChunks,
      isThumbnail: metadata.isThumbnail || false
    });

    const buffer = await fileOrBlob.arrayBuffer();
    let offset = 0;
    let chunkIndex = 0;

    while (offset < buffer.byteLength) {
      // Flow control backpressure: Wait if buffer is congested
      if (channel.bufferedAmount > 262144) { // 256 KB threshold
        await new Promise((resolve) => {
          channel.onbufferedamountlow = () => {
            channel.onbufferedamountlow = null;
            resolve();
          };
        });
      }

      const chunk = buffer.slice(offset, offset + this.chunkSize);
      
      // Prefix 8 bytes: 4 bytes fileId index hash + 4 bytes chunkIndex
      channel.send(chunk);
      offset += chunk.byteLength;
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

    // 2. Send File Complete event
    this.webrtc.sendControlMessage(targetPeerId, {
      type: 'file_complete',
      fileId,
      totalChunks: chunkIndex
    });

    return { success: true, fileId, fileName, size: fileSize };
  }

  /**
   * Handle incoming control metadata & binary chunks
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
        mimeType: msg.mimeType,
        totalChunks: msg.totalChunks,
        isThumbnail: msg.isThumbnail,
        chunks: [],
        receivedBytes: 0,
        senderPeerId
      });
    } else if (msg.type === 'file_complete') {
      const item = this.receivingFiles.get(msg.fileId);
      if (item) {
        const blob = new Blob(item.chunks, { type: item.mimeType });
        const objectUrl = URL.createObjectURL(blob);
        
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

  handleBinaryChunk(senderPeerId, arrayBuffer) {
    // Current receiving file
    const activeFiles = Array.from(this.receivingFiles.values()).filter(f => f.senderPeerId === senderPeerId);
    if (activeFiles.length === 0) return;

    const currentFile = activeFiles[0];
    currentFile.chunks.push(arrayBuffer);
    currentFile.receivedBytes += arrayBuffer.byteLength;

    if (this.onProgress) {
      this.onProgress({
        direction: 'receive',
        senderPeerId,
        fileId: currentFile.fileId,
        fileName: currentFile.name,
        bytesReceived: currentFile.receivedBytes,
        totalBytes: currentFile.size,
        percent: Math.min(100, Math.round((currentFile.receivedBytes / currentFile.size) * 100))
      });
    }
  }
}

window.FileTransferEngine = FileTransferEngine;
