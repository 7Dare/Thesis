import type { StudyCalendarRes } from '@/types/user-stats';

import { apiGet } from './http';

export function getStudyCalendarApi(userId: string, days = 365): Promise<StudyCalendarRes> {
  const q = new URLSearchParams({ days: String(days) });
  return apiGet<StudyCalendarRes>(`/users/${encodeURIComponent(userId)}/study-calendar?${q.toString()}`);
}

