import { ref } from 'vue';
import { defineStore } from 'pinia';

import type { InferenceStatusRes, IngestFrameRes } from '@/types/inference';

export const useInferenceStore = defineStore('inference', () => {
  const LOW_FOCUS_STREAK_TRIGGER = 3;
  const REMINDER_COOLDOWN_MS = 15000;

  const status = ref('-');
  const personCount = ref(0);
  const phoneCount = ref(0);
  const focusLabel = ref('-');
  const focusScore = ref<number | null>(null);
  const rawFocusScore = ref<number | null>(null);
  const focusDetail = ref<Record<string, number>>({});
  const focusEnabled = ref(false);
  const distracted = ref(false);
  const distractionRate = ref<number | null>(null);
  const interventionRequired = ref(false);
  const focusWindowSeconds = ref<number | null>(null);
  const focusWindowFrames = ref(0);
  const ts = ref<number | null>(null);
  const snapshotUrl = ref('');
  const lastError = ref('');
  const lowFocusActive = ref(false);
  const lowFocusReminder = ref('');
  let lowFocusStreak = 0;
  let lastReminderAt = 0;

  function updateLowFocusReminder(): void {
    const isLowFocus = Boolean(focusEnabled.value) && focusLabel.value === 'low_focus';
    if (isLowFocus) {
      lowFocusStreak += 1;
      const streakReached = lowFocusStreak >= LOW_FOCUS_STREAK_TRIGGER;
      if (!streakReached) return;
      lowFocusActive.value = true;
      const now = Date.now();
      if (!lowFocusReminder.value || now - lastReminderAt >= REMINDER_COOLDOWN_MS) {
        lowFocusReminder.value = '检测到当前专注度偏低，请尽快回到学习状态。';
        lastReminderAt = now;
      }
      return;
    }

    lowFocusStreak = 0;
    lowFocusActive.value = false;
    lowFocusReminder.value = '';
  }

  function setFromStatus(payload: InferenceStatusRes): void {
    status.value = payload.status || '-';
    personCount.value = payload.person_count ?? personCount.value;
    phoneCount.value = payload.phone_count ?? phoneCount.value;
    focusLabel.value = payload.focus_label ?? focusLabel.value;
    focusScore.value = payload.focus_score ?? focusScore.value;
    rawFocusScore.value = payload.raw_focus_score ?? rawFocusScore.value;
    focusDetail.value = payload.focus_detail ?? focusDetail.value;
    focusEnabled.value = payload.focus_enabled ?? focusEnabled.value;
    distracted.value = payload.distracted ?? distracted.value;
    distractionRate.value = payload.distraction_rate ?? distractionRate.value;
    interventionRequired.value = payload.intervention_required ?? interventionRequired.value;
    focusWindowSeconds.value = payload.focus_window_seconds ?? focusWindowSeconds.value;
    focusWindowFrames.value = payload.focus_window_frames ?? focusWindowFrames.value;
    ts.value = payload.ts ?? ts.value;
    updateLowFocusReminder();
  }

  function setFromIngest(payload: IngestFrameRes): void {
    status.value = payload.status;
    personCount.value = payload.person_count;
    phoneCount.value = payload.phone_count;
    focusLabel.value = payload.focus_label ?? focusLabel.value;
    focusScore.value = payload.focus_score ?? focusScore.value;
    rawFocusScore.value = payload.raw_focus_score ?? rawFocusScore.value;
    focusDetail.value = payload.focus_detail ?? focusDetail.value;
    focusEnabled.value = payload.focus_enabled ?? focusEnabled.value;
    distracted.value = payload.distracted ?? distracted.value;
    distractionRate.value = payload.distraction_rate ?? distractionRate.value;
    interventionRequired.value = payload.intervention_required ?? interventionRequired.value;
    focusWindowSeconds.value = payload.focus_window_seconds ?? focusWindowSeconds.value;
    focusWindowFrames.value = payload.focus_window_frames ?? focusWindowFrames.value;
    ts.value = payload.ts;
    updateLowFocusReminder();
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
    rawFocusScore.value = null;
    focusDetail.value = {};
    focusEnabled.value = false;
    distracted.value = false;
    distractionRate.value = null;
    interventionRequired.value = false;
    focusWindowSeconds.value = null;
    focusWindowFrames.value = 0;
    ts.value = null;
    snapshotUrl.value = '';
    lastError.value = '';
    lowFocusActive.value = false;
    lowFocusReminder.value = '';
    lowFocusStreak = 0;
    lastReminderAt = 0;
  }

  return {
    status,
    personCount,
    phoneCount,
    focusLabel,
    focusScore,
    rawFocusScore,
    focusDetail,
    focusEnabled,
    distracted,
    distractionRate,
    interventionRequired,
    focusWindowSeconds,
    focusWindowFrames,
    ts,
    snapshotUrl,
    lastError,
    lowFocusActive,
    lowFocusReminder,
    setFromStatus,
    setFromIngest,
    setSnapshotUrl,
    setError,
    clearError,
    resetInferenceState,
  };
});
