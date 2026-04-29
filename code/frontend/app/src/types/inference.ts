export interface IngestFrameRes {
  room_id: string;
  user_id: string;
  status: string;
  raw_status?: string;
  has_person: boolean;
  using_phone: boolean;
  person_count: number;
  phone_count: number;
  focus_label?: string;
  focus_score?: number;
  focus_enabled?: boolean;
  distracted?: boolean;
  distraction_rate?: number;
  intervention_required?: boolean;
  focus_window_seconds?: number;
  focus_window_frames?: number;
  focus_detail?: Record<string, number>;
  ts: number;
}

export interface InferenceStatusRes {
  room_id?: string;
  user_id?: string;
  status: string;
  has_person?: boolean;
  using_phone?: boolean;
  person_count?: number;
  phone_count?: number;
  focus_label?: string;
  focus_score?: number;
  focus_enabled?: boolean;
  distracted?: boolean;
  distraction_rate?: number;
  intervention_required?: boolean;
  focus_window_seconds?: number;
  focus_window_frames?: number;
  focus_detail?: Record<string, number>;
  ts?: number;
  [key: string]: unknown;
}
