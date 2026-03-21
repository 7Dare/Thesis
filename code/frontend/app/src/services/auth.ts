import type { LoginReq, LoginRes, RegisterReq, RegisterRes } from '@/types/auth';

import { apiPostForm } from './http';

export function registerApi(req: RegisterReq): Promise<RegisterRes> {
  return apiPostForm<RegisterRes>('/auth/register', {
    login_user_id: req.login_user_id,
    password: req.password,
    display_name: req.display_name,
    email: req.email || '',
  });
}

export function loginApi(req: LoginReq): Promise<LoginRes> {
  return apiPostForm<LoginRes>('/auth/login', {
    login_user_id: req.login_user_id,
    password: req.password,
  });
}
