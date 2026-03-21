import axios, { type AxiosRequestConfig } from 'axios';

import type { ApiEnvelope } from '@/types/api';
import { getApiBase } from '@/utils/env';
import { ApiClientError } from '@/utils/error';

const client = axios.create({
  baseURL: getApiBase(),
  timeout: 10000,
});

function unwrapEnvelope<T>(payload: ApiEnvelope<T>): T {
  if (payload && payload.code === 0) {
    return payload.data;
  }
  const code = (payload as { code?: string }).code || 'api_error';
  const message = (payload as { message?: string }).message || '请求失败';
  throw new ApiClientError(String(code), String(message));
}

function normalizeError(err: unknown): never {
  if (err instanceof ApiClientError) {
    throw err;
  }

  if (axios.isAxiosError(err)) {
    const status = err.response?.status;
    const data = err.response?.data as { code?: string; message?: string } | undefined;
    const code = data?.code || (status ? `http_${status}` : 'network_error');
    const message = data?.message || err.message || '网络请求失败';
    throw new ApiClientError(String(code), String(message), status);
  }

  throw new ApiClientError('unknown_error', '未知错误');
}

export async function apiGet<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
  try {
    const resp = await client.get<ApiEnvelope<T>>(url, config);
    return unwrapEnvelope(resp.data);
  } catch (err) {
    normalizeError(err);
  }
}

export async function apiPost<TReq, TRes>(
  url: string,
  data: TReq,
  config?: AxiosRequestConfig,
): Promise<TRes> {
  try {
    const resp = await client.post<ApiEnvelope<TRes>>(url, data, config);
    return unwrapEnvelope(resp.data);
  } catch (err) {
    normalizeError(err);
  }
}

export async function apiPostForm<TRes>(
  url: string,
  data: Record<string, string>,
  config?: AxiosRequestConfig,
): Promise<TRes> {
  try {
    const body = new URLSearchParams(data);
    const resp = await client.post<ApiEnvelope<TRes>>(url, body, {
      ...config,
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        ...(config?.headers || {}),
      },
    });
    return unwrapEnvelope(resp.data);
  } catch (err) {
    normalizeError(err);
  }
}

export async function apiPostMultipart<TRes>(
  url: string,
  formData: FormData,
  config?: AxiosRequestConfig,
): Promise<TRes> {
  try {
    const resp = await client.post<ApiEnvelope<TRes>>(url, formData, config);
    return unwrapEnvelope(resp.data);
  } catch (err) {
    normalizeError(err);
  }
}

export async function apiGetBlob(url: string, config?: AxiosRequestConfig): Promise<Blob> {
  try {
    const resp = await client.get(url, {
      ...config,
      responseType: 'blob',
    });
    return resp.data as Blob;
  } catch (err) {
    normalizeError(err);
  }
}
