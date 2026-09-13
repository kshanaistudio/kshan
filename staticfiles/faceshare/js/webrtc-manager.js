/**
 * FaceShare WebRTC Peer Connection Manager
 * Manages peer-to-peer data channels for signaling, metadata exchange and file streaming.
 * Features:
 * - Robust ICE Candidate buffering before remote description is set
 * - Ordered control and file streaming RTCDataChannels
 * - Automatic connection state tracking and graceful reconnection/teardown
 */

class WebRTCManager {
  constructor(options = {}) {
    this.role = options.role || 'participant'; // 'host' or 'participant'
    this.roomCode = options.roomCode;
    this.peerId = options.peerId || 'host';
    this.stunUrl = options.stunUrl || 'stun:stun.l.google.com:19302';
    this.turnUrl = options.turnUrl || '';
    this.turnUsername = options.turnUsername || '';
    this.turnCredential = options.turnCredential || '';

    this.onMessage = options.onMessage || null;
    this.onConnectionState = options.onConnectionState || null;
    this.onSignalingSend = options.onSignalingSend || null;

    this.peers = new Map(); // targetPeerId -> { pc, controlChannel, fileChannel, state, pendingCandidates, isRemoteDescriptionSet }
    this.iceServers = this.buildIceServers();
  }

  buildIceServers() {
    const servers = [{ urls: this.stunUrl }];
    if (this.turnUrl) {
      const turnConfig = { urls: this.turnUrl };
      if (this.turnUsername) turnConfig.username = this.turnUsername;
      if (this.turnCredential) turnConfig.credential = this.turnCredential;
      servers.push(turnConfig);
    }
    return servers;
  }

  getOrCreatePeer(targetPeerId) {
    if (this.peers.has(targetPeerId)) {
      return this.peers.get(targetPeerId);
    }

    const pc = new RTCPeerConnection({
      iceServers: this.iceServers,
      iceCandidatePoolSize: 10
    });

    const peerData = {
      targetPeerId,
      pc,
      controlChannel: null,
      fileChannel: null,
      state: 'new',
      pendingCandidates: [],
      isRemoteDescriptionSet: false
    };

    pc.onicecandidate = (event) => {
      if (event.candidate && this.onSignalingSend) {
        this.onSignalingSend({
          action: 'webrtc_ice_candidate',
          target_peer: targetPeerId,
          candidate: event.candidate.toJSON ? event.candidate.toJSON() : event.candidate
        });
      }
    };

    pc.onconnectionstatechange = () => {
      peerData.state = pc.connectionState;
      console.log(`[WebRTC] Peer ${targetPeerId} connection state: ${pc.connectionState}`);
      if (this.onConnectionState) {
        this.onConnectionState(targetPeerId, pc.connectionState);
      }
    };

    pc.oniceconnectionstatechange = () => {
      console.log(`[WebRTC] Peer ${targetPeerId} ICE state: ${pc.iceConnectionState}`);
      if (pc.iceConnectionState === 'failed') {
        try {
          pc.restartIce();
        } catch (e) {
          console.warn('[WebRTC] ICE restart error:', e);
        }
      }
    };

    // If host, create the Data Channels
    if (this.role === 'host') {
      const controlChannel = pc.createDataChannel('control', { ordered: true });
      const fileChannel = pc.createDataChannel('file_stream', { ordered: true });
      this.setupDataChannel(targetPeerId, controlChannel, 'control');
      this.setupDataChannel(targetPeerId, fileChannel, 'file_stream');
      peerData.controlChannel = controlChannel;
      peerData.fileChannel = fileChannel;
    } else {
      // Participant listens for channels created by Host
      pc.ondatachannel = (event) => {
        const channel = event.channel;
        console.log(`[WebRTC] Received DataChannel: ${channel.label} from ${targetPeerId}`);
        if (channel.label === 'control') {
          peerData.controlChannel = channel;
        } else if (channel.label === 'file_stream') {
          peerData.fileChannel = channel;
        }
        this.setupDataChannel(targetPeerId, channel, channel.label);
      };
    }

    this.peers.set(targetPeerId, peerData);
    return peerData;
  }

