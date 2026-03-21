import { getWsBase } from '@/utils/env';

export function buildSignalWsUrl(roomId: string, userId: string, displayName: string): string {
  const base = getWsBase();
  const params = new URLSearchParams({
    user_id: userId,
    display_name: displayName,
  });
  return `${base}/rooms/${encodeURIComponent(roomId)}/signal?${params.toString()}`;
}
