import type { InferenceStatusRes, IngestFrameRes } from '@/types/inference';

import { apiGet, apiGetBlob, apiPostMultipart } from './http';

export function ingestFrameApi(roomId: string, userId: string, frame: Blob): Promise<IngestFrameRes> {
  const formData = new FormData();
  formData.append('frame', frame, 'frame.jpg');
  formData.append('room_id', roomId);
  formData.append('user_id', userId);
  return apiPostMultipart<IngestFrameRes>('/ingest/frame', formData);
}

export function getInferenceStatusApi(): Promise<InferenceStatusRes> {
  return apiGet<InferenceStatusRes>('/status');
}

export function getSnapshotApi(): Promise<Blob> {
  return apiGetBlob('/snapshot');
}
