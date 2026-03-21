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
