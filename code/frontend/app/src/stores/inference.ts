import { ref } from 'vue';
import { defineStore } from 'pinia';

import type { InferenceStatusRes, IngestFrameRes } from '@/types/inference';

export const useInferenceStore = defineStore('inference', () => {
  const status = ref('-');
  const personCount = ref(0);
  const phoneCount = ref(0);
  const focusLabel = ref('-');
  const focusScore = ref<number | null>(null);
  const focusEnabled = ref(false);
  const distracted = ref(false);
  const distractionRate = ref<number | null>(null);
  const interventionRequired = ref(false);
  const focusWindowSeconds = ref<number | null>(null);
  const focusWindowFrames = ref(0);
  const ts = ref<number | null>(null);
  const snapshotUrl = ref('');
  const lastError = ref('');

  function setFromStatus(payload: InferenceStatusRes): void {
    status.value = payload.status || '-';
    personCount.value = payload.person_count ?? personCount.value;
    phoneCount.value = payload.phone_count ?? phoneCount.value;
    focusLabel.value = payload.focus_label ?? focusLabel.value;
    focusScore.value = payload.focus_score ?? focusScore.value;
    focusEnabled.value = payload.focus_enabled ?? focusEnabled.value;
    distracted.value = payload.distracted ?? distracted.value;
    distractionRate.value = payload.distraction_rate ?? distractionRate.value;
    interventionRequired.value = payload.intervention_required ?? interventionRequired.value;
    focusWindowSeconds.value = payload.focus_window_seconds ?? focusWindowSeconds.value;
    focusWindowFrames.value = payload.focus_window_frames ?? focusWindowFrames.value;
    ts.value = payload.ts ?? ts.value;
  }

  function setFromIngest(payload: IngestFrameRes): void {
    status.value = payload.status;
    personCount.value = payload.person_count;
    phoneCount.value = payload.phone_count;
    focusLabel.value = payload.focus_label ?? focusLabel.value;
    focusScore.value = payload.focus_score ?? focusScore.value;
    focusEnabled.value = payload.focus_enabled ?? focusEnabled.value;
    distracted.value = payload.distracted ?? distracted.value;
    distractionRate.value = payload.distraction_rate ?? distractionRate.value;
    interventionRequired.value = payload.intervention_required ?? interventionRequired.value;
    focusWindowSeconds.value = payload.focus_window_seconds ?? focusWindowSeconds.value;
    focusWindowFrames.value = payload.focus_window_frames ?? focusWindowFrames.value;
    ts.value = payload.ts;
  }

  function setSnapshotUrl(nextUrl: string): void {
    snapshotUrl.value = nextUrl;
  }

  function setError(message: string): void {
    lastError.value = message;
  }

  function clearError(): void {
    lastError.value = '';
  }

  function resetInferenceState(): void {
    status.value = '-';
    personCount.value = 0;
    phoneCount.value = 0;
    focusLabel.value = '-';
    focusScore.value = null;
    focusEnabled.value = false;
    distracted.value = false;
    distractionRate.value = null;
    interventionRequired.value = false;
    focusWindowSeconds.value = null;
    focusWindowFrames.value = 0;
    ts.value = null;
    snapshotUrl.value = '';
    lastError.value = '';
  }

  return {
    status,
    personCount,
    phoneCount,
    focusLabel,
    focusScore,
    focusEnabled,
    distracted,
    distractionRate,
    interventionRequired,
    focusWindowSeconds,
    focusWindowFrames,
    ts,
    snapshotUrl,
    lastError,
    setFromStatus,
    setFromIngest,
    setSnapshotUrl,
    setError,
    clearError,
    resetInferenceState,
  };
});
