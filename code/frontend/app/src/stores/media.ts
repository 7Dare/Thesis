import { computed, ref } from 'vue';
import { defineStore } from 'pinia';

import type { PeerState } from '@/types/webrtc';

export const useMediaStore = defineStore('media', () => {
  const localStream = ref<MediaStream | null>(null);
  const peers = ref<PeerState[]>([]);
  const wsConnected = ref(false);
  const micEnabled = ref(false);
  const camEnabled = ref(false);
  const permissionGranted = ref(false);
  const lastError = ref('');

  const peerCount = computed(() => peers.value.length);

  function setLocalStream(stream: MediaStream | null): void {
    localStream.value = stream;
    if (!stream) {
      micEnabled.value = false;
      camEnabled.value = false;
      permissionGranted.value = false;
      return;
    }
    permissionGranted.value = true;
    micEnabled.value = stream.getAudioTracks().some((t) => t.enabled);
    camEnabled.value = stream.getVideoTracks().some((t) => t.enabled);
  }

  function setMicEnabled(enabled: boolean): void {
    micEnabled.value = enabled;
  }

  function setCamEnabled(enabled: boolean): void {
    camEnabled.value = enabled;
  }

  function upsertPeer(
    userId: string,
    patch: Partial<Pick<PeerState, 'displayName' | 'stream' | 'connectionState'>>,
  ): void {
    const idx = peers.value.findIndex((p) => p.userId === userId);
    if (idx < 0) {
      peers.value.push({
        userId,
        displayName: patch.displayName || 'member',
        stream: patch.stream ?? null,
        connectionState: patch.connectionState || 'new',
      });
      return;
    }

    const prev = peers.value[idx];
    if (!prev) return;
    peers.value[idx] = {
      ...prev,
      ...patch,
      displayName: patch.displayName || prev.displayName,
      stream: patch.stream === undefined ? prev.stream : patch.stream,
      connectionState: patch.connectionState || prev.connectionState,
    };
  }

  function removePeer(userId: string): void {
    peers.value = peers.value.filter((p) => p.userId !== userId);
  }

  function setWsConnected(connected: boolean): void {
    wsConnected.value = connected;
  }

  function setPermissionError(message: string): void {
    permissionGranted.value = false;
    lastError.value = message;
  }

  function setError(message: string): void {
    lastError.value = message;
  }

  function clearError(): void {
    lastError.value = '';
  }

  function resetMediaState(): void {
    localStream.value = null;
    peers.value = [];
    wsConnected.value = false;
    micEnabled.value = false;
    camEnabled.value = false;
    permissionGranted.value = false;
    lastError.value = '';
  }

  return {
    localStream,
    peers,
    peerCount,
    wsConnected,
    micEnabled,
    camEnabled,
    permissionGranted,
    lastError,
    setLocalStream,
    setMicEnabled,
    setCamEnabled,
    upsertPeer,
    removePeer,
    setWsConnected,
    setPermissionError,
    setError,
    clearError,
    resetMediaState,
  };
});
