/**
 * FaceShare WebRTC Peer Connection Manager
 * Manages peer-to-peer data channels for signaling, metadata exchange and file streaming.
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

    this.peers = new Map(); // targetPeerId -> { pc, controlChannel, fileChannel, state }
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

    const pc = new RTCPeerConnection({ iceServers: this.iceServers });
    const peerData = {
      targetPeerId,
      pc,
      controlChannel: null,
      fileChannel: null,
      state: 'new'
    };

    pc.onicecandidate = (event) => {
      if (event.candidate && this.onSignalingSend) {
        this.onSignalingSend({
          action: 'webrtc_ice_candidate',
          target_peer: targetPeerId,
          candidate: event.candidate
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
    const offer = await peer.pc.createOffer();
    await peer.pc.setLocalDescription(offer);

    if (this.onSignalingSend) {
      this.onSignalingSend({
        action: 'webrtc_offer',
        target_peer: targetPeerId,
        sdp: peer.pc.localDescription
      });
    }
  }

  async handleOffer(fromPeerId, sdp) {
    const peer = this.getOrCreatePeer(fromPeerId);
    await peer.pc.setRemoteDescription(new RTCSessionDescription(sdp));
    const answer = await peer.pc.createAnswer();
    await peer.pc.setLocalDescription(answer);

    if (this.onSignalingSend) {
      this.onSignalingSend({
        action: 'webrtc_answer',
        target_peer: fromPeerId,
        sdp: peer.pc.localDescription
      });
    }
  }

  async handleAnswer(fromPeerId, sdp) {
    const peer = this.getOrCreatePeer(fromPeerId);
    await peer.pc.setRemoteDescription(new RTCSessionDescription(sdp));
  }

  async handleIceCandidate(fromPeerId, candidate) {
    const peer = this.getOrCreatePeer(fromPeerId);
    if (candidate) {
      try {
        await peer.pc.addIceCandidate(new RTCIceCandidate(candidate));
      } catch (err) {
        console.warn('[WebRTC] Error adding ICE candidate:', err);
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
    return false;
  }

  closePeer(targetPeerId) {
    const peer = this.peers.get(targetPeerId);
    if (peer) {
      if (peer.controlChannel) peer.controlChannel.close();
      if (peer.fileChannel) peer.fileChannel.close();
      peer.pc.close();
      this.peers.delete(targetPeerId);
    }
  }

  closeAll() {
    for (const peerId of this.peers.keys()) {
      this.closePeer(peerId);
    }
  }
}

window.WebRTCManager = WebRTCManager;
