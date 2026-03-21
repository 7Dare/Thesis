<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue';

import { getInferenceStatusApi, getSnapshotApi, ingestFrameApi } from '@/services';
import { useInferenceStore } from '@/stores/inference';
import { isApiClientError } from '@/utils/error';

const props = defineProps<{
  roomId: string;
  userId: string;
  localStream: MediaStream | null;
}>();

const inferenceStore = useInferenceStore();

const captureVideoRef = ref<HTMLVideoElement | null>(null);
const captureCanvasRef = ref<HTMLCanvasElement | null>(null);
let uploadTimer: ReturnType<typeof setInterval> | null = null;
let statusTimer: ReturnType<typeof setInterval> | null = null;
let snapshotTimer: ReturnType<typeof setInterval> | null = null;
let snapshotObjectUrl = '';
let uploading = false;

function clearTimers(): void {
  if (uploadTimer) clearInterval(uploadTimer);
  if (statusTimer) clearInterval(statusTimer);
  if (snapshotTimer) clearInterval(snapshotTimer);
  uploadTimer = null;
  statusTimer = null;
  snapshotTimer = null;
}

function bindCaptureStream(stream: MediaStream | null): void {
  if (!captureVideoRef.value) return;
  captureVideoRef.value.srcObject = stream;
  if (stream) {
    void captureVideoRef.value.play().catch(() => {
      // Ignore autoplay promise rejection and keep retrying via next ticks.
    });
  }
}

async function ingestOnce(): Promise<void> {
  if (uploading) return;
  if (!captureVideoRef.value || !captureCanvasRef.value) return;
  if (!props.roomId || !props.userId || !props.localStream) return;
  if (captureVideoRef.value.readyState < 2) return;
  if (!captureVideoRef.value.videoWidth || !captureVideoRef.value.videoHeight) return;

  const canvas = captureCanvasRef.value;
  const video = captureVideoRef.value;
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;

  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  uploading = true;
  try {
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise<Blob | null>((resolve) => {
      canvas.toBlob((v) => resolve(v), 'image/jpeg', 0.75);
    });
    if (!blob) return;
    const res = await ingestFrameApi(props.roomId, props.userId, blob);
    inferenceStore.setFromIngest(res);
    inferenceStore.clearError();
  } catch (err) {
    if (isApiClientError(err)) {
      inferenceStore.setError(err.message);
    } else {
      inferenceStore.setError('推理上传失败');
    }
  } finally {
    uploading = false;
  }
}

async function refreshStatus(): Promise<void> {
  try {
    const res = await getInferenceStatusApi();
    inferenceStore.setFromStatus(res);
  } catch {
    // Do not break the panel if polling fails.
  }
}

async function refreshSnapshot(): Promise<void> {
  try {
    const blob = await getSnapshotApi();
    const nextUrl = URL.createObjectURL(blob);
    if (snapshotObjectUrl) URL.revokeObjectURL(snapshotObjectUrl);
    snapshotObjectUrl = nextUrl;
    inferenceStore.setSnapshotUrl(nextUrl);
  } catch {
    // Keep previous snapshot silently.
  }
}

function startLoop(): void {
  clearTimers();
  uploadTimer = setInterval(() => {
    void ingestOnce();
  }, 700);
  statusTimer = setInterval(() => {
    void refreshStatus();
  }, 1000);
  snapshotTimer = setInterval(() => {
    void refreshSnapshot();
  }, 2000);
}

function stopLoop(): void {
  clearTimers();
}

watch(
  () => props.localStream,
  (stream) => {
    bindCaptureStream(stream);
    if (stream) {
      startLoop();
    } else {
      stopLoop();
    }
  },
  { immediate: true },
);

onMounted(() => {
  bindCaptureStream(props.localStream);
});

onBeforeUnmount(() => {
  stopLoop();
  if (captureVideoRef.value) {
    captureVideoRef.value.srcObject = null;
  }
  if (snapshotObjectUrl) {
    URL.revokeObjectURL(snapshotObjectUrl);
    snapshotObjectUrl = '';
  }
  inferenceStore.resetInferenceState();
});
</script>

<template>
  <article class="card">
    <h2>YOLO 状态</h2>
    <p class="subtitle">
      status: {{ inferenceStore.status }} | person: {{ inferenceStore.personCount }} | phone:
      {{ inferenceStore.phoneCount }}
    </p>
    <p class="subtitle">ts: {{ inferenceStore.ts ?? '-' }}</p>
    <p v-if="inferenceStore.lastError" class="tip tip-error">{{ inferenceStore.lastError }}</p>

    <video ref="captureVideoRef" class="capture-video" autoplay playsinline muted />
    <canvas ref="captureCanvasRef" class="capture-canvas" />

    <div class="snapshot-box">
      <img
        v-if="inferenceStore.snapshotUrl"
        :src="inferenceStore.snapshotUrl"
        alt="snapshot"
        class="snapshot-image"
      />
      <p v-else class="chat-empty">暂无快照</p>
    </div>
  </article>
</template>
