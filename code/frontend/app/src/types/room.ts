export interface CreateRoomReq {
  host_user_id: string;
  room_name: string;
  duration_minutes: number;
}

export interface CreateRoomRes {
  room_id: string;
  room_name: string;
  host_user_id: string;
  status: string;
  created_at: string;
  ends_at: string;
  invite_code: string;
}

export interface JoinByInviteReq {
  user_id: string;
  invite_code: string;
  display_name: string;
}

export interface JoinByInviteRes {
  room_id: string;
  user_id: string;
  role: string;
  joined_at: string;
}

export interface LeaveRoomReq {
  user_id: string;
}

export interface LeaveRoomRes {
  room_id: string;
  status: string;
  member_count?: number;
  reason?: string;
}

export interface CloseRoomReq {
  host_user_id: string;
}

export interface CloseRoomRes {
  room_id: string;
  status: string;
  closed_at: string | null;
}

export interface RoomMember {
  user_id: string;
  display_name: string;
  role: string;
  joined_at: string;
}

export interface RoomDetail {
  room_id: string;
  room_name: string;
  host_user_id: string;
  status: string;
  created_at: string;
  started_at: string;
  ends_at: string;
  invite_code: string;
  member_count: number;
  members: RoomMember[];
}

export interface ResumeCheckRes {
  room_id: string;
  resumable: boolean;
  room_status: string;
  is_member: boolean;
}

export interface CurrentActiveRoomRes {
  room_id: string;
  room_name: string;
  host_user_id: string;
  status: string;
  started_at: string;
  ends_at: string;
  invite_code: string;
  role: string;
  joined_at: string;
}

export interface RoomRecommendationTag {
  code: string;
  name: string;
  score: number;
}

export interface RoomRecommendationProfile {
  avg_session_minutes: number;
  preferred_duration_minutes: number;
  preferred_period: string | null;
  preferred_period_name: string;
  study_days_30d: number;
  total_minutes_30d: number;
  intensity_level: 'new' | 'relaxed' | 'normal' | 'high' | string;
}

export interface RecommendedRoom {
  room_id: string;
  room_name: string;
  host_user_id: string;
  duration_minutes: number;
  started_at: string | null;
  ends_at: string | null;
  invite_code: string;
  member_count: number;
  max_members: number;
  member_avg_session_minutes: number;
  match_score: number;
  tags: RoomRecommendationTag[];
  reasons: string[];
}

export interface RoomRecommendationsRes {
  user_profile: RoomRecommendationProfile;
  rooms: RecommendedRoom[];
}

export interface StudyTimeMember {
  user_id: string;
  display_name: string;
  total_seconds: number;
  current_session_seconds: number;
}

export interface RoomStudyTimeRes {
  room_id: string;
  room_status: string;
  room_total_seconds: number;
  room_elapsed_seconds: number;
  my_total_seconds: number;
  members: StudyTimeMember[];
}
