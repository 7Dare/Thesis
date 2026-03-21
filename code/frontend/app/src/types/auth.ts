export interface RegisterReq {
  login_user_id: string;
  password: string;
  display_name: string;
  email?: string;
}

export interface RegisterRes {
  user_id: string;
  login_user_id: string;
  display_name: string;
  email: string | null;
  created_at: string | null;
}

export interface LoginReq {
  login_user_id: string;
  password: string;
}

export interface LoginRes {
  user_id: string;
  login_user_id: string;
  display_name: string;
  email: string | null;
  message: string;
}
