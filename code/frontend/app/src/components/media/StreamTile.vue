<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue';

const props = defineProps<{
  stream: MediaStream | null;
  label: string;
  stateText?: string;
  muted?: boolean;
}>();

const videoRef = ref<HTMLVideoElement | null>(null);

function bindStream(stream: MediaStream | null): void {
  if (!videoRef.value) return;
  videoRef.value.srcObject = stream;
}

watch(
  () => props.stream,
  (stream) => {
    bindStream(stream);
  },
  { immediate: true },
);

onBeforeUnmount(() => {
  if (videoRef.value) {
    videoRef.value.srcObject = null;
  }
});
</script>

<template>
  <article class="video-tile">
    <video ref="videoRef" autoplay playsinline :muted="muted ?? false" />
    <div class="video-tile-meta">
      <span>{{ label }}</span>
      <span v-if="stateText" class="video-state">{{ stateText }}</span>
    </div>
  </article>
</template>

