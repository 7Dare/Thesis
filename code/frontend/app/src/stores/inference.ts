import { ref } from 'vue';
import { defineStore } from 'pinia';

import type { InferenceStatusRes } from '@/types/inference';

export const useInferenceStore = defineStore('inference', () => {
  const status = ref('-');
  const personCount = ref(0);
  const phoneCount = ref(0);
  const ts = ref<number | null>(null);
  const snapshotUrl = ref('');
  const lastError = ref('');

  function setFromStatus(payload: InferenceStatusRes): void {
    status.value = payload.status || '-';
    personCount.value = payload.person_count ?? personCount.value;
    phoneCount.value = payload.phone_count ?? phoneCount.value;
    ts.value = payload.ts ?? ts.value;
  }

  function setFromIngest(payload: {
    status: string;
    person_count: number;
    phone_count: number;
    ts: number;
  }): void {
    status.value = payload.status;
    personCount.value = payload.person_count;
    phoneCount.value = payload.phone_count;
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
    ts.value = null;
    snapshotUrl.value = '';
    lastError.value = '';
  }

  return {
    status,
    personCount,
    phoneCount,
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

