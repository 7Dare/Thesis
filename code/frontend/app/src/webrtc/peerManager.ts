import { buildSignalWsUrl } from '@/services';
import type { PeerConnectionState, SignalMessage } from '@/types/webrtc';

type PeerManagerHandlers = {
  onWsStateChange: (connected: boolean) => void;
      onPeerState: (userId: string, patch: {
        displayName?: string;
        stream?: MediaStream | null;
        connectionState?: PeerConnectionState;
      }) => void;
  onPeerLeave: (userId: string) => void;
  onError: (message: string) => void;
  onRoomClosed: () => void;
};

const MAX_RECONNECT_ATTEMPTS = 5;
const RECONNECT_DELAYS_MS = [1000, 2000, 4000, 8000, 16000];

export class PeerManager {
  private roomId: string;
  private userId: string;
  private displayName: string;
  private handlers: PeerManagerHandlers;
  private ws: WebSocket | null = null;
  private manualClosed = false;
  private reconnectAttempts = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private pcs = new Map<string, RTCPeerConnection>();
  private remoteStreams = new Map<string, MediaStream>();
  private pendingIce = new Map<string, RTCIceCandidateInit[]>();
  private localStream: MediaStream | null = null;

  constructor(roomId: string, userId: string, displayName: string, handlers: PeerManagerHandlers) {
    this.roomId = roomId;
    this.userId = userId;
    this.displayName = displayName;
    this.handlers = handlers;
  }

  async initLocalStream(): Promise<MediaStream> {
    const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
    const audioTracks = stream.getAudioTracks();
    for (const track of audioTracks) {
      track.enabled = false;
    }
    this.localStream = stream;
    return stream;
  }

  setLocalStream(stream: MediaStream | null): void {
    this.localStream = stream;
  }

  getLocalStream(): MediaStream | null {
    return this.localStream;
  }

  async connectSignaling(): Promise<void> {
    this.manualClosed = false;
    this.openWebSocket();
  }

  toggleMic(): boolean {
    if (!this.localStream) return false;
    const track = this.localStream.getAudioTracks()[0];
    if (!track) return false;
    track.enabled = !track.enabled;
    return track.enabled;
  }

  toggleCamera(): boolean {
    if (!this.localStream) return false;
    const track = this.localStream.getVideoTracks()[0];
    if (!track) return false;
    track.enabled = !track.enabled;
    return track.enabled;
  }

  cleanup(): void {
    this.manualClosed = true;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.handlers.onWsStateChange(false);

    for (const [, pc] of this.pcs) {
      pc.close();
    }
    this.pcs.clear();
    this.remoteStreams.clear();
    this.pendingIce.clear();
  }

  stopLocalTracks(): void {
    if (!this.localStream) return;
    for (const track of this.localStream.getTracks()) {
      track.stop();
    }
    this.localStream = null;
  }

