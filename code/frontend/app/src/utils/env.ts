export function getApiBase(): string {
  const value = import.meta.env.VITE_API_BASE as string | undefined;
  return (value || 'http://localhost:8000').replace(/\/$/, '');
}

export function getWsBase(): string {
  const value = import.meta.env.VITE_WS_BASE as string | undefined;
  if (value && value.trim()) {
    return value.replace(/\/$/, '');
  }
  return getApiBase().replace(/^http/i, 'ws');
}
