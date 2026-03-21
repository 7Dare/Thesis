export interface IngestFrameRes {
  room_id: string;
  user_id: string;
  status: string;
  raw_status?: string;
  has_person: boolean;
  using_phone: boolean;
  person_count: number;
  phone_count: number;
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
  ts?: number;
  [key: string]: unknown;
}
