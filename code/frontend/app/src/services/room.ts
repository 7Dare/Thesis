import type {
  CloseRoomReq,
  CloseRoomRes,
  CurrentActiveRoomRes,
  CreateRoomReq,
  CreateRoomRes,
  JoinByInviteReq,
  JoinByInviteRes,
  LeaveRoomReq,
  LeaveRoomRes,
  RoomRecommendationsRes,
  RoomStudyTimeRes,
  ResumeCheckRes,
  RoomDetail,
} from '@/types/room';

import { apiGet, apiPost } from './http';

export function createRoomApi(req: CreateRoomReq): Promise<CreateRoomRes> {
  return apiPost<CreateRoomReq, CreateRoomRes>('/rooms', req);
}

export function joinByInviteApi(req: JoinByInviteReq): Promise<JoinByInviteRes> {
  return apiPost<JoinByInviteReq, JoinByInviteRes>('/rooms/join-by-invite', req);
}

export function getCurrentActiveRoomApi(userId: string): Promise<CurrentActiveRoomRes> {
  const q = new URLSearchParams({ user_id: userId });
  return apiGet<CurrentActiveRoomRes>(`/rooms/active/current?${q.toString()}`);
}

export function getRoomRecommendationsApi(userId: string, limit = 6): Promise<RoomRecommendationsRes> {
  const q = new URLSearchParams({ user_id: userId, limit: String(limit) });
  return apiGet<RoomRecommendationsRes>(`/rooms/recommendations?${q.toString()}`);
}

export function leaveRoomApi(roomId: string, req: LeaveRoomReq): Promise<LeaveRoomRes> {
  return apiPost<LeaveRoomReq, LeaveRoomRes>(`/rooms/${roomId}/leave`, req);
}

export function closeRoomApi(roomId: string, req: CloseRoomReq): Promise<CloseRoomRes> {
  return apiPost<CloseRoomReq, CloseRoomRes>(`/rooms/${roomId}/close`, req);
}

export function getRoomApi(roomId: string): Promise<RoomDetail> {
  return apiGet<RoomDetail>(`/rooms/${roomId}`);
}

export function resumeCheckApi(roomId: string, userId: string): Promise<ResumeCheckRes> {
  const q = new URLSearchParams({ user_id: userId });
  return apiGet<ResumeCheckRes>(`/rooms/${roomId}/resume-check?${q.toString()}`);
}

export function getRoomStudyTimeApi(roomId: string, userId: string): Promise<RoomStudyTimeRes> {
  const q = new URLSearchParams({ user_id: userId });
  return apiGet<RoomStudyTimeRes>(`/rooms/${roomId}/study-time?${q.toString()}`);
}