  setupDataChannel(targetPeerId, channel, type) {
    channel.binaryType = 'arraybuffer';

    channel.onopen = () => {
      console.log(`[WebRTC] ${type} DataChannel opened with ${targetPeerId}`);
      if (this.onConnectionState) {
        this.onConnectionState(targetPeerId, 'connected');
      }
    };

    channel.onclose = () => {
      console.log(`[WebRTC] ${type} DataChannel closed with ${targetPeerId}`);
    };

    channel.onerror = (err) => {
      console.error(`[WebRTC] ${type} DataChannel error:`, err);
    };

    channel.onmessage = (event) => {
      if (this.onMessage) {
        this.onMessage(targetPeerId, type, event.data);
      }
    };
  }

  async createOffer(targetPeerId) {
    const peer = this.getOrCreatePeer(targetPeerId);
    try {
      const offer = await peer.pc.createOffer({
        offerToReceiveAudio: false,
        offerToReceiveVideo: false
      });
      await peer.pc.setLocalDescription(offer);

      if (this.onSignalingSend) {
        this.onSignalingSend({
          action: 'webrtc_offer',
          target_peer: targetPeerId,
          sdp: peer.pc.localDescription
        });
      }
    } catch (err) {
      console.error(`[WebRTC] Error creating offer to ${targetPeerId}:`, err);
      throw err;
    }
  }

  async handleOffer(fromPeerId, sdp) {
    const peer = this.getOrCreatePeer(fromPeerId);
    try {
      await peer.pc.setRemoteDescription(new RTCSessionDescription(sdp));
      peer.isRemoteDescriptionSet = true;
      await this.drainPendingCandidates(peer);

      const answer = await peer.pc.createAnswer();
      await peer.pc.setLocalDescription(answer);

      if (this.onSignalingSend) {
        this.onSignalingSend({
          action: 'webrtc_answer',
          target_peer: fromPeerId,
          sdp: peer.pc.localDescription
        });
      }
    } catch (err) {
      console.error(`[WebRTC] Error handling offer from ${fromPeerId}:`, err);
      throw err;
    }
  }

  async handleAnswer(fromPeerId, sdp) {
    const peer = this.getOrCreatePeer(fromPeerId);
    try {
      await peer.pc.setRemoteDescription(new RTCSessionDescription(sdp));
      peer.isRemoteDescriptionSet = true;
      await this.drainPendingCandidates(peer);
    } catch (err) {
      console.error(`[WebRTC] Error handling answer from ${fromPeerId}:`, err);
      throw err;
    }
  }

  async handleIceCandidate(fromPeerId, candidate) {
    if (!candidate) return;
    const peer = this.getOrCreatePeer(fromPeerId);
    
    if (peer.pc.remoteDescription && peer.pc.remoteDescription.type) {
      try {
        await peer.pc.addIceCandidate(new RTCIceCandidate(candidate));
      } catch (err) {
        console.warn(`[WebRTC] Error adding ICE candidate directly:`, err);
      }
    } else {
      // Remote description not yet set; buffer candidate for later
      peer.pendingCandidates.push(candidate);
    }
  }

  async drainPendingCandidates(peer) {
    if (!peer.pendingCandidates || peer.pendingCandidates.length === 0) return;
    const candidates = [...peer.pendingCandidates];
    peer.pendingCandidates = [];

    for (const c of candidates) {
      try {
        await peer.pc.addIceCandidate(new RTCIceCandidate(c));
      } catch (err) {
        console.warn('[WebRTC] Error adding buffered ICE candidate:', err);
      }
    }
  }

  sendControlMessage(targetPeerId, data) {
    const peer = this.peers.get(targetPeerId);
    if (peer && peer.controlChannel && peer.controlChannel.readyState === 'open') {
      const payload = typeof data === 'string' ? data : JSON.stringify(data);
      peer.controlChannel.send(payload);
      return true;
    }
    console.warn(`[WebRTC] Cannot send control message to ${targetPeerId} (Channel state: ${peer?.controlChannel?.readyState})`);
    return false;
  }

  closePeer(targetPeerId) {
    const peer = this.peers.get(targetPeerId);
    if (peer) {
      try {
        if (peer.controlChannel) peer.controlChannel.close();
        if (peer.fileChannel) peer.fileChannel.close();
        peer.pc.close();
      } catch (e) {
        console.warn('[WebRTC] Error closing peer:', e);
      }
      this.peers.delete(targetPeerId);
    }
  }

  closeAll() {
    for (const peerId of Array.from(this.peers.keys())) {
      this.closePeer(peerId);
    }
  }
}

window.WebRTCManager = WebRTCManager;
