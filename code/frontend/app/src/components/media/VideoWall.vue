<script setup lang="ts">
import StreamTile from './StreamTile.vue';

import type { PeerState } from '@/types/webrtc';

defineProps<{
  localStream: MediaStream | null;
  localName: string;
  peers: PeerState[];
  wsConnected: boolean;
  micEnabled: boolean;
  camEnabled: boolean;
  permissionGranted: boolean;
  errorText: string;
}>();

const emit = defineEmits<{
  'toggle-mic': [];
  'toggle-cam': [];
}>();
</script>

<template>
  <article class="card">
    <div class="media-toolbar">
      <h2>视频连麦</h2>
      <div class="media-actions">
        <button class="btn" type="button" @click="emit('toggle-mic')">
          {{ micEnabled ? '麦克风开' : '麦克风关' }}
        </button>
        <button class="btn" type="button" @click="emit('toggle-cam')">
          {{ camEnabled ? '摄像头开' : '摄像头关' }}
        </button>
      </div>
    </div>

    <p class="subtitle media-subtitle">
      信令：{{ wsConnected ? '已连接' : '未连接' }} | 远端人数：{{ peers.length }}
    </p>
    <p v-if="errorText" class="tip tip-error">{{ errorText }}</p>
    <p v-else-if="!permissionGranted" class="tip">未获取音视频权限，连麦不可用。</p>

    <div class="video-grid">
      <StreamTile
        :stream="localStream"
        :label="`${localName}（我）`"
        state-text="local"
        :muted="true"
      />
      <StreamTile
        v-for="peer in peers"
        :key="peer.userId"
        :stream="peer.stream"
        :label="peer.displayName || peer.userId"
        :state-text="peer.connectionState"
      />
    </div>
  </article>
</template>