  private openWebSocket(): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) return;

    const url = buildSignalWsUrl(this.roomId, this.userId, this.displayName);
    const ws = new WebSocket(url);
    this.ws = ws;

    ws.onopen = () => {
      this.reconnectAttempts = 0;
      this.handlers.onWsStateChange(true);
    };

    ws.onmessage = (event) => {
      void this.handleIncoming(event.data);
    };

    ws.onerror = () => {
      // Keep real error reason in onclose event.
    };

    ws.onclose = (event) => {
      this.handlers.onWsStateChange(false);
      if (this.manualClosed) return;

      if (event.reason === 'room_not_found_or_closed') {
        this.handlers.onRoomClosed();
        return;
      }
      if (event.reason === 'not_room_member') {
        this.handlers.onError('你已不在房间成员列表中');
        return;
      }

      if (event.code === 1006) {
        this.handlers.onError('连接中断，正在重连（最多5次）');
      }

      if (event.reason) {
        this.handlers.onError(`信令连接关闭: ${event.reason}`);
      } else if (event.code && event.code !== 1006) {
        this.handlers.onError(`信令连接关闭(code=${event.code})`);
      }

      this.scheduleReconnect();
    };
  }

  private scheduleReconnect(): void {
    if (this.manualClosed) return;
    if (this.reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
      this.handlers.onError('连接失败，可返回大厅或刷新重试');
      return;
    }
    const delay = RECONNECT_DELAYS_MS[this.reconnectAttempts] || 16000;
    this.reconnectAttempts += 1;
    this.handlers.onError(`连接中断，正在重连（${this.reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS}）`);
    this.reconnectTimer = setTimeout(() => {
      this.openWebSocket();
    }, delay);
  }

  private async handleIncoming(raw: string): Promise<void> {
    let msg: SignalMessage;
    try {
      msg = JSON.parse(raw) as SignalMessage;
    } catch {
      return;
    }

    const from = (msg.from_user_id || '').trim();
    const payload = (msg.payload || {}) as Record<string, unknown>;

    if (msg.type === 'peer_join') {
      if (!from || from === this.userId) return;
      const displayName = typeof payload.display_name === 'string' ? payload.display_name : 'member';
      this.ensurePeerConnection(from, displayName);
      if (this.shouldInitiateOffer(from)) {
        await this.createOffer(from);
      }
      return;
    }

    if (msg.type === 'peer_leave') {
      if (!from) return;
      this.removePeer(from);
      return;
    }

    if (msg.type === 'offer') {
      if (!from) return;
      await this.handleOffer(from, payload);
      return;
    }

    if (msg.type === 'answer') {
      if (!from) return;
      await this.handleAnswer(from, payload);
      return;
    }

    if (msg.type === 'ice') {
      if (!from) return;
      await this.handleIce(from, payload);
      return;
    }

    if (msg.type === 'room_closed') {
      this.handlers.onRoomClosed();
      return;
    }

    if (msg.type === 'signal_error') {
      const message = typeof payload.message === 'string' ? payload.message : '信令错误';
      this.handlers.onError(message);
    }
  }

  private shouldInitiateOffer(peerUserId: string): boolean {
    return this.userId < peerUserId;
  }

  private ensurePeerConnection(peerUserId: string, displayName: string): RTCPeerConnection {
    const existing = this.pcs.get(peerUserId);
    if (existing) return existing;

    const pc = new RTCPeerConnection({
      iceServers: [{ urls: 'stun:stun.l.google.com:19302' }],
    });
    this.pcs.set(peerUserId, pc);

    this.handlers.onPeerState(peerUserId, {
      displayName,
      connectionState: 'connecting',
    });

    if (this.localStream) {
      for (const track of this.localStream.getTracks()) {
        pc.addTrack(track, this.localStream);
      }
    }

    pc.onicecandidate = (event) => {
      if (!event.candidate) return;
      this.sendSignal({
        type: 'ice',
        target_user_id: peerUserId,
        payload: event.candidate.toJSON(),
      });
    };

    pc.onconnectionstatechange = () => {
      const state = pc.connectionState as PeerConnectionState;
      this.handlers.onPeerState(peerUserId, { connectionState: state });
      if (state === 'failed' || state === 'closed') {
        this.removePeer(peerUserId);
      }
    };

    pc.ontrack = (event) => {
      const stream = event.streams[0] || this.createStreamFromTrack(event.track, peerUserId);
      this.remoteStreams.set(peerUserId, stream);
      this.handlers.onPeerState(peerUserId, { stream, connectionState: 'connected' });
    };

    return pc;
  }

  private createStreamFromTrack(track: MediaStreamTrack, peerUserId: string): MediaStream {
    const stream = this.remoteStreams.get(peerUserId) || new MediaStream();
    stream.addTrack(track);
    return stream;
  }

  private async createOffer(peerUserId: string): Promise<void> {
    const pc = this.ensurePeerConnection(peerUserId, 'member');
    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);
    this.sendSignal({
      type: 'offer',
      target_user_id: peerUserId,
      payload: offer,
    });
  }

  private async handleOffer(peerUserId: string, payload: Record<string, unknown>): Promise<void> {
    const pc = this.ensurePeerConnection(peerUserId, 'member');
    const offer = new RTCSessionDescription(payload as unknown as RTCSessionDescriptionInit);
    await pc.setRemoteDescription(offer);
    const answer = await pc.createAnswer();
    await pc.setLocalDescription(answer);
    this.sendSignal({
      type: 'answer',
      target_user_id: peerUserId,
      payload: answer,
    });
    await this.flushPendingIce(peerUserId);
  }

  private async handleAnswer(peerUserId: string, payload: Record<string, unknown>): Promise<void> {
    const pc = this.ensurePeerConnection(peerUserId, 'member');
    const answer = new RTCSessionDescription(payload as unknown as RTCSessionDescriptionInit);
    await pc.setRemoteDescription(answer);
    await this.flushPendingIce(peerUserId);
  }

  private async handleIce(peerUserId: string, payload: Record<string, unknown>): Promise<void> {
    const pc = this.ensurePeerConnection(peerUserId, 'member');
    if (!pc.remoteDescription) {
      const queue = this.pendingIce.get(peerUserId) || [];
      queue.push(payload as RTCIceCandidateInit);
      this.pendingIce.set(peerUserId, queue);
      return;
    }
    await pc.addIceCandidate(new RTCIceCandidate(payload as RTCIceCandidateInit));
  }

  private async flushPendingIce(peerUserId: string): Promise<void> {
    const pc = this.pcs.get(peerUserId);
    if (!pc || !pc.remoteDescription) return;
    const queue = this.pendingIce.get(peerUserId) || [];
    if (!queue.length) return;
    for (const item of queue) {
      await pc.addIceCandidate(new RTCIceCandidate(item));
    }
    this.pendingIce.delete(peerUserId);
  }

  private removePeer(peerUserId: string): void {
    const pc = this.pcs.get(peerUserId);
    if (pc) pc.close();
    this.pcs.delete(peerUserId);
    this.remoteStreams.delete(peerUserId);
    this.pendingIce.delete(peerUserId);
    this.handlers.onPeerLeave(peerUserId);
  }

  private sendSignal(message: {
    type: 'offer' | 'answer' | 'ice' | 'peer_ping';
    target_user_id?: string;
    payload: unknown;
  }): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
    this.ws.send(JSON.stringify(message));
  }
}
